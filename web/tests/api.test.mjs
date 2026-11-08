import assert from 'node:assert/strict';
import { afterEach, beforeEach, test } from 'node:test';
import { api, cartIssue } from '../src/lib.ts';

const originalFetch = globalThis.fetch;

function storage() {
  const values = new Map();
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  };
}

beforeEach(() => {
  globalThis.localStorage = storage();
  globalThis.sessionStorage = storage();
  globalThis.window = new EventTarget();
});

afterEach(() => { globalThis.fetch = originalFetch; delete globalThis.window; });

test('checkout retries once as a guest after an expired session', async () => {
  sessionStorage.setItem('janadhishToken', 'expired-token');
  sessionStorage.setItem('janadhishUser', JSON.stringify({ id: 7 }));
  const body = JSON.stringify({ checkout_key: 'same-reference', cart_items: [] });
  const requests = [];
  globalThis.fetch = async (path, options) => {
    requests.push({ path, body: options.body, authorization: options.headers.get('Authorization') });
    return new Response(JSON.stringify(requests.length === 1 ? { detail: 'Invalid token' } : { order_id: 42 }), {
      status: requests.length === 1 ? 401 : 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  assert.deepEqual(await api('/api/orders', { method: 'POST', body }), { order_id: 42 });
  assert.deepEqual(requests, [
    { path: '/api/orders', body, authorization: 'Bearer expired-token' },
    { path: '/api/orders', body, authorization: null },
  ]);
  assert.equal(sessionStorage.getItem('janadhishToken'), null);
  assert.equal(sessionStorage.getItem('janadhishUser'), null);
});

test('protected requests still stop on an expired session', async () => {
  sessionStorage.setItem('janadhishToken', 'expired-token');
  let requests = 0;
  globalThis.fetch = async () => {
    requests += 1;
    return new Response(JSON.stringify({ detail: 'Invalid token' }), { status: 401 });
  };

  await assert.rejects(api('/api/orders/my-orders'), /sign-in expired/i);
  assert.equal(requests, 1);
  assert.equal(sessionStorage.getItem('janadhishToken'), null);
});

test('custom requests retry once as a guest after an expired session', async () => {
  sessionStorage.setItem('janadhishToken', 'expired-token');
  const body = JSON.stringify({ garment_category: 'Kurta', measurements: { Chest: 36 } });
  const requests = [];
  globalThis.fetch = async (path, options) => {
    requests.push({ path, body: options.body, authorization: options.headers.get('Authorization') });
    return new Response(JSON.stringify(requests.length === 1 ? { detail: 'Invalid token' } : { id: 9 }), {
      status: requests.length === 1 ? 401 : 200,
    });
  };

  assert.deepEqual(await api('/api/customizations', { method: 'POST', body }), { id: 9 });
  assert.deepEqual(requests, [
    { path: '/api/customizations', body, authorization: 'Bearer expired-token' },
    { path: '/api/customizations', body, authorization: null },
  ]);
});

test('revoked admin access clears the stale session and updates the UI', async () => {
  sessionStorage.setItem('janadhishToken', 'admin-token');
  sessionStorage.setItem('janadhishUser', JSON.stringify({ id: 7, is_admin: true }));
  let changes = 0;
  window.addEventListener('janadhish-session-change', () => { changes += 1; });
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Admin access required' }), { status: 403 });

  await assert.rejects(api('/api/admin/payments'), /admin access changed/i);
  assert.equal(sessionStorage.getItem('janadhishToken'), null);
  assert.equal(sessionStorage.getItem('janadhishUser'), null);
  assert.equal(changes, 1);
});

test('saved bag blocks checkout when a piece disappears or total quantity exceeds stock', () => {
  const pieces = [{ id: 1, name: 'Test Kurti', stock_quantity: 2, sizes: ['M'], colors: ['Red'], with_pads_price: null }];
  assert.equal(cartIssue([{ product_id: 9, quantity: 1 }], pieces),
    'A piece in your bag is no longer available. Remove it to continue.');
  assert.match(cartIssue([{ product_id: 1, quantity: 1, size: 'M', color: 'Red' }, { product_id: 1, quantity: 2, size: 'M', color: 'Red' }], pieces),
    /only 2 available/);
  assert.match(cartIssue([{ product_id: 1, quantity: 1, color: 'Red' }], pieces), /option that is no longer available/);
  assert.match(cartIssue([{ product_id: 1, quantity: 1, size: 'M' }], pieces), /option that is no longer available/);
  assert.match(cartIssue([{ product_id: 1, quantity: 1, size: 'XL' }], pieces), /option that is no longer available/);
  assert.match(cartIssue([{ product_id: 1, quantity: 1, size: 'M', color: 'Red', with_pads: true }], pieces), /option that is no longer available/);
  assert.equal(cartIssue([{ product_id: 1, quantity: 2, size: 'M', color: 'Red' }], pieces), null);
});
