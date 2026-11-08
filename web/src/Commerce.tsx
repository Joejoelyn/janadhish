import { useEffect, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router';
import { AlertCircle, Check, Copy, Minus, Plus } from 'lucide-react';
import { AdminAccess, Banner } from './Layout';
import { ThemeSelect } from './ThemeSelect';
import { indianRegions } from './locations';
import { formIssue } from './formValidation';
import { ApiError, api, cartIssue, clearSession, formatPrice, getToken, getUser, priceOf, saveSession, shippingOf } from './lib';
import type { CartItem, Order, Product, User } from './types';

type CheckoutReceipt = {
  order_id: number; total: number; status: string; payment_method: 'upi_qr'; checkout_token: string;
  payment_reference: string | null; review_note: string | null;
  refunded_amount_paise: number;
  refunds: { id: number; amount_paise: number; outgoing_reference: string; reason: string; created_at: string }[];
  fulfillment?: { status: string; carrier: string | null; tracking_reference: string | null } | null;
  upi: { qr_image_url: string; payee_name: string };
};

type PaymentLink = { order_id: number; checkout_token: string };

function paymentLink(token: string): string {
  return `/checkout#payment=${encodeURIComponent(token)}`;
}

function readPaymentLinks(): PaymentLink[] {
  try {
    const stored: unknown = JSON.parse(sessionStorage.getItem('janadhishPaymentLinks') || '[]');
    return Array.isArray(stored) ? stored.filter((item): item is PaymentLink =>
      typeof item?.order_id === 'number' && typeof item?.checkout_token === 'string') : [];
  } catch { return []; }
}

function rememberPayment(receipt: CheckoutReceipt): void {
  const links = readPaymentLinks().filter(item => item.checkout_token !== receipt.checkout_token);
  sessionStorage.setItem('janadhishPaymentLinks', JSON.stringify([{ order_id: receipt.order_id, checkout_token: receipt.checkout_token }, ...links].slice(0, 5)));
}

function CheckoutConflict({ orderId, onView, onStartNew }: { orderId: number; onView: () => void; onStartNew: () => void }) {
  return <div className="checkout-conflict" role="alert">
    <h3>Earlier order found</h3>
    <p>Order #{orderId} already used this checkout reference. The details you just entered were not applied to it. Your current bag is still saved.</p>
    <div className="checkout-conflict-actions">
      <button type="button" className="button button-primary" onClick={onView}>View order #{orderId}</button>
      <button type="button" className="button button-outline" onClick={onStartNew}>Start a separate order</button>
    </div>
  </div>;
}

function CancelPaymentDialog({ orderId, busy, error, onClose, onConfirm }: {
  orderId: number; busy: boolean; error: string; onClose: () => void; onConfirm: () => void;
}) {
  const [confirmed, setConfirmed] = useState(false);
  const confirmationBox = useRef<HTMLInputElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const confirmButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    cancelButton.current?.focus();
    return () => previous?.focus();
  }, []);
  const handleKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape' && !busy) { event.preventDefault(); onClose(); }
    if (event.key !== 'Tab') return;
    if (event.shiftKey && document.activeElement === confirmationBox.current) {
      event.preventDefault(); confirmButton.current?.focus();
    } else if (!event.shiftKey && document.activeElement === confirmButton.current) {
      event.preventDefault(); confirmationBox.current?.focus();
    }
  };
  return <div className="dialog-backdrop" onKeyDown={handleKey}>
    <section className="payment-dialog" role="alertdialog" aria-modal="true" aria-labelledby="cancel-payment-title" aria-describedby="cancel-payment-description">
      <AlertCircle size={26} aria-hidden="true" />
      <h2 id="cancel-payment-title">Request cancellation for order #{orderId}?</h2>
      <p id="cancel-payment-description">We will check the receiving account before cancelling and releasing this order. If you already paid, keep it open and submit your transaction reference.</p>
      <label className="confirm-check"><input ref={confirmationBox} type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span className="confirm-check-box"><Check size={15} aria-hidden="true" /></span><span>I have not sent a payment for this order.</span></label>
      {error && <p className="notice error" role="alert">{error}</p>}
      <div className="payment-dialog-actions"><button ref={cancelButton} type="button" className="button button-outline" onClick={onClose} disabled={busy}>Keep order</button><button ref={confirmButton} type="button" className="button button-primary" onClick={() => { if (confirmed && !busy) onConfirm(); }} aria-disabled={busy || !confirmed}>{busy ? 'Requesting…' : 'Request cancellation'}</button></div>
    </section>
  </div>;
}

function PaymentReferenceForm({ busy, error, cancellationRequested, onSubmit }: {
  busy: boolean; error: string; cancellationRequested: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return <form noValidate onSubmit={onSubmit}><h3>{cancellationRequested ? 'Already paid?' : 'After paying'}</h3><p>{cancellationRequested
    ? 'If you paid before requesting cancellation, enter your UPI transaction reference so we can review it. A screenshot alone is not accepted as proof of payment.'
    : 'Find the UPI transaction reference or UTR in your payment app and enter it here. A screenshot alone is not accepted as proof of payment.'}</p><label>Transaction reference / UTR<input name="reference" required minLength={8} maxLength={60} pattern="[A-Za-z0-9-]+" title="Use 8–60 letters, numbers or hyphens" autoComplete="off" /></label><label>Name shown on payment<input name="payer_name" required minLength={2} maxLength={150} /></label>{error && <p className="notice error" role="alert">{error}</p>}<button className="button button-primary full-width" type="submit" disabled={busy}>{busy ? 'Submitting…' : 'Submit payment reference'}</button></form>;
}

function CartRows({ products, cart, changeQuantity, removeItem }: { products: Product[]; cart: CartItem[]; changeQuantity: (index: number, delta: number) => void; removeItem: (index: number) => void }) {
  return <div className="cart-items">{cart.map((item, index) => {
    const product = products.find(value => value.id === item.product_id);
    if (!product) return <div key={index} className="cart-item"><p>Product {item.product_id} is unavailable. Please remove it.</p><button type="button" className="remove-link" onClick={() => removeItem(index)}>Remove</button></div>;
    return <article className="cart-item" key={index}><Link to={`/product/${product.id}`}><img src={product.image_url || ''} alt={product.name} /></Link><div className="cart-item-info"><p className="eyebrow">{product.category?.name}</p><h2><Link to={`/product/${product.id}`}>{product.name}</Link></h2><p>{item.size || 'Standard'} · {item.color || 'As pictured'} · {item.with_pads ? 'With pads' : 'Without pads'}</p>{item.measurements && <details><summary>Measurements added</summary><p>{Object.entries(item.measurements.values).map(([label, value]) => `${label}: ${value} ${item.measurements?.unit === 'cm' ? 'cm' : 'in'}`).join(' · ')}</p></details>}<div className="cart-qty"><button type="button" aria-label={`Decrease ${product.name} quantity`} onClick={() => changeQuantity(index, -1)}><Minus size={16} aria-hidden="true" /></button><span>{item.quantity}</span><button type="button" aria-label={`Increase ${product.name} quantity`} disabled={item.quantity >= 100 || cart.filter(value => value.product_id === product.id).reduce((total, value) => total + value.quantity, 0) >= product.stock_quantity} onClick={() => changeQuantity(index, 1)}><Plus size={16} aria-hidden="true" /></button></div><button type="button" className="remove-link" onClick={() => removeItem(index)}>Remove</button></div><strong>{formatPrice(priceOf(product, Boolean(item.with_pads)) * item.quantity)}</strong></article>;
  })}</div>;
}

function Totals({ subtotal }: { subtotal: number }) {
  const shipping = shippingOf(subtotal);
  return <div className="totals"><div><span>Subtotal</span><strong>{formatPrice(subtotal)}</strong></div><div><span>Shipping</span><strong>{shipping ? formatPrice(shipping) : 'Complimentary'}</strong></div><div className="total"><span>Total</span><strong>{formatPrice(subtotal + shipping)}</strong></div><p>Final prices are confirmed when you place the order.</p></div>;
}

export function CartPage({ products, cart, loading, catalogError, refreshProducts, changeQuantity, removeItem }: { products: Product[]; cart: CartItem[]; loading: boolean; catalogError: string; refreshProducts: () => Promise<void>; changeQuantity: (index: number, delta: number) => void; removeItem: (index: number) => void }) {
  const paymentLinks = readPaymentLinks();
  const issue = !loading && !catalogError ? cartIssue(cart, products) : null;
  const subtotal = cart.reduce((total, item) => {
    const product = products.find(value => value.id === item.product_id);
    return total + (product ? priceOf(product, Boolean(item.with_pads)) * item.quantity : 0);
  }, 0);
  return <main><Banner eyebrow="Your bag" title="Your selected pieces" description="Review your pieces and fit details before checkout." /><section className="section"><div className="container cart-layout">{loading ? <div className="empty-state" role="status">Loading your bag…</div> : catalogError ? <div className="empty-state"><h2>Could not load the collection</h2><p>Your bag is saved. Retry to check current prices and availability.</p><button type="button" className="button button-outline" onClick={() => void refreshProducts()}>Retry collection</button></div> : cart.length ? <CartRows products={products} cart={cart} changeQuantity={changeQuantity} removeItem={removeItem} /> : <div className="empty-state"><h2>Your bag is waiting</h2><p>Explore the collection and find a piece you love.</p><Link to="/shop" className="button button-primary">Shop the collection</Link></div>}<aside className="summary-card"><h2>Order summary</h2>{!loading && !catalogError && <Totals subtotal={subtotal} />}{issue && <p className="notice error" role="alert">{issue}</p>}{cart.length > 0 && !loading && !catalogError && !issue && <Link to="/checkout?new=1" className="button button-primary full-width">Proceed to checkout ↗</Link>}{paymentLinks.length > 0 && <div className="previous-orders"><h3>Recent payment links</h3><p>Keep these links private. They can submit payment references for your orders.</p>{paymentLinks.map(item => <Link key={item.checkout_token} to={paymentLink(item.checkout_token)}>Return to order #{item.order_id} ↗</Link>)}</div>}</aside></div></section></main>;
}

export function Checkout({ products, cart, loading, catalogError, clearCart, refreshProducts }: { products: Product[]; cart: CartItem[]; loading: boolean; catalogError: string; clearCart: () => void; refreshProducts: () => Promise<void> }) {
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const legacyPaymentToken = params.get('payment');
  const paymentToken = new URLSearchParams(location.hash.slice(1)).get('payment') || legacyPaymentToken;
  const newOrder = params.get('new') === '1';
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [linkCopyStatus, setLinkCopyStatus] = useState('');
  const [recovering, setRecovering] = useState(Boolean(paymentToken));
  const [statusUnavailable, setStatusUnavailable] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [region, setRegion] = useState('');
  const [regionInvalid, setRegionInvalid] = useState(false);
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [existingOrder, setExistingOrder] = useState<CheckoutReceipt | null>(null);
  const [pending, setPending] = useState<CheckoutReceipt | null>(() => {
    try { return JSON.parse(sessionStorage.getItem('janadhishPendingPayment') || 'null') as CheckoutReceipt | null; }
    catch { return null; }
  });
  useEffect(() => { setLinkCopyStatus(''); }, [pending?.checkout_token]);
  useEffect(() => {
    if (legacyPaymentToken && paymentToken) navigate(paymentLink(paymentToken), { replace: true });
    else if (!paymentToken && pending && !newOrder) navigate(paymentLink(pending.checkout_token), { replace: true });
  }, [legacyPaymentToken, location.hash, paymentToken, pending?.checkout_token, newOrder, navigate]);
  useEffect(() => {
    if (!paymentToken) return;
    let active = true;
    setRecovering(true); setStatusUnavailable(false);
    api<CheckoutReceipt>('/api/payments/status', { method: 'POST', body: JSON.stringify({ checkout_token: paymentToken }) })
      .then(status => { if (active) { sessionStorage.setItem('janadhishPendingPayment', JSON.stringify(status)); rememberPayment(status); setPending(status); } })
      .catch(reason => {
        if (!active) return;
        if (reason instanceof ApiError && reason.status === 404) {
          sessionStorage.removeItem('janadhishPendingPayment');
          sessionStorage.removeItem('janadhishCheckoutKey');
          setPending(null);
          setError('The previous order link is unavailable. You can start a new order.');
          setRecovering(false);
          navigate('/checkout', { replace: true });
        } else {
          setStatusUnavailable(true);
          setError(reason instanceof Error ? reason.message : 'Could not check this order');
        }
      })
      .finally(() => { if (active) setRecovering(false); });
    return () => { active = false; };
  }, [paymentToken, retryCount, navigate]);
  useEffect(() => { if (pending) window.scrollTo(0, 0); }, [pending?.order_id, pending?.status]);
  const user = getUser();
  const subtotal = cart.reduce((total, item) => {
    const product = products.find(value => value.id === item.product_id);
    return total + (product ? priceOf(product, Boolean(item.with_pads)) * item.quantity : 0);
  }, 0);
  const checkPayment = async (data: CheckoutReceipt) => {
    setBusy(true); setError('');
    try {
      const status = await api<CheckoutReceipt>('/api/payments/status', { method: 'POST', body: JSON.stringify({ checkout_token: data.checkout_token }) });
      sessionStorage.setItem('janadhishPendingPayment', JSON.stringify(status));
      rememberPayment(status);
      setPending(status);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not check payment status'); }
    finally { setBusy(false); }
  };
  const copyOrderLink = async (receipt: CheckoutReceipt) => {
    const link = new URL(paymentLink(receipt.checkout_token), window.location.origin);
    try {
      await navigator.clipboard.writeText(link.toString());
      setLinkCopyStatus('Private order link copied. Keep it somewhere safe.');
    } catch {
      setLinkCopyStatus('Copy unavailable. Save this page from your browser address bar.');
    }
  };
  const submitReference = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!pending) return;
    const issue = formIssue(event.currentTarget);
    if (issue) { setError(issue); return; }
    setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try {
      const status = await api<CheckoutReceipt>('/api/payments/submit', { method: 'POST', body: JSON.stringify({
        checkout_token: pending.checkout_token, reference: String(form.get('reference') || '').trim(), payer_name: String(form.get('payer_name') || '').trim(),
      }) });
      sessionStorage.setItem('janadhishPendingPayment', JSON.stringify(status));
      setPending(status);
      sessionStorage.removeItem('janadhishCheckoutKey');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not submit payment reference'); }
    finally { setBusy(false); }
  };
  const cancelOrder = async () => {
    if (!pending) return;
    setBusy(true); setError('');
    try {
      const cancelled = await api<CheckoutReceipt>('/api/payments/cancel', { method: 'POST', body: JSON.stringify({ checkout_token: pending.checkout_token }) });
      sessionStorage.setItem('janadhishPendingPayment', JSON.stringify(cancelled));
      sessionStorage.removeItem('janadhishCheckoutKey');
      setPending(cancelled);
      setShowCancelDialog(false);
      void refreshProducts();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not request cancellation'); }
    finally { setBusy(false); }
  };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!cart.length || existingOrder) return;
    const issue = formIssue(event.currentTarget);
    if (issue) { setError(issue); return; }
    setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    const field = (name: string) => String(form.get(name) || '').trim();
    if (!region) { setRegionInvalid(true); setError('Choose your state or union territory.'); setBusy(false); return; }
    if (!/^[1-9][0-9]{5}$/.test(field('postal_code'))) { setError('Enter a valid six-digit Indian PIN code.'); setBusy(false); return; }
    let checkoutKey = '';
    try {
      checkoutKey = sessionStorage.getItem('janadhishCheckoutKey') || crypto.randomUUID();
      sessionStorage.setItem('janadhishCheckoutKey', checkoutKey);
      const data = await api<CheckoutReceipt>('/api/orders', { method: 'POST', body: JSON.stringify({
        customer_name: field('customer_name'), email: field('email'), phone: field('phone'),
        shipping_address: field('shipping_address'), city: field('city'), state: field('state'),
        postal_code: field('postal_code'), country: field('country'),
        shipping_method: field('shipping_method'), payment_method: field('payment_method'), checkout_key: checkoutKey,
        cart_items: cart.map(item => ({ product_id: item.product_id, quantity: item.quantity,
          size: item.size, color: item.color, with_pads: Boolean(item.with_pads),
          customization_details: item.measurements || null })),
      }) });
      sessionStorage.setItem('janadhishPendingPayment', JSON.stringify(data));
      rememberPayment(data);
      sessionStorage.removeItem('janadhishCheckoutKey');
      setPending(data);
      navigate(paymentLink(data.checkout_token), { replace: true });
      clearCart();
      void refreshProducts();
    } catch (reason) {
      if (checkoutKey && reason instanceof ApiError && reason.status === 409 && reason.message === 'Checkout reference was already used for a different order') {
        try {
          const recovered = await api<CheckoutReceipt>('/api/orders/recover', {
            method: 'POST', body: JSON.stringify({ checkout_key: checkoutKey }),
          });
          rememberPayment(recovered);
          setExistingOrder(recovered);
          setError('');
        } catch {
          setError('An earlier order may exist, but we could not retrieve it. Retry before placing another order or contact us.');
        }
      } else setError(reason instanceof Error ? reason.message : 'Could not place order');
    }
    finally { setBusy(false); }
  };
  const viewExistingOrder = () => {
    if (!existingOrder) return;
    sessionStorage.setItem('janadhishPendingPayment', JSON.stringify(existingOrder));
    rememberPayment(existingOrder);
    sessionStorage.removeItem('janadhishCheckoutKey');
    setPending(existingOrder);
    setExistingOrder(null);
    navigate(paymentLink(existingOrder.checkout_token), { replace: true });
  };
  const startNewOrder = () => {
    sessionStorage.removeItem('janadhishCheckoutKey');
    setExistingOrder(null);
    setError('');
  };
  if (recovering) return <main className="simple-page"><p role="status">Loading your payment status…</p></main>;
  if (statusUnavailable) return <main className="simple-page"><h1>Payment status unavailable</h1><p role="alert">{error}</p><p>Keep this private page link. Your order has not been changed.</p><button type="button" className="button button-primary" onClick={() => setRetryCount(count => count + 1)}>Retry status check</button></main>;
  if (paymentToken && !pending) return <main className="simple-page"><h1>Order link unavailable</h1><p role="alert">{error || 'This payment link could not be opened.'}</p><Link to="/shop" className="button button-primary">Shop the collection</Link></main>;
  if (pending && !newOrder) return <main>{showCancelDialog && <CancelPaymentDialog orderId={pending.order_id} busy={busy} error={error} onClose={() => setShowCancelDialog(false)} onConfirm={() => void cancelOrder()} />}<Banner eyebrow={`Order #${pending.order_id}`} title={pending.status === 'paid' ? 'Payment verified' : pending.status === 'payment_submitted' ? 'Payment under review' : pending.status === 'cancelled' ? 'Order cancelled' : pending.status === 'cancellation_requested' ? 'Cancellation requested' : 'Pay with UPI'} description="We confirm each QR payment against the receiving account before processing an order." /><section className="section"><div className="container payment-layout"><div className="checkout-form">
    {pending.status !== 'cancelled' && <p className="form-note">Keep this page link to return to order #{pending.order_id}. The link can submit a payment reference or request cancellation, so keep it private.</p>}
    {pending.status !== 'cancelled' && <div className="payment-link-tools"><button type="button" className="button button-outline" onClick={() => void copyOrderLink(pending)}><Copy size={16} aria-hidden="true" /> Copy private order link</button>{linkCopyStatus && <p role="status">{linkCopyStatus}</p>}</div>}
    {pending.status === 'awaiting_payment' && <p className="payment-mobile-help">Paying on this phone? <a href={pending.upi.qr_image_url} download="janadhish-upi.jpeg">Save the QR image</a>, then open it from your UPI app's scanner or gallery.</p>}
    {pending.status === 'awaiting_payment' && <><h2>Scan and pay</h2><p>Pay exactly <strong>{formatPrice(pending.total)}</strong> to <strong>{pending.upi.payee_name}</strong> using any UPI app. Include order #{pending.order_id} in the note if your app allows it.</p><img className="payment-qr" src={pending.upi.qr_image_url} alt={`UPI payment QR code for ${pending.upi.payee_name}`} /><p className="form-note">Check the recipient name and amount in your UPI app before paying. This QR does not fill the order amount automatically.</p>{pending.review_note && <p className="notice error" role="alert">Previous reference was rejected: {pending.review_note}</p>}<PaymentReferenceForm busy={busy} error={showCancelDialog ? '' : error} cancellationRequested={false} onSubmit={submitReference} /><button type="button" className="remove-link" onClick={() => { setError(''); setShowCancelDialog(true); }} disabled={busy}>Request cancellation</button></>}
    {pending.status === 'cancellation_requested' && <><h2>Cancellation requested</h2><p>Do not send a new payment. Your order remains reserved while we check the receiving account. If you already paid, submit the transaction reference below.</p><PaymentReferenceForm busy={busy} error={error} cancellationRequested onSubmit={submitReference} /></>}
    {pending.status === 'payment_submitted' && <><span className="success-mark">✓</span><h2>Reference received</h2><p>Order #{pending.order_id} · {formatPrice(pending.total)} · Reference <strong>{pending.payment_reference}</strong></p><p>Payment is awaiting a bank statement check. Your order is not yet confirmed for fulfilment.</p><button type="button" className="button button-outline" onClick={() => checkPayment(pending)} disabled={busy}>{busy ? 'Checking…' : 'Check verification status'}</button>{error && <p className="notice error" role="alert">{error}</p>}</>}
    {pending.status === 'paid' && <>
      <span className="success-mark">✓</span><h2>Thank you for shopping with us.</h2>
      <p>Payment for order #{pending.order_id} has been verified.</p>
      {pending.refunded_amount_paise > 0 && <div className="notice"><strong>{pending.refunded_amount_paise >= Math.round(pending.total * 100) ? 'Full refund recorded' : 'Partial refund recorded'}:</strong> {formatPrice(pending.refunded_amount_paise / 100)}.{pending.refunds.map(item => <p key={item.id}>{formatPrice(item.amount_paise / 100)} · Reference {item.outgoing_reference}</p>)}</div>}
      <p>Delivery: <strong>{pending.fulfillment?.status || 'processing'}</strong>{pending.fulfillment?.tracking_reference && <> · {pending.fulfillment.carrier}: {pending.fulfillment.tracking_reference}</>}</p>
      <button type="button" className="button button-outline" onClick={() => checkPayment(pending)} disabled={busy}>{busy ? 'Checking…' : 'Check delivery status'}</button>
      <Link to="/shop" className="button button-primary" onClick={() => { sessionStorage.removeItem('janadhishPendingPayment'); sessionStorage.removeItem('janadhishCheckoutKey'); }}>Continue shopping</Link>
      {user && <Link to="/account?section=orders" className="button button-outline">View orders</Link>}
    </>}
    {pending.status === 'cancelled' && <><h2>This order was cancelled</h2><Link to="/shop" className="button button-primary" onClick={() => { sessionStorage.removeItem('janadhishPendingPayment'); sessionStorage.removeItem('janadhishCheckoutKey'); }}>Shop again</Link></>}
  </div><aside className="summary-card"><h2>Order summary</h2><p>Order #{pending.order_id}</p><div className="total"><span>Total</span><strong>{formatPrice(pending.total)}</strong></div><p>UPI QR payment</p></aside></div></section></main>;
  if (!cart.length) return <main className="simple-page"><h1>Your bag is empty</h1>{error && <p className="notice error" role="alert">{error}</p>}<p>Add a piece before checking out.</p><Link to="/shop" className="button button-primary">Shop the collection</Link></main>;
  if (loading) return <main className="simple-page"><p role="status">Checking current prices and availability…</p></main>;
  if (catalogError) return <main className="simple-page"><h1>Collection unavailable</h1><p>Your bag is saved. Retry before placing an order.</p><button type="button" className="button button-primary" onClick={() => void refreshProducts()}>Retry collection</button><Link to="/cart" className="button button-outline">View bag</Link></main>;
  const issue = cartIssue(cart, products);
  if (issue) return <main className="simple-page"><h1>Check your bag</h1><p role="alert">{issue}</p><Link to="/cart" className="button button-primary">Update bag</Link></main>;
  return <main><Banner eyebrow="Almost yours" title="Checkout" description="Complete your details, then scan the UPI QR to pay." /><section className="section"><div className="container checkout-layout"><form className="checkout-form" noValidate onSubmit={submit}>{existingOrder && <CheckoutConflict orderId={existingOrder.order_id} onView={viewExistingOrder} onStartNew={startNewOrder} />}<h2>Shipping details</h2><div className="field-grid"><label>Full name<input name="customer_name" defaultValue={user?.full_name || ''} required minLength={2} maxLength={150} autoComplete="name" /></label><label>Email<input name="email" type="email" defaultValue={user?.email || ''} required autoComplete="email" /></label><label>Phone<input name="phone" type="tel" defaultValue={user?.phone || ''} maxLength={50} inputMode="tel" autoComplete="tel" /></label><ThemeSelect label="Country" name="country" value="India" options={[{ value: 'India', label: 'India' }]} /><label className="wide">Shipping address<input name="shipping_address" required minLength={5} maxLength={500} autoComplete="street-address" /></label><label>City<input name="city" required minLength={2} maxLength={100} autoComplete="address-level2" /></label><ThemeSelect label="State / UT" name="state" value={region} invalid={regionInvalid} onChange={value => { setRegion(value); setRegionInvalid(false); }} options={[{ value: '', label: 'Choose state or UT' }, ...indianRegions.map(item => ({ value: item, label: item }))]} /><label>PIN code<input name="postal_code" required inputMode="numeric" pattern="[1-9][0-9]{5}" maxLength={6} title="Enter a six-digit Indian PIN code" autoComplete="postal-code" /></label></div><h2>Delivery</h2><p className="form-note">We currently ship within India.</p><div className="radio-options"><label><input type="radio" name="shipping_method" value="standard" defaultChecked /> Standard delivery</label><label><input type="radio" name="shipping_method" value="express" /> Express request</label></div><p className="form-note">Express is a request, subject to availability. The displayed total is the full amount to pay now; we will contact you before any additional charge.</p><h2>Payment</h2><p>UPI QR payment is the only payment method currently offered. After paying, submit your transaction reference for verification.</p><input type="hidden" name="payment_method" value="upi_qr" />{error && <p className="notice error" role="alert">{error}</p>}<button type="submit" className="button button-primary full-width" disabled={busy || Boolean(existingOrder)}>{busy ? 'Preparing order…' : 'Continue to UPI QR'}</button></form><aside className="summary-card checkout-summary"><h2>Your order</h2>{cart.map((item, index) => { const product = products.find(value => value.id === item.product_id); return <div className="checkout-line" key={index}><span>{product?.name || 'Product'} × {item.quantity}<small>{item.size} · {item.with_pads ? 'With pads' : 'Without pads'}</small></span><strong>{product ? formatPrice(priceOf(product, Boolean(item.with_pads)) * item.quantity) : '—'}</strong></div>; })}<Totals subtotal={subtotal} /></aside></div></section></main>;
}

type SessionResponse = { access_token: string; user: User };

function AuthForm({ register }: { register: boolean }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const destination = params.get('returnTo');
  const adminDestination = ['/admin/payments', '/admin/fulfillment', '/admin/inbox', '/admin/catalog'].includes(destination || '') ? destination : null;
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const issue = formIssue(event.currentTarget);
    if (issue) { setError(issue); return; }
    const form = new FormData(event.currentTarget);
    if (register && new TextEncoder().encode(String(form.get('password') || '')).length > 72) {
      setError('Password is too long. Use at most 72 UTF-8 bytes.');
      return;
    }
    setBusy(true); setError('');
    const body = register ? { full_name: form.get('full_name'), email: form.get('email'), phone: form.get('phone'), password: form.get('password') } : { email: form.get('email'), password: form.get('password') };
    try { const data = await api<SessionResponse>(`/api/auth/${register ? 'register' : 'login'}`, { method: 'POST', body: JSON.stringify(body) }); saveSession(data.access_token, data.user); navigate(data.user.is_admin && adminDestination ? adminDestination : '/account'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Authentication failed'); }
    finally { setBusy(false); }
  };
  return <main className="auth-page"><div className="auth-card"><p className="eyebrow">Your JANADHISH account</p><h1>{register ? 'Join our story' : 'Welcome back'}</h1><form noValidate onSubmit={submit}>{register && <><label>Full name<input name="full_name" required minLength={2} maxLength={150} autoComplete="name" /></label><label>Phone<input name="phone" type="tel" maxLength={50} autoComplete="tel" /></label></>}<label>Email<input name="email" type="email" required autoComplete="email" /></label><label>Password<input name="password" type="password" required minLength={8} autoComplete={register ? 'new-password' : 'current-password'} /></label>{error && <p className="notice error" role="alert">{error}</p>}<button className="button button-primary full-width" type="submit" disabled={busy}>{busy ? 'Please wait…' : register ? 'Create account' : 'Sign in'}</button></form><p>{register ? <>Already have an account? <Link to={adminDestination ? `/login?returnTo=${encodeURIComponent(adminDestination)}` : '/login'}>Sign in</Link></> : <>New here? <Link to={adminDestination ? `/register?returnTo=${encodeURIComponent(adminDestination)}` : '/register'}>Create an account</Link></>}</p></div></main>;
}
export function Login() { return <AuthForm register={false} />; }
export function Register() { return <AuthForm register />; }

export function Account({ products, wishlist, toggleWishlist }: { products: Product[]; wishlist: number[]; toggleWishlist: (id: number) => void }) {
  const [params, setParams] = useSearchParams();
  const section = params.get('section') || 'profile';
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState('');
  const [loadingOrders, setLoadingOrders] = useState(Boolean(getToken()));
  const navigate = useNavigate();
  const user = getUser();
  const loadOrders = async () => {
    setLoadingOrders(true); setError('');
    try { setOrders(await api<Order[]>('/api/orders/my-orders')); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Order history unavailable'); }
    finally { setLoadingOrders(false); }
  };
  useEffect(() => { if (getToken()) void loadOrders(); }, []);
  if (section === 'wishlist' && (!user || !getToken())) return <main><Banner eyebrow="Your favourites" title="Saved pieces" description="Your wishlist is saved in this browser." /><section className="section"><div className="container">{wishlist.length ? <div className="wishlist-grid">{wishlist.map(id => { const product = products.find(item => item.id === id); return product ? <article key={id}><Link to={`/product/${id}`}><img src={product.image_url || ''} alt={product.name} /><h3>{product.name}</h3></Link><p>{formatPrice(priceOf(product))}</p><button type="button" onClick={() => toggleWishlist(id)}>Remove</button></article> : null; })}</div> : <div className="empty-state"><h2>No saved pieces yet</h2><p>Tap the heart on any piece to keep it here.</p><Link to="/shop" className="button button-primary">Explore the collection</Link></div>}</div></section></main>;
  if (!user || !getToken()) return <main className="simple-page"><h1>Your account</h1><p>Sign in to view your profile and orders.</p><Link to="/login" className="button button-primary">Sign in</Link></main>;
  return <main><Banner eyebrow="Welcome back" title={`Hello, ${user.full_name.split(' ')[0]}`} /><section className="section"><div className="container account-layout"><nav className="account-menu" aria-label="Account sections">{[['profile', 'Profile'], ['orders', 'Order history'], ['wishlist', `Wishlist (${wishlist.length})`]].map(([key, label]) => <button key={key} type="button" className={section === key ? 'selected' : ''} onClick={() => setParams({ section: key })}>{label}</button>)}<button type="button" onClick={() => { clearSession(); navigate('/login'); }}>Sign out</button></nav><div className="account-content">{section === 'orders' ? <><div className="account-order-heading"><h2>Order history</h2><button type="button" className="button button-outline" disabled={loadingOrders} onClick={() => void loadOrders()}>{loadingOrders ? "Refreshing…" : "Refresh orders"}</button></div>{error && <p className="notice error" role="alert">{error}</p>}{loadingOrders && !orders.length ? <p role="status">Loading orders…</p> : orders.length ? orders.map(order => <article className="order-card" key={order.id}><div><h3>Order #{order.id}</h3><span>{new Date(order.created_at).toLocaleDateString('en-IN')}</span></div><p>Status: {order.status === 'awaiting_payment' ? 'Awaiting UPI payment' : order.status === 'cancellation_requested' ? 'Cancellation under review' : order.status === 'payment_submitted' ? 'Payment under review' : order.status === 'paid' ? 'Payment verified' : order.status === 'cancelled' ? 'Cancelled' : order.status.replaceAll('_', ' ')}</p><p>{order.items.map(item => `${item.product_name} × ${item.quantity}`).join(' · ')}</p><strong>{formatPrice(order.total)}</strong>{order.refunded_amount_paise > 0 && <p className="notice">Recorded refund: {formatPrice(order.refunded_amount_paise / 100)}</p>}{order.fulfillment && <p>Delivery: <strong>{order.fulfillment.status}</strong>{order.fulfillment.tracking_reference && <> · {order.fulfillment.carrier}: {order.fulfillment.tracking_reference}</>}</p>}{order.payment_token && <Link to={paymentLink(order.payment_token)} className="button button-outline order-payment-link">{order.status === "awaiting_payment" ? "Resume UPI payment" : order.status === "cancellation_requested" ? "View cancellation request" : order.status === "paid" ? "View payment & delivery" : order.status === "cancelled" ? "View cancelled order" : "Check payment review"}</Link>}</article>) : !error ? <p>No orders yet. Your pieces will appear here after checkout.</p> : null}</> : section === 'wishlist' ? <><h2>Your saved pieces</h2>{wishlist.length ? <div className="wishlist-grid">{wishlist.map(id => { const product = products.find(item => item.id === id); return product ? <article key={id}><Link to={`/product/${id}`}><img src={product.image_url || ''} alt={product.name} /><h3>{product.name}</h3></Link><p>{formatPrice(priceOf(product))}</p><button type="button" onClick={() => toggleWishlist(id)}>Remove</button></article> : null; })}</div> : <p>Save pieces you love using the heart on a product card.</p>}</> : <><h2>Your profile</h2><dl><dt>Name</dt><dd>{user.full_name}</dd><dt>Email</dt><dd>{user.email}</dd><dt>Phone</dt><dd>{user.phone || 'Not provided'}</dd></dl></>}</div></div></section></main>;
}

type AdminPayment = {
  order_id: number; customer_name: string; email: string; total: number; status: string;
  payment_reference: string | null; payer_name: string | null; submitted_at: string | null;
  created_at: string; review_note: string | null;
  reviews: { decision: string; reference: string | null; note: string | null; created_at: string }[];
  refunded_amount_paise: number;
  refunds: { id: number; amount_paise: number; outgoing_reference: string; reason: string; created_at: string }[];
};
type AdminPaymentPage = { items: AdminPayment[]; has_more: boolean };

export function AdminPayments() {
  const user = getUser();
  const [orders, setOrders] = useState<AdminPayment[]>([]);
  const [error, setError] = useState('');
  const [errorOrderId, setErrorOrderId] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [view, setView] = useState<'review' | 'awaiting' | 'closed'>('review');
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const requestId = useRef(0);
  const selectView = (next: 'review' | 'awaiting' | 'closed') => {
    if (next === view) return;
    requestId.current += 1;
    setOrders([]); setHasMore(false); setError(''); setErrorOrderId(null); setView(next);
  };
  const refresh = async (offset = 0, selectedView = view) => {
    const id = ++requestId.current;
    setLoading(true); setError(''); setErrorOrderId(null);
    try {
      const page = await api<AdminPaymentPage>(`/api/admin/payments?view=${selectedView}&offset=${offset}`);
      if (id !== requestId.current) return;
      setOrders(current => offset ? [...current, ...page.items] : page.items);
      setHasMore(page.has_more);
    } catch (reason) { if (id === requestId.current) setError(reason instanceof Error ? reason.message : 'Could not load payments'); }
    finally { if (id === requestId.current) setLoading(false); }
  };
  useEffect(() => { if (user?.is_admin) void refresh(0, view); }, [user?.is_admin, view]);
  const review = async (event: FormEvent<HTMLFormElement>, order: AdminPayment, decision: 'approve' | 'reject' | 'cancel') => {
    event.preventDefault();
    const issue = formIssue(event.currentTarget);
    if (issue) { setErrorOrderId(order.order_id); setError(issue); return; }
    setBusy(order.order_id); setError(''); setErrorOrderId(null);
    const form = new FormData(event.currentTarget);
    try {
      await api(`/api/admin/payments/${order.order_id}/review`, { method: 'POST', body: JSON.stringify({
        decision, statement_reference: String(form.get('statement_reference') || '').trim(),
        statement_amount_paise: Math.round(Number(form.get('statement_amount') || 0) * 100),
        statement_checked: form.get('statement_checked') === 'on',
        note: String(form.get('note') || '').trim(),
        statement_checked_no_payment: form.get('statement_checked_no_payment') === 'on',
      }) });
      await refresh(0, view);
    } catch (reason) { setErrorOrderId(order.order_id); setError(reason instanceof Error ? reason.message : 'Could not review payment'); }
    finally { setBusy(null); }
  };
  const recordRefund = async (event: FormEvent<HTMLFormElement>, order: AdminPayment) => {
    event.preventDefault();
    const issue = formIssue(event.currentTarget);
    if (issue) { setErrorOrderId(order.order_id); setError(issue); return; }
    const form = new FormData(event.currentTarget);
    setBusy(order.order_id); setError(''); setErrorOrderId(null);
    try {
      await api(`/api/admin/payments/${order.order_id}/refunds`, { method: 'POST', body: JSON.stringify({
        amount_paise: Math.round(Number(form.get('amount')) * 100),
        outgoing_reference: String(form.get('outgoing_reference') || '').trim(),
        reason: String(form.get('reason') || '').trim(),
        transfer_confirmed: form.get('transfer_confirmed') === 'on',
      }) });
      await refresh(0, view);
    } catch (reason) { setErrorOrderId(order.order_id); setError(reason instanceof Error ? reason.message : 'Could not record refund'); }
    finally { setBusy(null); }
  };
  if (!user?.is_admin) return <AdminAccess purpose="review payments" />;
  return <main>
    <Banner eyebrow="Store operations" title="UPI payment review" description="Match payment references and cancellation requests against the receiving account before approving payment or releasing stock." />
    <section className="section"><div className="container admin-payments">
      <div className="admin-queue-tabs" role="group" aria-label="Payment queue view">
        <button type="button" disabled={busy !== null} aria-pressed={view === 'review'} onClick={() => selectView('review')}>References to review</button>
        <button type="button" disabled={busy !== null} aria-pressed={view === 'awaiting'} onClick={() => selectView('awaiting')}>Unpaid / cancellation</button>
        <button type="button" disabled={busy !== null} aria-pressed={view === 'closed'} onClick={() => selectView('closed')}>Completed history</button>
      </div>
      <button type="button" className="button button-outline" disabled={loading || busy !== null} onClick={() => void refresh()}>Refresh</button>
      {error && errorOrderId === null && <p className="notice error" role="alert">{error}</p>}
      {orders.map(order => <article className="checkout-form" key={order.order_id}>
        <h2>Order #{order.order_id} · {formatPrice(order.total)}</h2>
        <p>{order.customer_name} · {order.email}</p>
        <p>Placed {new Date(order.created_at).toLocaleString('en-IN')}</p>
        <p>Status: <strong>{order.status.replaceAll('_', ' ')}</strong></p>
        {order.status === 'cancellation_requested' && <p className="notice">Customer requested cancellation. Check the receiving account before closing this order.</p>}
        <p>Payer: {order.payer_name || 'Not submitted'} · Reference: <strong>{order.payment_reference || 'Not submitted'}</strong></p>
        {order.review_note && <p>Previous review: {order.review_note}</p>}
        {order.reviews.length > 0 && <details className="payment-review-history"><summary>Review history ({order.reviews.length})</summary><ul>{order.reviews.map((item, index) => <li key={`${item.created_at}-${index}`}><strong>{item.decision.replaceAll('_', ' ')}</strong> · {new Date(item.created_at).toLocaleString('en-IN')}{item.reference && <> · Reference {item.reference}</>}{item.note && <p>{item.note}</p>}</li>)}</ul></details>}
        {order.refunded_amount_paise > 0 && <p className="notice">Recorded refunds: {formatPrice(order.refunded_amount_paise / 100)} of {formatPrice(order.total)}.</p>}
        {order.refunds.length > 0 && <details className="payment-review-history"><summary>Refund records ({order.refunds.length})</summary><ul>{order.refunds.map(item => <li key={item.id}><strong>{formatPrice(item.amount_paise / 100)}</strong> · {new Date(item.created_at).toLocaleString('en-IN')} · Outgoing reference {item.outgoing_reference}<p>{item.reason}</p></li>)}</ul></details>}
        {order.status === 'paid' && order.refunded_amount_paise < Math.round(order.total * 100) && <form noValidate onSubmit={event => recordRefund(event, order)}>
          <p className="wide">Record an already completed bank or UPI refund. This form does not send money.</p>
          <label>Refund amount (₹)<input name="amount" type="number" min="0.01" max={(Math.round(order.total * 100) - order.refunded_amount_paise) / 100} step="0.01" required /></label>
          <label>Outgoing refund reference<input name="outgoing_reference" minLength={8} maxLength={100} pattern="[A-Za-z0-9/_-]+" required autoComplete="off" /></label>
          <label>Reason<input name="reason" minLength={5} maxLength={1000} required /></label>
          <label className="admin-confirm"><input name="transfer_confirmed" type="checkbox" required /> I checked the actual completed refund and amount</label>
          <button className="button button-outline" disabled={busy === order.order_id}>Record completed refund</button>
        </form>}
        {order.status === 'payment_submitted' && <form noValidate onSubmit={event => review(event, order, 'approve')}>
          <label>Reference on receiving bank statement<input name="statement_reference" required autoComplete="off" /></label>
          <label>Amount on receiving bank statement (₹)<input name="statement_amount" type="number" min="0.01" step="0.01" required /></label>
          <label className="admin-confirm"><input name="statement_checked" type="checkbox" required /> I checked the receiving account, reference and exact amount</label>
          <button className="button button-primary" disabled={busy === order.order_id}>Verify and approve</button>
        </form>}
        {order.status !== 'paid' && order.status !== 'cancelled' && <form noValidate onSubmit={event => review(event, order, order.status === 'payment_submitted' ? 'reject' : 'cancel')}>
          <label>Reason / review note<input name="note" required maxLength={1000} /></label>
          {order.status !== 'payment_submitted' && <label className="admin-confirm"><input name="statement_checked_no_payment" type="checkbox" required /> Receiving account checked; no matching payment found</label>}
          <button className="button button-outline" disabled={busy === order.order_id}>{order.status === 'payment_submitted' ? 'Reject reference' : order.status === 'cancellation_requested' ? 'Confirm cancellation' : 'Cancel unpaid order'}</button>
        </form>}
        {order.status === 'payment_submitted' && <form noValidate onSubmit={event => review(event, order, 'cancel')}>
          <label>Cancellation reason<input name="note" required maxLength={1000} /></label>
          <label className="admin-confirm"><input name="statement_checked_no_payment" type="checkbox" required /> Receiving account checked; no matching payment found</label>
          <button className="remove-link" disabled={busy === order.order_id}>Cancel order after review</button>
        </form>}
        {errorOrderId === order.order_id && <p className="notice error" role="alert">{error}</p>}
      </article>)}
      {orders.length === 0 && !loading && !error && <p>{view === 'review' ? 'No submitted references need review.' : view === 'awaiting' ? 'No unpaid orders or cancellation requests.' : 'No completed payment reviews yet.'}</p>}
      {hasMore && <button type="button" className="button button-outline" disabled={loading || busy !== null} onClick={() => void refresh(orders.length)}>{loading ? 'Loading…' : 'Load more orders'}</button>}
    </div></section>
  </main>;
}
