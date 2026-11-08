import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { AdminAccess, Banner } from './Layout';
import { formIssue } from './formValidation';
import { api, formatPrice, getUser } from './lib';

type Fulfillment = {
  status: 'processing' | 'packed' | 'shipped' | 'delivered';
  carrier: string | null; tracking_reference: string | null; version: number;
};
type ItemDetails = {
  with_pads?: boolean;
  measurements?: { unit?: string; values?: Record<string, number>; notes?: string } | null;
} | string | null;
type PaidOrderItem = {
  name: string; quantity: number; size: string | null; color: string | null;
  customization_details: ItemDetails;
};
type PaidOrder = {
  order_id: number; customer_name: string; email: string; phone: string | null;
  shipping_address: string; city: string; state: string; postal_code: string; country: string;
  shipping_method: string; total: number; created_at: string;
  refunded_amount_paise: number;
  items: PaidOrderItem[];
  fulfillment: Fulfillment;
};
type FulfillmentPage = { items: PaidOrder[]; has_more: boolean };

function OrderItems({ items }: { items: PaidOrderItem[] }) {
  return <ul className="admin-order-items">{items.map((item, index) => {
    const details = item.customization_details;
    const fit = details && typeof details === 'object' ? details : null;
    const measurements = fit?.measurements;
    const values = measurements?.values ? Object.entries(measurements.values) : [];
    const finish = fit ? (fit.with_pads ? 'With pads' : 'Without pads') : null;
    return <li key={index}><strong>{item.name} × {item.quantity}</strong><span>{[item.size, item.color, finish].filter(Boolean).join(' · ')}</span>{values.length > 0 && <details><summary>Measurements</summary><dl>{values.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value} {measurements?.unit === 'cm' ? 'cm' : 'in'}</dd></div>)}</dl></details>}{measurements?.notes && <p>Fit notes: {measurements.notes}</p>}{typeof details === 'string' && <p>Fit notes: {details}</p>}</li>;
  })}</ul>;
}

export function AdminFulfillment() {
  const isAdmin = getUser()?.is_admin;
  const [orders, setOrders] = useState<PaidOrder[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState('');
  const [errorOrderId, setErrorOrderId] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<'open' | 'delivered'>('open');
  const requestId = useRef(0);
  const selectView = (next: 'open' | 'delivered') => {
    if (next === view) return;
    requestId.current += 1;
    setOrders([]); setHasMore(false); setError(''); setErrorOrderId(null); setView(next);
  };
  const load = async (offset = 0, selectedView = view) => {
    const id = ++requestId.current;
    setLoading(true); setError(''); setErrorOrderId(null);
    try {
      const page = await api<FulfillmentPage>(`/api/admin/fulfillment?view=${selectedView}&offset=${offset}`);
      if (id !== requestId.current) return;
      setOrders(current => offset ? [...current, ...page.items] : page.items);
      setHasMore(page.has_more);
    } catch (reason) { if (id === requestId.current) setError(reason instanceof Error ? reason.message : 'Could not load paid orders'); }
    finally { if (id === requestId.current) setLoading(false); }
  };
  useEffect(() => { if (isAdmin) void load(0, view); }, [isAdmin, view]);
  const advance = async (event: FormEvent<HTMLFormElement>, order: PaidOrder) => {
    event.preventDefault();
    const issue = formIssue(event.currentTarget);
    if (issue) { setErrorOrderId(order.order_id); setError(issue); return; }
    const next = order.fulfillment.status === 'processing' ? 'packed' : order.fulfillment.status === 'packed' ? 'shipped' : 'delivered';
    const form = new FormData(event.currentTarget);
    setBusy(order.order_id); setError(''); setErrorOrderId(null);
    try {
      const fulfillment = await api<Fulfillment>(`/api/admin/fulfillment/${order.order_id}`, {
        method: 'POST', body: JSON.stringify({
          status: next, expected_version: order.fulfillment.version,
          carrier: next === 'shipped' ? String(form.get('carrier') || '').trim() : null,
          tracking_reference: next === 'shipped' ? String(form.get('tracking_reference') || '').trim() : null,
        }),
      });
      if (next === 'delivered') await load(0, 'open');
      else setOrders(current => current.map(item => item.order_id === order.order_id ? { ...item, fulfillment } : item));
    } catch (reason) { setErrorOrderId(order.order_id); setError(reason instanceof Error ? reason.message : 'Could not update fulfilment'); }
    finally { setBusy(null); }
  };
  if (!isAdmin) return <AdminAccess purpose="manage fulfilment" />;
  return <main><Banner eyebrow="Store operations" title="Paid orders & delivery" description="Prepare and ship only after payment verification. Record the actual carrier and tracking reference when dispatching." /><section className="section"><div className="container admin-fulfillment"><div className="admin-queue-tabs" role="group" aria-label="Paid order view"><button type="button" disabled={busy !== null} aria-pressed={view === "open"} onClick={() => selectView("open")}>Open orders</button><button type="button" disabled={busy !== null} aria-pressed={view === "delivered"} onClick={() => selectView("delivered")}>Delivered history</button></div><button type="button" className="button button-outline" disabled={loading} onClick={() => void load()}>Refresh orders</button>{error && errorOrderId === null && <p className="notice error" role="alert">{error}</p>}{orders.map(order => <article className="checkout-form" key={order.order_id}><div className="admin-order-heading"><h2>Order #{order.order_id} · {formatPrice(order.total)}</h2><strong>{order.fulfillment.status.replaceAll('_', ' ')}</strong></div><p>Placed {new Date(order.created_at).toLocaleDateString('en-IN')} · {order.shipping_method} delivery</p>{order.refunded_amount_paise > 0 && <p className="notice">Recorded refund: {formatPrice(order.refunded_amount_paise / 100)} of {formatPrice(order.total)}.</p>}<h3>Ship to</h3><address>{order.customer_name}<br />{order.shipping_address}<br />{order.city}, {order.state} {order.postal_code}<br />{order.country}</address><p>{order.email}{order.phone ? ` · ${order.phone}` : ''}</p><h3>Items</h3><OrderItems items={order.items} />{order.fulfillment.tracking_reference && <p>Carrier: <strong>{order.fulfillment.carrier}</strong> · Tracking: <strong>{order.fulfillment.tracking_reference}</strong></p>}{order.refunded_amount_paise >= Math.round(order.total * 100) && ['processing', 'packed'].includes(order.fulfillment.status) ? <p className="notice">Fully refunded. Packing and shipping are unavailable.</p> : order.fulfillment.status !== 'delivered' && <form noValidate onSubmit={event => void advance(event, order)}>{order.fulfillment.status === 'packed' && <><label>Carrier<input name="carrier" required minLength={2} maxLength={100} autoComplete="off" /></label><label>Tracking reference<input name="tracking_reference" required minLength={2} maxLength={100} autoComplete="off" /></label></>}<button className="button button-primary" disabled={busy === order.order_id}>{busy === order.order_id ? 'Saving…' : order.fulfillment.status === 'processing' ? 'Mark packed' : order.fulfillment.status === 'packed' ? 'Mark shipped' : 'Mark delivered'}</button></form>}{errorOrderId === order.order_id && <p className="notice error" role="alert">{error}</p>}</article>)}{!orders.length && !loading && !error && <p>{view === "open" ? "No paid orders waiting for fulfilment." : "No delivered orders yet."}</p>}{hasMore && <button type="button" className="button button-outline" disabled={loading} onClick={() => void load(orders.length)}>{loading ? 'Loading…' : 'Load more orders'}</button>}</div></section></main>;
}
