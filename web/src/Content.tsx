import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { Banner } from './Layout';
import { ThemeSelect } from './ThemeSelect';
import { formIssue } from './formValidation';
import { api, getUser } from './lib';
import type { Option } from './types';

export function About() {
  return <main><Banner eyebrow="Our story" title="A mother’s passion, stitched into a dream." /><section className="section"><div className="container about-grid"><div><p className="eyebrow">Made with love</p><h2>25+ years of making clothes feel personal.</h2><img src="/Images/products/white-halter-neck-kurti/photo-01.webp" alt="A JANADHISH garment" /></div><div className="story-copy"><p>JANADHISH started with something our mother has loved doing for over 25 years: stitching and creating clothes. Kiran Lodha has always enjoyed making outfits, trying new designs, and turning simple pieces of fabric into something beautiful.</p><p>What began as a passion slowly grew into a dream of having something of her own. That’s how JANADHISH came into being.</p><p>We believe clothes should be comfortable, beautiful, and made the way you like them. We love Indian fabrics, cottons, handblock prints, and designs you can wear and feel good in.</p><p>For us, this brand is personal: our mother’s years of experience, her love for stitching, and our little dream of turning that passion into something bigger.</p><p><strong>Welcome to JANADHISH. We’re happy you’re here.</strong></p><Link to="/shop" className="button button-primary">Explore the collection</Link></div></div></section></main>;
}

type ContactTrackingState = {
  ticket_number: string; status: string;
  updates: { status: string; reply: string; created_at: string }[];
};

export function Contact() {
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const [tracking, setTracking] = useState<ContactTrackingState | null>(null);
  const [trackingError, setTrackingError] = useState('');
  const [trackingBusy, setTrackingBusy] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const trackingToken = new URLSearchParams(location.hash.slice(1)).get('ticket');
  useEffect(() => {
    if (!trackingToken) { setTracking(null); setTrackingError(''); return; }
    let active = true;
    setTracking(null); setTrackingError('');
    setTrackingBusy(true);
    api<ContactTrackingState>('/api/contact/status', {
      method: 'POST', body: JSON.stringify({ tracking_token: trackingToken }),
    }).then(result => { if (active) { setTracking(result); setTrackingError(''); } })
      .catch(reason => { if (active) setTrackingError(reason instanceof Error ? reason.message : 'Could not load request status'); })
      .finally(() => { if (active) setTrackingBusy(false); });
    return () => { active = false; };
  }, [trackingToken]);
  const refreshTracking = async () => {
    if (!trackingToken) return;
    setTrackingBusy(true); setTrackingError('');
    try {
      setTracking(await api<ContactTrackingState>('/api/contact/status', {
        method: 'POST', body: JSON.stringify({ tracking_token: trackingToken }),
      }));
    } catch (reason) {
      setTracking(null);
      setTrackingError(reason instanceof Error ? reason.message : 'Could not load request status');
    }
    finally { setTrackingBusy(false); }
  };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const issue = formIssue(event.currentTarget);
    if (issue) { setStatus(issue); return; }
    setBusy(true); setStatus('');
    const form = event.currentTarget;
    const values = new FormData(form);
    try {
      const data = await api<{ message: string; ticket_number: string; tracking_token: string }>('/api/contact', {
        method: 'POST', body: JSON.stringify(Object.fromEntries(values)),
      });
      setStatus(`${data.message} Reference ${data.ticket_number}. Save this private page address to track it.`);
      navigate({ hash: `ticket=${encodeURIComponent(data.tracking_token)}` }, { replace: true });
      form.reset();
    }
    catch (error) { setStatus(error instanceof Error ? error.message : 'Could not send your message.'); }
    finally { setBusy(false); }
  };
  return <main><Banner eyebrow="Get in touch" title="We’d love to hear from you." description="Questions about a piece, fit, or your order? Write to us." /><section className="section"><div className="container contact-layout"><form className="contact-form" noValidate onSubmit={submit}><div className="field-grid"><label>Name<input name="name" required minLength={2} maxLength={150} /></label><label>Email<input type="email" name="email" required /></label><label>Phone<input type="tel" name="phone" maxLength={50} /></label><label>Subject<input name="subject" maxLength={200} /></label><label className="wide">Message<textarea name="message" rows={6} required minLength={5} maxLength={5000} /></label></div><button type="submit" disabled={busy} className="button button-primary">{busy ? 'Sending…' : 'Send message'}</button><p className="status-message" role="status">{status}</p>{trackingToken && <div className="contact-tracking"><h2>Track your request</h2><p role="status">{tracking ? tracking.ticket_number + ' · ' + tracking.status.replaceAll('_', ' ') : trackingError || 'Checking status…'}</p>{trackingError && tracking && <p className="notice error" role="alert">{trackingError}</p>}{tracking?.updates.map(item => <div className="contact-reply" key={item.created_at + item.reply}><small>JANADHISH · {new Date(item.created_at).toLocaleString('en-IN')}</small><p>{item.reply}</p></div>)}<button type="button" className="button button-outline" disabled={trackingBusy} onClick={() => void refreshTracking()}>{trackingBusy ? 'Checking…' : 'Refresh ticket'}</button><small>Staff replies appear here; no email is sent. Keep this private page address.</small></div>}</form><aside className="contact-details"><h2>Visit or call us</h2><p><strong>Instagram</strong><br /><a href="https://www.instagram.com/janadhish_clo/" target="_blank" rel="noreferrer">@janadhish_clo</a></p><p><strong>Phone</strong><br /><a href="tel:+916378257535">+91 63782 57535</a></p><p><strong>Studio</strong><br />Mansi Apt, Bedla Road, opposite Hero Honda Showroom, Udaipur, Rajasthan</p><p><strong>Hours</strong><br />Monday to Saturday, 10:00 AM – 6:00 PM</p></aside></div></section></main>;
}

const garmentMeasurements = {
  Saree: ['Waist', 'Hips', 'Shoulder to waist', 'Saree length', 'Pallu length'],
  Kurta: ['Chest', 'Waist', 'Hips', 'Shoulder', 'Sleeve length', 'Kurta length'],
  Anarkali: ['Bust', 'Waist', 'Hip', 'Shoulder', 'Sleeve length', 'Gown length'],
  'Fusion Set': ['Bust', 'Waist', 'Hip', 'Shoulder', 'Trouser waist', 'Pant length'],
  Gown: ['Bust', 'Waist', 'Hip', 'Shoulder', 'Sleeve length', 'Gown length'],
} as const;
type Garment = keyof typeof garmentMeasurements;
const garments = Object.keys(garmentMeasurements) as Garment[];

export function CustomMade() {
  const [fabrics, setFabrics] = useState<Option[]>([]);
  const [designs, setDesigns] = useState<Option[]>([]);
  const [garment, setGarment] = useState<Garment | ''>('');
  const [fabric, setFabric] = useState('');
  const [design, setDesign] = useState('');
  const [unit, setUnit] = useState('inches');
  const [measurements, setMeasurements] = useState<Record<string, string>>({});
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const user = getUser();
  const labels = garment ? garmentMeasurements[garment] : [];
  useEffect(() => {
    api<Option[]>('/api/fabrics').then(setFabrics).catch(() => setStatus('Fabric choices are temporarily unavailable.'));
    api<Option[]>('/api/designs').then(setDesigns).catch(() => setStatus('Design choices are temporarily unavailable.'));
  }, []);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const issue = formIssue(event.currentTarget);
    if (issue) { setStatus(issue); return; }
    setBusy(true); setStatus('');
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    if (!garment || !fabric || !design) { setStatus('Choose a garment, fabric and design.'); setBusy(false); return; }
    const values = Object.fromEntries(garmentMeasurements[garment].map(label => [label, Number(measurements[label])]));
    try {
      const data = await api<{ id: number }>('/api/customizations', { method: 'POST', body: JSON.stringify({
        garment_category: garment, fabric_name: fabric, design_name: design,
        contact_name: String(form.get('contact_name') || '').trim(),
        contact_email: String(form.get('contact_email') || '').trim(),
        contact_phone: String(form.get('contact_phone') || '').trim(),
        measurements: values, preferences: { style: form.get('style') || '', measurement_unit: form.get('unit') },
        special_instructions: form.get('instructions') || '',
      }) });
      formElement.reset(); setGarment(''); setFabric(''); setDesign(''); setUnit('inches'); setMeasurements({});
      setStatus(`Request #${data.id} received. Our team can use your contact details to discuss it. No order or payment was placed.`);
    }
    catch (error) { setStatus(error instanceof Error ? error.message : 'Could not send your request.'); }
    finally { setBusy(false); }
  };
  return <main><Banner eyebrow="Made around you" title="A piece as individual as you." description="Choose a garment and share your ideas. Our team will review your request." />
    <section className="section"><div className="container custom-intro"><div><p className="eyebrow">Have a piece in mind?</p><h2>Tell us what you imagine.</h2><p>Already found a piece in our collection? You can add optional measurements directly on its product page.</p><Link to="/shop" className="text-link">Explore the collection ↗</Link></div><img src="/Images/products/green-farshi-salwar-set/photo-39.webp" alt="Green Farshi salwar set" /></div></section>
    <section className="section section-alt"><div className="container custom-form-wrap"><div><p className="eyebrow">Your request</p><h2>Let's make it personal.</h2><p>Choose each detail, then check the summary before sending. This request does not place an order.</p></div>
      <form className="custom-form" noValidate onSubmit={submit}>
        <fieldset className="custom-fieldset"><legend>1. Garment</legend><div className="custom-garments">{garments.map(item => <label key={item} className={`custom-garment ${garment === item ? 'selected' : ''}`}><input type="radio" name="garment" value={item} checked={garment === item} onChange={() => { setGarment(item); setMeasurements({}); }} required /><span>{item}</span></label>)}</div></fieldset>
        <fieldset className="custom-fieldset"><legend>2. Fabric</legend><div className="custom-options">{fabrics.map(item => <label key={item.id} className={`custom-option ${fabric === item.name ? 'selected' : ''}`}><input type="radio" name="fabric" value={item.name} checked={fabric === item.name} onChange={() => setFabric(item.name)} required /><img src={item.image_url || '/assets/images/fabrics/cotton-silk.svg'} alt="" /><span><strong>{item.name}</strong><small>{item.description}</small></span></label>)}</div></fieldset>
        <fieldset className="custom-fieldset"><legend>3. Design</legend><div className="custom-options">{designs.map(item => <label key={item.id} className={`custom-option ${design === item.name ? 'selected' : ''}`}><input type="radio" name="design" value={item.name} checked={design === item.name} onChange={() => setDesign(item.name)} required /><img src={item.image_url || '/assets/images/designs/floral-chikankari.svg'} alt="" /><span><strong>{item.name}</strong><small>{item.description}</small></span></label>)}</div></fieldset>
        <fieldset className="custom-fieldset"><legend>4. Measurements</legend><div className="field-grid"><ThemeSelect label="Unit" name="unit" value={unit} onChange={setUnit} options={[{ value: 'inches', label: 'Inches' }, { value: 'cm', label: 'Centimetres' }]} /></div>{garment ? <div className="field-grid">{labels.map(label => <label key={label}>{label}<input type="number" name={label} required min="0.1" max="300" step="0.1" inputMode="decimal" value={measurements[label] || ''} onChange={event => setMeasurements(current => ({ ...current, [label]: event.target.value }))} /></label>)}</div> : <p className="form-note">Choose a garment to see its measurements.</p>}</fieldset>
        <fieldset className="custom-fieldset"><legend>5. Your details</legend><div className="field-grid"><label>Name<input name="contact_name" required minLength={2} maxLength={150} defaultValue={user?.full_name || ''} autoComplete="name" /></label><label>Email<input name="contact_email" type="email" required defaultValue={user?.email || ''} autoComplete="email" /></label><label>Phone<input name="contact_phone" type="tel" defaultValue={user?.phone || ''} autoComplete="tel" /></label><label className="wide">Style preferences<textarea name="style" rows={3} maxLength={1000} placeholder="Colours, silhouette, detailing…" /></label><label className="wide">Special instructions<textarea name="instructions" rows={3} maxLength={1000} /></label></div></fieldset>
        <div className="custom-review"><h3>Review your request</h3><p><strong>Garment:</strong> {garment || 'Choose a garment'}</p><p><strong>Fabric:</strong> {fabric || 'Choose a fabric'}</p><p><strong>Design:</strong> {design || 'Choose a design'}</p>{garment && <p><strong>Measurements:</strong> {labels.map(label => `${label}: ${measurements[label] || '—'}`).join(' · ')}</p>}</div>
        <button type="submit" className="button button-primary" disabled={busy || !fabrics.length || !designs.length}>{busy ? 'Sending…' : 'Send measurement request'}</button><p className="status-message" role="status">{status}</p>
      </form></div></section></main>;
}

export function Faq() {
  return <main><Banner eyebrow="Good to know" title="Frequently asked questions" /><section className="section"><div className="container faq-list"><details><summary>How do I add measurements to a product?</summary><p>Open the product page and expand “Add your measurements”. Complete every field, or leave them all blank to use a standard size.</p></details><details><summary>How do I request a custom piece?</summary><p>Use the <Link to="/custom-made">custom-made request form</Link>. Our team reviews the details before confirming an order or price.</p></details><details><summary>How much is shipping?</summary><p>Standard shipping is ₹250 below ₹3,000 and complimentary from ₹3,000. Express availability is confirmed separately.</p></details><details><summary>Can I change my size after ordering?</summary><p><Link to="/contact">Contact us</Link> as soon as possible. Changes depend on whether your piece has entered production or dispatch.</p></details></div></section></main>;
}

export function Policy({ kind }: { kind: 'privacy' | 'terms' | 'shipping' }) {
  const content = {
    privacy: {
      eyebrow: 'Privacy', title: 'Your information',
      sections: [
        { title: 'Information we collect', text: 'Account details include your name, email, optional phone number, and a password stored as a hash. Checkout also records your address, selected items, optional measurements, order status, and any UPI reference you submit. Contact and custom-made forms retain the details you send.' },
        { title: 'How we use it', text: 'We use this information to run the store, verify QR payments, prepare and deliver orders, answer requests, and protect the service. We do not ask for your UPI PIN, bank password, or card number.' },
        { title: 'Browser and stylist', text: 'Your bag and wishlist are kept in this browser. Sign-in and private order links are kept for the browser session. Contact requests have a private tracking link for staff replies and status updates that you should keep secure. The stylist uses our catalog locally by default. If you opt in to external AI advice, your question and relevant catalog details may be sent to the configured AI provider.' },
        { title: 'Access and requests', text: 'Authorised staff can access information needed for payment review, fulfilment, and support. Contact us to ask about, correct, or request deletion of your information. Order and payment records may need to be retained for fulfilment, disputes, and applicable obligations. A final retention schedule and provider list will be published before launch.' },
      ],
    },
    terms: {
      eyebrow: 'Store terms', title: 'Shopping with JANADHISH',
      sections: [
        { title: 'Products and orders', text: 'Prices are shown in INR. Sizes, colours, and availability appear on each product page. Checkout calculates the item and shipping total. An order is accepted for fulfilment after we verify payment and confirm stock; if we cannot fulfil it, we will contact you to resolve the order and any amount received.' },
        { title: 'UPI QR payment', text: 'The displayed QR is the only checkout payment option. Check that your UPI app shows Kiran Lodha as the recipient and enter the exact order total. Submit your transaction reference through your private order link. A submitted reference is reviewed manually and is not proof of payment by itself. Do not pay twice while waiting for review.' },
        { title: 'Custom-made requests', text: 'Sending measurements or a design request starts a discussion. We confirm the design, price, and timing separately before accepting a custom order.' },
        { title: 'Changes and support', text: 'An unpaid order can be submitted for cancellation from its private link. We check the receiving account before releasing reserved stock. For paid orders, delivery, returns, and refunds, contact us with your order number. These sample terms do not limit remedies that apply to faulty, incorrect, or misdescribed goods.' },
      ],
    },
    shipping: {
      eyebrow: 'Shipping & returns', title: 'Delivery and returns',
      sections: [
        { title: 'Where and what it costs', text: 'We currently accept delivery addresses in India. Standard shipping is ₹250 below a ₹3,000 item subtotal and complimentary from ₹3,000. An express selection is a request; we confirm availability and any additional price before proceeding.' },
        { title: 'Dispatch and delivery', text: 'For this policy preview, we aim to dispatch ready-made items within 3–5 business days after payment is verified. Delivery time depends on the destination and courier. Custom or altered garments need a separately agreed schedule. Any carrier and tracking reference entered by our team will appear on your order page or private order link.' },
        { title: 'Returns and exchanges', text: 'For this policy preview, contact us within 7 calendar days of delivery about a ready-made item. A change-of-mind return should be unused, unwashed, and have its original tags. Custom or altered items are reviewed individually. Tell us promptly if an item is faulty, incorrect, or not as described; applicable consumer rights remain available.' },
        { title: 'Return shipping and refunds', text: 'We cover reasonable return shipping for an accepted faulty or incorrect item. For an accepted change-of-mind return, the customer covers return shipping. We verify returned items and any UPI deposit before approving a refund. For this policy preview, we aim to initiate an approved refund to a verified payer account within 7 business days; bank processing may take longer.' },
      ],
    },
  }[kind];
  return <main><Banner eyebrow={content.eyebrow} title={content.title} /><section className="section"><div className="container policy-content"><p className="policy-preview">Policy preview for owner review. The legal seller and grievance contact, sample timelines, and refund process need final confirmation before public launch.</p>{content.sections.map(section => <article key={section.title}><h2>{section.title}</h2><p>{section.text}</p></article>)}<div className="policy-contact"><h2>Need help?</h2><p>Use our contact form or call <a href="tel:+916378257535">+91 63782 57535</a>. Studio: Mansi Apt, Bedla Road, opposite Hero Honda Showroom, Udaipur, Rajasthan.</p><Link to="/contact" className="button button-outline">Contact us</Link></div></div></section></main>;
}
