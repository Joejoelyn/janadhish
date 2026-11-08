import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Check, History, Pencil, Save, Search } from 'lucide-react';
import { AdminAccess, Banner } from './Layout';
import { ThemeSelect } from './ThemeSelect';
import { formIssue } from './formValidation';
import { api, formatPrice, getUser, priceOf } from './lib';
import type { Product } from './types';

type CatalogAudit = {
  id: number; editor_user_id: number; before: Record<string, unknown>;
  after: Record<string, unknown>; created_at: string;
};

export function AdminCatalog({ refreshProducts }: { refreshProducts: () => Promise<void> }) {
  const user = getUser();
  const [products, setProducts] = useState<Product[]>([]);
  const [search, setSearch] = useState('');
  const [visibility, setVisibility] = useState('all');
  const [activeId, setActiveId] = useState<number | null>(null);
  const [history, setHistory] = useState<CatalogAudit[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const editor = useRef<HTMLDivElement>(null);
  const active = products.find(product => product.id === activeId);

  const load = async () => {
    setBusy(true); setError('');
    try { setProducts(await api<Product[]>('/api/admin/products')); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load products'); }
    finally { setBusy(false); }
  };
  useEffect(() => { if (user?.is_admin) void load(); }, [user?.is_admin]);

  const edit = async (product: Product) => {
    setActiveId(product.id); setError(''); setMessage(''); setShowHistory(false);
    try { setHistory(await api<CatalogAudit[]>(`/api/admin/products/${product.id}/history`)); }
    catch { setHistory([]); }
    requestAnimationFrame(() => { editor.current?.focus({ preventScroll: true }); editor.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!active) return;
    const issue = formIssue(event.currentTarget);
    if (issue) { setError(issue); return; }
    const data = new FormData(event.currentTarget);
    const text = (name: string) => String(data.get(name) || '').trim();
    const standard = Number(text('without_pads_price'));
    const pads = text('with_pads_price') ? Number(text('with_pads_price')) : null;
    if (pads !== null && pads <= standard) { setError('With-pads price must be higher than the standard price.'); return; }
    setBusy(true); setError(''); setMessage('');
    try {
      const updated = await api<Product>(`/api/admin/products/${active.id}`, { method: 'PUT', body: JSON.stringify({
        name: text('name'), short_description: text('short_description') || null,
        description: text('description') || null, fabric_details: text('fabric_details') || null,
        care_instructions: text('care_instructions') || null,
        without_pads_price: standard, with_pads_price: pads,
        stock_quantity: Number(text('stock_quantity')),
        expected_stock_quantity: active.stock_quantity,
        is_active: data.has('is_active'), is_new_arrival: data.has('is_new_arrival'),
        is_best_seller: data.has('is_best_seller'), is_featured: data.has('is_featured'),
      }) });
      setProducts(current => current.map(product => product.id === updated.id ? updated : product));
      await refreshProducts();
      try { setHistory(await api<CatalogAudit[]>(`/api/admin/products/${updated.id}/history`)); }
      catch { setHistory([]); }
      setMessage(`${updated.name} was saved. The storefront now shows the updated catalog.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save product'); }
    finally { setBusy(false); }
  };

  const shown = products.filter(product => {
    const matches = `${product.name} ${product.sku} ${product.category?.name || ''}`.toLowerCase().includes(search.toLowerCase());
    return matches && (visibility === 'all' || (visibility === 'active') === product.is_active);
  });

  if (!user?.is_admin) return <AdminAccess purpose="manage the catalog" />;
  return <main><Banner eyebrow="Store operations" title="Catalog management" description="Update prices, available stock and product details. Changes appear in the storefront immediately." />
    <section className="section"><div className="container admin-catalog">
      <div className="admin-catalog-heading"><div><h2>Products</h2><p>{shown.length} shown · {products.length} total</p></div><button type="button" className="button button-outline" disabled={busy} onClick={() => void load()}>Refresh products</button></div>
      <div className="admin-catalog-layout">
        <div className="admin-catalog-list">
          <label className="catalog-search"><Search size={18} aria-hidden="true" /><span className="sr-only">Search products</span><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search name, SKU or collection" /></label>
          <ThemeSelect label="Visibility" value={visibility} onChange={setVisibility} options={[{ value: 'all', label: 'All products' }, { value: 'active', label: 'Visible in store' }, { value: 'inactive', label: 'Hidden from store' }]} />
          <div className="admin-catalog-items">{shown.map(product => <article key={product.id} className={`admin-catalog-item ${activeId === product.id ? 'selected' : ''}`}>
            <img src={product.image_url || ''} alt="" /><div><h3>{product.name}</h3><p>{product.sku} · {product.category?.name || 'Uncategorized'}</p><strong>{formatPrice(priceOf(product))} · {product.stock_quantity} available</strong><span>{product.is_active ? 'Visible' : 'Hidden'}</span></div>
            <button type="button" aria-label={`Edit ${product.name}`} onClick={() => void edit(product)}><Pencil size={17} /></button>
          </article>)}{!shown.length && <p className="notice">No products match this view.</p>}</div>
        </div>
        <div ref={editor} id="product-editor" className="admin-catalog-editor" tabIndex={-1}>
          {active ? <><div className="admin-catalog-editor-heading"><div><p className="eyebrow">Editing {active.sku}</p><h2>{active.name}</h2></div><img src={active.image_url || ''} alt="" /></div>
            <form key={`${active.id}-${active.without_pads_price}-${active.with_pads_price}-${active.stock_quantity}`} noValidate onSubmit={save}>
              <div className="field-grid"><label className="wide">Product name<input name="name" required minLength={2} maxLength={200} defaultValue={active.name} /></label>
                <label>Standard price (₹)<input name="without_pads_price" type="number" min="0.01" max="1000000" step="0.01" required defaultValue={active.without_pads_price ?? active.price} /></label>
                <label>With-pads price (₹, optional)<input name="with_pads_price" type="number" min="0.01" max="1000000" step="0.01" defaultValue={active.with_pads_price ?? ''} /></label>
                <label>Available stock<input name="stock_quantity" type="number" min="0" max="1000000" step="1" required defaultValue={active.stock_quantity} /></label>
                <label className="wide">Short description<textarea name="short_description" rows={2} maxLength={1000} defaultValue={active.short_description || ''} /></label>
                <label className="wide">Description<textarea name="description" rows={4} maxLength={5000} defaultValue={active.description || ''} /></label>
                <label className="wide">Fabric details<textarea name="fabric_details" rows={2} maxLength={2000} defaultValue={active.fabric_details || ''} /></label>
                <label className="wide">Care instructions<textarea name="care_instructions" rows={2} maxLength={2000} defaultValue={active.care_instructions || ''} /></label>
              </div>
              <div className="catalog-toggles">{[
                ['is_active', 'Visible in store', active.is_active],
                ['is_new_arrival', 'New arrival', active.is_new_arrival],
                ['is_best_seller', 'Bestseller', active.is_best_seller],
                ['is_featured', 'Featured', active.is_featured],
              ].map(([name, label, checked]) => <label key={String(name)} className="confirm-check"><input name={String(name)} type="checkbox" defaultChecked={Boolean(checked)} /><span className="confirm-check-box" aria-hidden="true"><Check size={15} /></span><span>{label}</span></label>)}</div>
              {error && <p className="notice error" role="alert">{error}</p>}{message && <p className="notice" role="status">{message}</p>}
              <button type="submit" className="button button-primary" disabled={busy}><Save size={17} aria-hidden="true" /> {busy ? 'Saving…' : 'Save changes'}</button>
            </form>
            <button type="button" className="catalog-history-toggle" aria-expanded={showHistory} onClick={() => setShowHistory(!showHistory)}><History size={17} aria-hidden="true" /> Recent changes ({history.length})</button>
            {showHistory && <div className="catalog-history">{history.length ? history.map(row => <p key={row.id}><strong>{new Date(row.created_at).toLocaleString('en-IN')}</strong> · Editor #{row.editor_user_id}<br />Price {formatPrice(Number(row.before.sale_price ?? row.before.price))} → {formatPrice(Number(row.after.sale_price ?? row.after.price))}; stock {String(row.before.stock_quantity)} → {String(row.after.stock_quantity)}</p>) : <p>No catalog changes recorded yet.</p>}</div>}
          </> : <div className="empty-state"><h2>Select a product</h2><p>Choose a piece from the list to edit its price, stock or details.</p></div>}
        </div>
      </div>
    </div></section>
  </main>;
}
