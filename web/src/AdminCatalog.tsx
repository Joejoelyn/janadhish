import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Check, History, ImagePlus, Pencil, Plus, Save, Search } from 'lucide-react';
import { AdminAccess, Banner } from './Layout';
import { ThemeSelect } from './ThemeSelect';
import { formIssue } from './formValidation';
import { api, formatPrice, getUser, priceOf } from './lib';
import type { Product } from './types';

type CatalogAudit = {
  id: number; editor_user_id: number; before: Record<string, unknown>;
  after: Record<string, unknown>; created_at: string;
};
type Category = { id: number; name: string; slug: string };

function auditChange(row: CatalogAudit): string {
  if (!Object.keys(row.before).length) return 'Product created';
  if (row.before.image_url !== row.after.image_url) return 'Product photos replaced';
  const oldPrice = row.before.sale_price ?? row.before.price;
  const newPrice = row.after.sale_price ?? row.after.price;
  if (oldPrice !== newPrice || row.before.stock_quantity !== row.after.stock_quantity) {
    return `Price ${formatPrice(Number(oldPrice))} → ${formatPrice(Number(newPrice))}; stock ${String(row.before.stock_quantity)} → ${String(row.after.stock_quantity)}`;
  }
  return 'Product details updated';
}

function ImagePicker({ files, onChange, onError }: {
  files: File[]; onChange: (files: File[]) => void; onError: (message: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [previews, setPreviews] = useState<string[]>([]);
  useEffect(() => {
    const urls = files.map(file => URL.createObjectURL(file));
    setPreviews(urls);
    return () => urls.forEach(url => URL.revokeObjectURL(url));
  }, [files]);
  return <div className="catalog-photo-picker">
    <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" multiple tabIndex={-1} onChange={event => {
      const chosen = Array.from(event.target.files || []);
      if (chosen.length > 6 || chosen.some(file => file.size > 10 * 1024 * 1024)) {
        onError('Choose up to 6 JPEG, PNG, or WebP photos, each 10 MB or smaller.');
        onChange([]); event.target.value = ''; return;
      }
      onError(''); onChange(chosen);
    }} />
    <button type="button" className="button button-outline" onClick={() => input.current?.click()}><ImagePlus size={17} aria-hidden="true" /> Choose photos</button>
    <span>{files.length ? `${files.length} photo${files.length === 1 ? '' : 's'} selected` : '1–6 photos · JPEG, PNG or WebP'}</span>
    {previews.length > 0 && <div className="catalog-photo-previews">{previews.map((url, index) => <img key={url} src={url} alt={`Selected photo ${index + 1}`} />)}</div>}
  </div>;
}

function CatalogFields({ product, categories }: { product?: Product; categories: Category[] }) {
  return <>
    <div className="field-grid">
      <label>SKU<input name="sku" required minLength={3} maxLength={40} pattern="[A-Za-z0-9][A-Za-z0-9_-]{2,39}" title="Use 3–40 letters, numbers, hyphens or underscores" defaultValue={product?.sku || ''} /></label>
      <ThemeSelect label="Collection" name="category_id" defaultValue={product?.category?.id.toString() || ''} options={[{ value: '', label: 'Choose collection' }, ...categories.map(category => ({ value: String(category.id), label: category.name }))]} />
      <label className="wide">Product name<input name="name" required minLength={2} maxLength={200} defaultValue={product?.name || ''} /></label>
      <label>Sizes, separated by commas<input name="sizes" maxLength={600} placeholder="XS, S, M, L" defaultValue={product?.sizes.join(', ') || ''} /></label>
      <label>Colors, separated by commas<input name="colors" maxLength={600} placeholder="Blue, Cream" defaultValue={product?.colors.join(', ') || ''} /></label>
      <label>Standard price (₹)<input name="without_pads_price" type="number" min="0.01" max="1000000" step="0.01" required defaultValue={product?.without_pads_price ?? product?.price ?? ''} /></label>
      <label>With-pads price (₹, optional)<input name="with_pads_price" type="number" min="0.01" max="1000000" step="0.01" defaultValue={product?.with_pads_price ?? ''} /></label>
      <label>Available stock<input name="stock_quantity" type="number" min="0" max="1000000" step="1" required defaultValue={product?.stock_quantity ?? 0} /></label>
      <label className="wide">Short description<textarea name="short_description" rows={2} maxLength={1000} defaultValue={product?.short_description || ''} /></label>
      <label className="wide">Description<textarea name="description" rows={4} maxLength={5000} defaultValue={product?.description || ''} /></label>
      <label className="wide">Fabric details<textarea name="fabric_details" rows={2} maxLength={2000} defaultValue={product?.fabric_details || ''} /></label>
      <label className="wide">Care instructions<textarea name="care_instructions" rows={2} maxLength={2000} defaultValue={product?.care_instructions || ''} /></label>
    </div>
    <div className="catalog-toggles">{[
      ['is_active', 'Visible in store', product?.is_active ?? false],
      ['is_new_arrival', 'New arrival', product?.is_new_arrival ?? false],
      ['is_best_seller', 'Bestseller', product?.is_best_seller ?? false],
      ['is_featured', 'Featured', product?.is_featured ?? false],
    ].map(([name, label, checked]) => <label key={String(name)} className="confirm-check"><input name={String(name)} type="checkbox" defaultChecked={Boolean(checked)} /><span className="confirm-check-box" aria-hidden="true"><Check size={15} /></span><span>{label}</span></label>)}</div>
  </>;
}

export function AdminCatalog({ refreshProducts }: { refreshProducts: () => Promise<void> }) {
  const user = getUser();
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [search, setSearch] = useState('');
  const [visibility, setVisibility] = useState('all');
  const [activeId, setActiveId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [photoFiles, setPhotoFiles] = useState<File[]>([]);
  const [history, setHistory] = useState<CatalogAudit[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const editor = useRef<HTMLDivElement>(null);
  const active = creating ? undefined : products.find(product => product.id === activeId);

  const load = async () => {
    setBusy(true); setError('');
    try {
      const [items, collections] = await Promise.all([
        api<Product[]>('/api/admin/products'), api<Category[]>('/api/categories'),
      ]);
      setProducts(items); setCategories(collections);
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load products'); }
    finally { setBusy(false); }
  };
  useEffect(() => { if (user?.is_admin) void load(); }, [user?.is_admin]);

  const edit = async (product: Product) => {
    setCreating(false); setActiveId(product.id); setPhotoFiles([]); setError(''); setMessage(''); setShowHistory(false);
    try { setHistory(await api<CatalogAudit[]>(`/api/admin/products/${product.id}/history`)); }
    catch { setHistory([]); }
    requestAnimationFrame(() => { editor.current?.focus({ preventScroll: true }); editor.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
  };

  const beginCreate = () => {
    setCreating(true); setActiveId(null); setPhotoFiles([]); setError(''); setMessage(''); setShowHistory(false);
    requestAnimationFrame(() => { editor.current?.focus({ preventScroll: true }); editor.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
  };

  const options = (value: string): string[] => value.split(',').map(item => item.trim()).filter(Boolean);
  const fields = (data: FormData) => {
    const text = (name: string) => String(data.get(name) || '').trim();
    return {
      sku: text('sku'), name: text('name'), category_id: Number(text('category_id')),
      sizes: options(text('sizes')), colors: options(text('colors')),
      short_description: text('short_description') || null, description: text('description') || null,
      fabric_details: text('fabric_details') || null, care_instructions: text('care_instructions') || null,
      without_pads_price: Number(text('without_pads_price')),
      with_pads_price: text('with_pads_price') ? Number(text('with_pads_price')) : null,
      stock_quantity: Number(text('stock_quantity')),
      is_active: data.has('is_active'), is_new_arrival: data.has('is_new_arrival'),
      is_best_seller: data.has('is_best_seller'), is_featured: data.has('is_featured'),
    };
  };

  const syncProduct = async (productId: number): Promise<boolean> => {
    const [storefront, audit] = await Promise.allSettled([
      refreshProducts(), api<CatalogAudit[]>(`/api/admin/products/${productId}/history`),
    ]);
    setHistory(audit.status === 'fulfilled' ? audit.value : []);
    return storefront.status === 'fulfilled';
  };

  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const issue = formIssue(event.currentTarget);
    if (issue) { setError(issue); return; }
    const details = fields(new FormData(event.currentTarget));
    if (!categories.some(category => category.id === details.category_id)) { setError('Choose a collection.'); return; }
    if (!photoFiles.length) { setError('Choose at least one product photo.'); return; }
    if (details.with_pads_price !== null && details.with_pads_price <= details.without_pads_price) {
      setError('With-pads price must be higher than the standard price.'); return;
    }
    const body = new FormData();
    body.append('details', JSON.stringify(details));
    photoFiles.forEach(file => body.append('images', file));
    setBusy(true); setError(''); setMessage('');
    try {
      const created = await api<Product>('/api/admin/products', { method: 'POST', body });
      setProducts(current => [...current, created].sort((a, b) => a.name.localeCompare(b.name)));
      setCreating(false); setActiveId(created.id); setPhotoFiles([]);
      const synced = await syncProduct(created.id);
      setMessage(synced ? `${created.name} was added ${created.is_active ? 'and is visible in the store' : 'as a hidden draft'}.` : `${created.name} was added. Refresh the page to update the storefront view.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not add product'); }
    finally { setBusy(false); }
  };

  const replacePhotos = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!active || !photoFiles.length) { setError('Choose replacement photos.'); return; }
    const body = new FormData();
    body.append('expected_image_url', active.image_url || '');
    photoFiles.forEach(file => body.append('images', file));
    setBusy(true); setError(''); setMessage('');
    try {
      const updated = await api<Product>(`/api/admin/products/${active.id}/images`, { method: 'POST', body });
      setProducts(current => current.map(product => product.id === updated.id ? updated : product));
      setPhotoFiles([]);
      const synced = await syncProduct(updated.id);
      setMessage(synced ? `${updated.name}'s photos were replaced.` : `${updated.name}'s photos were replaced. Refresh the page to update the storefront view.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not replace photos'); }
    finally { setBusy(false); }
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!active) return;
    const issue = formIssue(event.currentTarget);
    if (issue) { setError(issue); return; }
    const data = new FormData(event.currentTarget);
    const details = fields(data);
    if (!categories.some(category => category.id === details.category_id)) { setError('Choose a collection.'); return; }
    if (details.with_pads_price !== null && details.with_pads_price <= details.without_pads_price) {
      setError('With-pads price must be higher than the standard price.'); return;
    }
    setBusy(true); setError(''); setMessage('');
    try {
      const updated = await api<Product>(`/api/admin/products/${active.id}`, {
        method: 'PUT', body: JSON.stringify({ ...details, expected_stock_quantity: active.stock_quantity }),
      });
      setProducts(current => current.map(product => product.id === updated.id ? updated : product));
      const synced = await syncProduct(updated.id);
      setMessage(synced ? `${updated.name} was saved. The storefront now shows the updated catalog.` : `${updated.name} was saved. Refresh the page to update the storefront view.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save product'); }
    finally { setBusy(false); }
  };

  const shown = products.filter(product => {
    const matches = `${product.name} ${product.sku} ${product.category?.name || ''}`.toLowerCase().includes(search.toLowerCase());
    return matches && (visibility === 'all' || (visibility === 'active') === product.is_active);
  });

  if (!user?.is_admin) return <AdminAccess purpose="manage the catalog" />;
  return <main><Banner eyebrow="Store operations" title="Catalog management" description="Add and update pieces, photos, prices and stock. Publish when each piece is ready." />
    <section className="section"><div className="container admin-catalog">
      <div className="admin-catalog-heading"><div><h2>Products</h2><p>{shown.length} shown · {products.length} total</p></div><div className="admin-catalog-actions"><button type="button" className="button button-outline" disabled={busy} onClick={() => void load()}>Refresh products</button><button type="button" className="button button-primary" disabled={busy} onClick={beginCreate}><Plus size={17} aria-hidden="true" /> Add product</button></div></div>
      {error && !active && !creating && <p className="notice error" role="alert">{error}</p>}
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
          {creating ? <><div className="admin-catalog-editor-heading"><div><p className="eyebrow">New piece</p><h2>Add a product</h2><p>Choose photos and details. Leave visibility off to save a draft.</p></div></div>
            <form key="new-product" noValidate onSubmit={create}>
              <CatalogFields categories={categories} />
              <ImagePicker files={photoFiles} onChange={setPhotoFiles} onError={setError} />
              {error && <p className="notice error" role="alert">{error}</p>}
              <button type="submit" className="button button-primary" disabled={busy}><Plus size={17} aria-hidden="true" /> {busy ? 'Adding…' : 'Add product'}</button>
            </form>
          </> : active ? <><div className="admin-catalog-editor-heading"><div><p className="eyebrow">Editing {active.sku}</p><h2>{active.name}</h2></div><img src={active.image_url || ''} alt="" /></div>
            <form key={`${active.id}-${active.without_pads_price}-${active.with_pads_price}-${active.stock_quantity}`} noValidate onSubmit={save}>
              <CatalogFields product={active} categories={categories} />
              {error && <p className="notice error" role="alert">{error}</p>}{message && <p className="notice" role="status">{message}</p>}
              <button type="submit" className="button button-primary" disabled={busy}><Save size={17} aria-hidden="true" /> {busy ? 'Saving…' : 'Save changes'}</button>
            </form>
            <div className="catalog-photo-current"><h3>Product photos</h3><div className="catalog-photo-previews">{[...new Set([active.image_url, ...active.gallery].filter((url): url is string => Boolean(url)))].map((url, index) => <img key={url} src={url} alt={`Product photo ${index + 1}`} />)}</div></div>
            <form key={`${active.id}-${active.image_url}`} className="catalog-photo-replace" onSubmit={replacePhotos}>
              <p>Choose 1–6 photos to replace the full gallery.</p>
              <ImagePicker files={photoFiles} onChange={setPhotoFiles} onError={setError} />
              <button type="submit" className="button button-outline" disabled={busy || !photoFiles.length}>Replace photos</button>
            </form>
            <button type="button" className="catalog-history-toggle" aria-expanded={showHistory} onClick={() => setShowHistory(!showHistory)}><History size={17} aria-hidden="true" /> Recent changes ({history.length})</button>
            {showHistory && <div className="catalog-history">{history.length ? history.map(row => <p key={row.id}><strong>{new Date(row.created_at).toLocaleString('en-IN')}</strong> · Editor #{row.editor_user_id}<br />{auditChange(row)}</p>) : <p>No catalog changes recorded yet.</p>}</div>}
          </> : <div className="empty-state"><h2>Select a product</h2><p>Choose a piece from the list to edit its price, stock or details.</p></div>}
        </div>
      </div>
    </div></section>
  </main>;
}
