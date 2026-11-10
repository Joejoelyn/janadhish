import type { CartItem, Measurements, Product, User } from './types';

export function readStorage<T>(key: string, fallback: T): T {
  try { return JSON.parse(localStorage.getItem(key) || '') as T; }
  catch { return fallback; }
}

export function readCart(): CartItem[] {
  const stored = readStorage<unknown>('janadhishCart', []);
  if (!Array.isArray(stored)) return [];
  const validMeasurements = (value: unknown): value is Measurements => {
    if (!value || typeof value !== 'object') return false;
    const data = value as Partial<Measurements>;
    return (data.unit === 'inches' || data.unit === 'cm')
      && Boolean(data.values) && typeof data.values === 'object'
      && Object.values(data.values).every(amount => typeof amount === 'number' && Number.isFinite(amount) && amount >= 0.1 && amount <= 300);
  };
  return stored.filter((item): item is CartItem =>
    item && typeof item === 'object'
    && Number.isInteger(item.product_id) && item.product_id > 0
    && Number.isInteger(item.quantity) && item.quantity > 0 && item.quantity <= 100
  ).map(item => ({
    product_id: item.product_id, quantity: item.quantity,
    size: typeof item.size === 'string' ? item.size : null,
    color: typeof item.color === 'string' ? item.color : null,
    with_pads: Boolean(item.with_pads),
    ...(validMeasurements(item.measurements) ? { measurements: item.measurements } : {}),
  }));
}

export function readWishlist(): number[] {
  const stored = readStorage<unknown>('janadhishWishlist', []);
  return Array.isArray(stored) ? [...new Set(stored.filter((id): id is number => Number.isInteger(id) && id > 0))] : [];
}

export const formatPrice = (value: number) => `₹${value.toLocaleString('en-IN')}`;
export const priceOf = (product: Product, withPads = false) =>
  withPads ? (product.with_pads_price ?? product.price) : (product.without_pads_price ?? product.sale_price ?? product.price);
export const shippingOf = (subtotal: number) => subtotal >= 3000 || subtotal === 0 ? 0 : 250;
export const getToken = () => sessionStorage.getItem('janadhishToken');
export const getUser = () => {
  try { return JSON.parse(sessionStorage.getItem('janadhishUser') || 'null') as User | null; }
  catch { return null; }
};
const notifySessionChange = () => {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event('janadhish-session-change'));
};
export function saveSession(token: string, user: User) {
  localStorage.removeItem('janadhishToken');
  localStorage.removeItem('janadhishUser');
  sessionStorage.setItem('janadhishToken', token);
  sessionStorage.setItem('janadhishUser', JSON.stringify(user));
  notifySessionChange();
}
export function clearSession() {
  localStorage.removeItem('janadhishToken');
  localStorage.removeItem('janadhishUser');
  sessionStorage.removeItem('janadhishToken');
  sessionStorage.removeItem('janadhishUser');
  notifySessionChange();
}
export function cartKey(item: CartItem) {
  return JSON.stringify([item.product_id, item.size, item.color, item.with_pads, item.measurements || null]);
}

export function cartIssue(cart: CartItem[], products: Product[]): string | null {
  const quantities = new Map<number, number>();
  for (const item of cart) {
    const product = products.find(value => value.id === item.product_id);
    if (!product) return 'A piece in your bag is no longer available. Remove it to continue.';
    if (((product.sizes.length > 0 || item.size) && !product.sizes.includes(item.size || ''))
      || ((product.colors.length > 0 || item.color) && !product.colors.includes(item.color || ''))
      || (item.with_pads && product.with_pads_price == null)) {
      return `${product.name} has an option that is no longer available. Choose an available option on its product page and remove this line.`;
    }
    quantities.set(item.product_id, (quantities.get(item.product_id) || 0) + item.quantity);
  }
  for (const [id, quantity] of quantities) {
    const product = products.find(value => value.id === id);
    if (product && quantity > product.stock_quantity) return `${product.name} has only ${product.stock_quantity} available. Reduce or remove it to continue.`;
  }
  return null;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  const hasExplicitAuthorization = headers.has('Authorization');
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (token && !hasExplicitAuthorization) headers.set('Authorization', `Bearer ${token}`);
  let response = await fetch(path, { ...options, headers });
  let retriedAsGuest = false;
  if (response.status === 401 && token && !hasExplicitAuthorization && ['/api/orders', '/api/customizations'].includes(path)) {
    clearSession();
    headers.delete('Authorization');
    retriedAsGuest = true;
    response = await fetch(path, { ...options, headers });
  }
  let data: unknown;
  try { data = await response.json(); }
  catch { throw new Error('The store is temporarily unavailable. Please try again.'); }
  if (!response.ok) {
    if (response.status === 403 && path.startsWith('/api/admin/') && getUser()?.is_admin) {
      clearSession();
      throw new Error('Your admin access changed. Sign in again.');
    }
    if (response.status === 401 && token && !retriedAsGuest && !path.startsWith('/api/auth/')) {
      clearSession();
      throw new Error('Your sign-in expired. Sign in again or retry as a guest.');
    }
    const raw = typeof data === 'object' && data !== null && 'detail' in data ? data.detail : null;
    const detail = typeof raw === 'string' ? raw : Array.isArray(raw) && raw[0]?.msg ? String(raw[0].msg) : 'Request failed. Please try again.';
    throw new ApiError(detail, response.status);
  }
  return data as T;
}
