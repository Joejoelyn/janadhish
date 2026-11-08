import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { AdminAccess, Banner } from './Layout';
import { ThemeSelect } from './ThemeSelect';
import { formIssue } from './formValidation';
import { api, getUser } from './lib';

type Page<T> = { items: T[]; has_more: boolean };
type Message = {
  id: number; name: string; email: string; phone: string | null; subject: string | null;
  message: string; status: 'received' | 'in_progress' | 'resolved'; created_at: string;
  updates: { status: string; reply: string | null; reviewer_user_id: number; created_at: string }[];
};
type CustomRequest = {
  id: number; garment_category: string; fabric_name: string | null; design_name: string | null;
  measurements: Record<string, number>; preferences: {
    contact?: { name?: string; email?: string; phone?: string };
    style?: string; measurement_unit?: string; admin_note?: string;
  };
  special_instructions: string | null; status: string; created_at: string;
};

export function AdminInbox() {
  const user = getUser();
  const [messages, setMessages] = useState<Message[]>([]);
  const [requests, setRequests] = useState<CustomRequest[]>([]);
  const [moreMessages, setMoreMessages] = useState(false);
  const [moreRequests, setMoreRequests] = useState(false);
  const [error, setError] = useState('');
  const [errorTarget, setErrorTarget] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadMessages = async (offset = 0) => {
    const page = await api<Page<Message>>(`/api/admin/contact-messages?offset=${offset}`);
    setMessages(current => offset ? [...current, ...page.items] : page.items);
    setMoreMessages(page.has_more);
  };
  const loadRequests = async (offset = 0) => {
    const page = await api<Page<CustomRequest>>(`/api/admin/custom-requests?offset=${offset}`);
    setRequests(current => offset ? [...current, ...page.items] : page.items);
    setMoreRequests(page.has_more);
  };
  const refresh = async () => {
    setBusy(true); setError(''); setErrorTarget(null);
    try { await Promise.all([loadMessages(), loadRequests()]); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load the inbox'); }
    finally { setBusy(false); }
  };
  useEffect(() => { if (user?.is_admin) void refresh(); }, [user?.is_admin]);
  const loadMore = async (kind: 'messages' | 'requests') => {
    setBusy(true); setError(''); setErrorTarget(null);
    try { if (kind === 'messages') await loadMessages(messages.length); else await loadRequests(requests.length); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load more'); }
    finally { setBusy(false); }
  };
  const review = async (event: FormEvent<HTMLFormElement>, id: number) => {
    event.preventDefault(); setBusy(true); setError(''); setErrorTarget(null);
    const values = new FormData(event.currentTarget);
    try {
      await api(`/api/admin/custom-requests/${id}/review`, { method: 'POST', body: JSON.stringify({
        status: values.get('status'), note: String(values.get('note') || '').trim(),
      }) });
      await loadRequests();
    } catch (reason) { setErrorTarget(`request-${id}`); setError(reason instanceof Error ? reason.message : 'Could not update the request'); }
    finally { setBusy(false); }
  };
  const reviewMessage = async (event: FormEvent<HTMLFormElement>, item: Message) => {
    event.preventDefault();
    const issue = formIssue(event.currentTarget);
    if (issue) { setErrorTarget(`message-${item.id}`); setError(issue); return; }
    const values = new FormData(event.currentTarget);
    const status = String(values.get('status'));
    const reply = String(values.get('reply') || '').trim();
    if (status === item.status && !reply) { setErrorTarget(`message-${item.id}`); setError('Choose a new status or add a reply.'); return; }
    if (status === 'resolved' && !reply && !item.updates.some(update => update.reply)) {
      setErrorTarget(`message-${item.id}`); setError('Add a customer-visible reply before resolving this ticket.'); return;
    }
    const form = event.currentTarget;
    setBusy(true); setError(''); setErrorTarget(null);
    try {
      await api(`/api/admin/contact-messages/${item.id}/review`, {
        method: 'POST', body: JSON.stringify({ status, reply }),
      });
      form.reset();
      await loadMessages();
    } catch (reason) { setErrorTarget(`message-${item.id}`); setError(reason instanceof Error ? reason.message : 'Could not update message status'); }
    finally { setBusy(false); }
  };

  if (!user?.is_admin) return <AdminAccess purpose="view the inbox" />;
  return <main><Banner eyebrow="Store operations" title="Customer inbox" description="Contact messages and custom requests submitted through the storefront." />
    <section className="section"><div className="container admin-inbox">
      <button type="button" className="button button-outline" disabled={busy} onClick={() => void refresh()}>Refresh inbox</button>
      {error && !errorTarget && <p className="notice error" role="alert">{error}</p>}
      <h2>Custom requests</h2>
      {requests.length ? requests.map(item => <article className="checkout-form" key={item.id}>
        <div className="inbox-heading"><h3>Request #{item.id} · {item.garment_category}</h3><span>{new Date(item.created_at).toLocaleString('en-IN')}</span></div>
        <p><strong>Status:</strong> {item.status}</p>
        <p><strong>Customer:</strong> {item.preferences?.contact?.name || 'Earlier request'} · {item.preferences?.contact?.email ? <a href={`mailto:${item.preferences.contact.email}`}>{item.preferences.contact.email}</a> : 'No email supplied'}{item.preferences?.contact?.phone && <> · <a href={`tel:${item.preferences.contact.phone}`}>{item.preferences.contact.phone}</a></>}</p>
        <p><strong>Fabric:</strong> {item.fabric_name || '—'} · <strong>Design:</strong> {item.design_name || '—'}</p>
        <p><strong>Measurements:</strong> {Object.entries(item.measurements || {}).map(([name, value]) => `${name}: ${value}`).join(' · ') || '—'} {item.preferences?.measurement_unit || ''}</p>
        {item.preferences?.style && <p><strong>Style:</strong> {item.preferences.style}</p>}
        {item.special_instructions && <p><strong>Instructions:</strong> {item.special_instructions}</p>}
        <form key={`${item.id}-${item.status}-${item.preferences?.admin_note || ''}`} className="inbox-review" onSubmit={event => review(event, item.id)}>
          <ThemeSelect label="Status" name="status" defaultValue={item.status} options={[{ value: 'pending', label: 'Pending' }, { value: 'reviewed', label: 'Reviewed' }, { value: 'closed', label: 'Closed' }]} />
          <label>Internal note<input name="note" maxLength={1000} defaultValue={item.preferences?.admin_note || ''} /></label>
          <button className="button button-primary" disabled={busy}>Save review</button>
        </form>
        {errorTarget === `request-${item.id}` && <p className="notice error" role="alert">{error}</p>}
      </article>) : <p>No custom requests yet.</p>}
      {moreRequests && <button type="button" className="button button-outline" disabled={busy} onClick={() => void loadMore('requests')}>Load more requests</button>}
      <h2>Contact messages</h2>
      {messages.length ? messages.map(item => <article className="checkout-form" key={item.id}>
        <div className="inbox-heading"><h3>JD-{String(item.id).padStart(6, '0')} · {item.subject || 'Contact message'}</h3><span>{new Date(item.created_at).toLocaleString('en-IN')}</span></div>
        <p><strong>Status:</strong> {item.status.replaceAll('_', ' ')}</p>
        <p><strong>{item.name}</strong> · <a href={`mailto:${item.email}`}>{item.email}</a>{item.phone && <> · <a href={`tel:${item.phone}`}>{item.phone}</a></>}</p>
        <p className="inbox-message">{item.message}</p>
        {item.updates.length > 0 && <details className="payment-review-history"><summary>Ticket history ({item.updates.length})</summary><ul>{item.updates.map((update, index) => <li key={`${update.created_at}-${index}`}><strong>{update.status.replaceAll('_', ' ')}</strong> · {new Date(update.created_at).toLocaleString('en-IN')} · Staff #{update.reviewer_user_id}{update.reply && <p>Customer reply: {update.reply}</p>}</li>)}</ul></details>}
        <form key={`${item.id}-${item.status}`} className="inbox-review" noValidate onSubmit={event => reviewMessage(event, item)}>
          <ThemeSelect label="Status" name="status" defaultValue={item.status} options={[{ value: 'received', label: 'Received' }, { value: 'in_progress', label: 'In progress' }, { value: 'resolved', label: 'Resolved' }]} />
          <label className="inbox-reply-field">Reply on private tracking page<textarea name="reply" rows={3} maxLength={2000} placeholder="A reply is required when resolving a ticket." /></label>
          <button className="button button-primary" disabled={busy}>Save update</button>
        </form>
        {errorTarget === `message-${item.id}` && <p className="notice error" role="alert">{error}</p>}
      </article>) : <p>No contact messages yet.</p>}
      {moreMessages && <button type="button" className="button button-outline" disabled={busy} onClick={() => void loadMore('messages')}>Load more messages</button>}
    </div></section></main>;
}
