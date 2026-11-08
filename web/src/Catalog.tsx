import { useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { Heart, Minus, Plus, X } from 'lucide-react';
import { Banner, Status } from './Layout';
import { ThemeSelect } from './ThemeSelect';
import { formatPrice, priceOf } from './lib';
import type { CartItem, Measurements, Product } from './types';

type CatalogProps = {
  products: Product[]; loading: boolean; error: string;
  add: (item: CartItem) => boolean; wishlist: number[]; toggleWishlist: (id: number) => void;
};

function ProductCard({ product, add, wishlist, toggleWishlist }: { product: Product } & Pick<CatalogProps, 'add' | 'wishlist' | 'toggleWishlist'>) {
  const [addStatus, setAddStatus] = useState<'added' | 'full' | ''>('');
  const feedbackTimer = useRef<number | null>(null);
  useEffect(() => () => { if (feedbackTimer.current !== null) window.clearTimeout(feedbackTimer.current); }, []);
  const addItem = () => {
    const added = add({ product_id: product.id, quantity: 1, size: product.sizes.includes('M') ? 'M' : product.sizes[0] || null, color: product.colors[0] || null, with_pads: false });
    setAddStatus(added ? 'added' : 'full');
    if (feedbackTimer.current !== null) window.clearTimeout(feedbackTimer.current);
    feedbackTimer.current = window.setTimeout(() => { setAddStatus(''); feedbackTimer.current = null; }, 2200);
  };
  return <article className="product-card">
    <div className="product-card-media"><Link to={`/product/${product.id}`} aria-label={`View ${product.name}`}><img src={product.image_url || '/assets/images/logo/brand-mark.svg'} alt={product.name} loading="lazy" /></Link>{product.is_new_arrival && <span className="product-badge">Just in</span>}<button type="button" className={`heart-button ${wishlist.includes(product.id) ? 'selected' : ''}`} aria-label={wishlist.includes(product.id) ? `Remove ${product.name} from wishlist` : `Save ${product.name} to wishlist`} aria-pressed={wishlist.includes(product.id)} onClick={() => toggleWishlist(product.id)}><Heart size={19} fill={wishlist.includes(product.id) ? 'currentColor' : 'none'} /></button></div>
    <div className="product-card-copy"><p className="product-category">{product.category?.name || 'Collection'}</p><h3><Link to={`/product/${product.id}`}>{product.name}</Link></h3><p className="product-description">{product.short_description}</p><div className="product-price"><strong>{formatPrice(priceOf(product))}</strong>{product.with_pads_price != null && <span>With pads {formatPrice(product.with_pads_price)}</span>}</div><div className="product-actions"><button type="button" className="button button-primary" disabled={product.stock_quantity < 1} onClick={addItem}>{product.stock_quantity < 1 ? 'Out of stock' : addStatus === 'full' ? 'Bag limit reached' : addStatus === 'added' ? 'Added to bag ✓' : 'Add to bag'}</button><Link className="text-link" to={`/product/${product.id}`}>View details ↗</Link></div></div>
  </article>;
}

function Grid({ products, ...props }: { products: Product[] } & Pick<CatalogProps, 'add' | 'wishlist' | 'toggleWishlist'>) {
  return <div className="product-grid">{products.map(product => <ProductCard key={product.id} product={product} {...props} />)}</div>;
}

export function Home(props: CatalogProps) {
  const categories = [...new Map(props.products.filter(product => product.category).map(product => [product.category!.slug, product])).values()];
  return <main>
    <section className="hero"><div className="container hero-grid"><div className="hero-copy"><p className="eyebrow">The JANADHISH edit</p><h1>Tradition,<br /><em>tailored to you.</em></h1><p>Expressive Indian wear. Thoughtful fabrics. Pieces made for the way you move.</p><div className="hero-actions"><Link to="/shop?sort=new" className="button button-primary">Shop new arrivals ↗</Link><Link to="/custom-made" className="button button-outline">Made around you</Link></div><span className="hero-note">Comfortable clothing with a personal touch</span></div><div className="hero-image"><img src="/Images/products/green-farshi-salwar-set/photo-39.webp" alt="JANADHISH Farshi salwar set" /><span>THE FESTIVE EDIT · 01</span></div></div></section>
    <section className="section"><div className="container"><div className="section-heading"><div><p className="eyebrow">Find your style</p><h2>Shop by collection</h2></div><Link to="/shop" className="text-link">Explore all ↗</Link></div><Status loading={props.loading} error={props.error} /><div className="category-grid">{categories.map(product => <Link key={product.category!.slug} className="category-card" to={`/shop?category=${product.category!.slug}`}><img src={product.image_url || ''} alt="" loading="lazy" /><span>{product.category!.name} ↗</span></Link>)}</div></div></section>
    <section className="section section-alt"><div className="container"><div className="section-heading"><div><p className="eyebrow">Freshly made</p><h2>New arrivals</h2></div><Link to="/shop?sort=new" className="text-link">View all new pieces ↗</Link></div><Grid {...props} products={props.products.filter(product => product.is_new_arrival).slice(0, 4)} /></div></section>
    <section className="story-band"><div className="container story-grid"><div><p className="eyebrow">Our story</p><h2>A mother’s passion, stitched into a dream.</h2></div><div><p>For more than 25 years, Kiran Lodha has loved creating clothes that feel beautiful and comfortable. JANADHISH grew from that craft and from a simple idea: clothes should be made the way you like them.</p><Link to="/about" className="text-link">Discover our story ↗</Link></div></div></section>
    <section className="section"><div className="container"><div className="section-heading"><div><p className="eyebrow">Most loved</p><h2>Customer favourites</h2></div><Link to="/shop?sort=bestseller" className="text-link">See bestsellers ↗</Link></div><Grid {...props} products={props.products.filter(product => product.is_best_seller).slice(0, 4)} /></div></section>
    <section className="custom-banner"><div className="container custom-banner-grid"><img src="/Images/products/semi-chanderi-farshi-salwar-set/photo-44.webp" alt="Semi Chanderi Farshi salwar set" loading="lazy" /><div><p className="eyebrow">Fit that feels like you</p><h2>Make it yours.</h2><p>Choose a piece you love and add your measurements, or tell us what you would like us to create.</p><Link to="/custom-made" className="button button-primary">Explore custom-made ↗</Link></div></div></section>
  </main>;
}

export function Shop(props: CatalogProps) {
  const [params, setParams] = useSearchParams();
  const sort = params.get('sort') || 'newest';
  const category = params.get('category') || '';
  const search = (params.get('search') || '').trim().toLowerCase();
  const categories = [...new Map(props.products.filter(product => product.category).map(product => [product.category!.slug, product.category!])).values()];
  const setFilter = (name: string, value: string) => { const next = new URLSearchParams(params); if (value) next.set(name, value); else next.delete(name); setParams(next); };
  let shown = props.products.filter(product => (!category || product.category?.slug === category) && (!search || `${product.name} ${product.short_description || ''} ${product.fabric_details || ''}`.toLowerCase().includes(search)));
  if (sort === 'new') shown = shown.filter(product => product.is_new_arrival);
  if (sort === 'bestseller') shown = shown.filter(product => product.is_best_seller);
  if (sort === 'price_asc') shown.sort((a, b) => priceOf(a) - priceOf(b));
  if (sort === 'price_desc') shown.sort((a, b) => priceOf(b) - priceOf(a));
  if (sort === 'featured') shown.sort((a, b) => Number(b.is_featured) - Number(a.is_featured));
  return <main><Banner eyebrow="The collection" title={sort === 'new' ? 'New arrivals' : sort === 'bestseller' ? 'Most loved pieces' : 'Pieces with a point of view.'} description="Thoughtful Indian clothing for every day and every occasion." /><section className="section"><div className="container"><div className="catalog-toolbar"><div><p className="catalog-count">{props.loading ? 'Loading collection…' : `${shown.length} ${shown.length === 1 ? 'piece' : 'pieces'}`}</p>{(category || search) && <button type="button" className="clear-filters" onClick={() => setParams(sort && sort !== 'newest' ? { sort } : {})}><X size={15} aria-hidden="true" /> Clear filters</button>}</div><div className="catalog-controls"><ThemeSelect label="Collection" value={category} onChange={value => setFilter('category', value)} options={[{ value: '', label: 'All collections' }, ...categories.map(item => ({ value: item.slug, label: item.name }))]} /><ThemeSelect label="Sort by" value={sort} onChange={value => setFilter('sort', value)} options={[{ value: 'newest', label: 'All pieces' }, { value: 'new', label: 'New arrivals only' }, { value: 'bestseller', label: 'Bestsellers' }, { value: 'price_asc', label: 'Price: low to high' }, { value: 'price_desc', label: 'Price: high to low' }, { value: 'featured', label: 'Featured' }]} /></div></div><Status loading={props.loading} error={props.error} />{!props.loading && !props.error && (shown.length ? <Grid {...props} products={shown} /> : <div className="empty-state"><h2>No pieces found</h2><p>Try another search or collection.</p><Link to="/shop" className="button button-outline">View all pieces</Link></div>)}</div></section></main>;
}

export function ProductPage(props: CatalogProps & { refreshProducts: () => Promise<void> }) {
  const { id } = useParams();
  const product = props.products.find(item => item.id === Number(id));
  const [selectedImage, setSelectedImage] = useState('');
  const [size, setSize] = useState('');
  const [color, setColor] = useState('');
  const [withPads, setWithPads] = useState(false);
  const [showMeasurements, setShowMeasurements] = useState(false);
  const [unit, setUnit] = useState<'inches' | 'cm'>('inches');
  const [values, setValues] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  useEffect(() => { if (product) document.title = `${product.name} | JANADHISH`; return () => { document.title = 'JANADHISH | Tradition, tailored to you'; }; }, [product]);
  useEffect(() => {
    setSelectedImage(''); setSize(product?.sizes.includes('M') ? 'M' : product?.sizes[0] || '');
    setColor(product?.colors[0] || ''); setWithPads(false); setShowMeasurements(false);
    setUnit('inches'); setValues({}); setMessage('');
  }, [product?.id]);
  if (props.loading) return <main className="container product-layout"><Status loading error="" /></main>;
  if (props.error) return <main className="simple-page"><h1>Could not load this piece</h1><p>The collection is temporarily unavailable. Please try again.</p><button type="button" className="button button-primary" onClick={() => void props.refreshProducts()}>Retry collection</button></main>;
  if (!product) return <main className="simple-page"><h1>Piece unavailable</h1><p>This piece could not be found.</p><Link to="/shop" className="button button-primary">Shop the collection</Link></main>;
  const images = [...new Set([product.image_url, ...product.gallery].filter((value): value is string => Boolean(value)))];
  const labels = product.category?.slug === 'farshi-sets' ? ['Bust / chest', 'Top waist', 'Hip', 'Shoulder', 'Sleeve length', 'Kurta length', 'Trouser waist', 'Trouser hip', 'Inseam'] : ['Bust / chest', 'Waist', 'Hip', 'Shoulder', 'Sleeve length', 'Garment length'];
  const addItem = () => {
    const filled = labels.filter(label => values[label]?.trim());
    if (filled.length && filled.length !== labels.length) { setMessage('Complete every measurement, or leave them all blank.'); setShowMeasurements(true); return; }
    if (filled.some(label => !Number.isFinite(Number(values[label])) || Number(values[label]) < 0.1 || Number(values[label]) > 300)) { setMessage('Measurements must be between 0.1 and 300.'); return; }
    const measurements: Measurements | undefined = filled.length ? { unit, values: Object.fromEntries(labels.map(label => [label, Number(values[label])])) } : undefined;
    const added = props.add({ product_id: product.id, quantity: 1, size: size || product.sizes[0] || null, color: color || product.colors[0] || null, with_pads: withPads, ...(measurements ? { measurements } : {}) });
    setMessage(added ? `${product.name} was added to your bag.` : 'This piece has reached its bag limit or available stock.');
  };
  return <main><div className="container breadcrumb"><Link to="/shop">Shop</Link><span>/</span><span>{product.category?.name}</span><span>/</span><span>{product.name}</span></div><section className="container product-layout"><div className="gallery"><div className="gallery-main"><img src={selectedImage || images[0] || '/assets/images/logo/brand-mark.svg'} alt={product.name} /></div><div className="gallery-thumbs">{images.map((image, index) => <button key={image} type="button" aria-label={`View photo ${index + 1}`} aria-pressed={(selectedImage || images[0]) === image} onClick={() => setSelectedImage(image)}><img src={image} alt="" loading="lazy" /></button>)}</div></div><div className="purchase-panel"><p className="eyebrow">{product.category?.name || 'JANADHISH'}</p><h1>{product.name}</h1><p className="product-lead">{product.description || product.short_description}</p><p className="stock-label">{product.stock_quantity > 0 ? '● In stock' : 'Sold out'}</p><div className="selection"><h2>Finish</h2><div className="choice-row"><button type="button" className={!withPads ? 'selected' : ''} aria-pressed={!withPads} onClick={() => setWithPads(false)}>Without pads <strong>{formatPrice(priceOf(product))}</strong></button>{product.with_pads_price != null && <button type="button" className={withPads ? 'selected' : ''} aria-pressed={withPads} onClick={() => setWithPads(true)}>With pads <strong>{formatPrice(product.with_pads_price)}</strong></button>}</div></div>{product.sizes.length > 0 && <div className="selection"><h2>Size <span>{size || product.sizes[0]}</span></h2><div className="size-row">{product.sizes.map(option => <button key={option} type="button" className={(size || product.sizes[0]) === option ? 'selected' : ''} aria-pressed={(size || product.sizes[0]) === option} onClick={() => setSize(option)}>{option}</button>)}</div></div>}{product.colors.length > 0 && <div className="selection"><h2>Colour</h2><ThemeSelect label="Colour" value={color || product.colors[0]} onChange={setColor} options={product.colors.map(option => ({ value: option, label: option }))} /></div>}<div className="measurement-panel"><button type="button" aria-expanded={showMeasurements} onClick={() => setShowMeasurements(!showMeasurements)}>Add your measurements <span>{showMeasurements ? <Minus size={18} /> : <Plus size={18} />}</span></button><p>Optional. Add all measurements for a more personal fit.</p>{showMeasurements && <div className="measurement-content"><ThemeSelect label="Unit" value={unit} onChange={value => setUnit(value as 'inches' | 'cm')} options={[{ value: 'inches', label: 'Inches' }, { value: 'cm', label: 'Centimetres' }]} /><div className="measurement-grid">{labels.map(label => <label key={label}>{label}<input type="number" min="0.1" max="300" step="0.1" inputMode="decimal" value={values[label] || ''} onChange={event => setValues(current => ({ ...current, [label]: event.target.value }))} placeholder={unit === 'cm' ? 'cm' : 'in'} /></label>)}</div></div>}</div><div className="purchase-actions"><button type="button" className="button button-primary" disabled={product.stock_quantity <= 0} onClick={addItem}>Add to bag · {formatPrice(priceOf(product, withPads))}</button><button type="button" className={`button button-outline ${props.wishlist.includes(product.id) ? 'saved' : ''}`} onClick={() => props.toggleWishlist(product.id)} aria-pressed={props.wishlist.includes(product.id)}><Heart size={17} fill={props.wishlist.includes(product.id) ? 'currentColor' : 'none'} /> {props.wishlist.includes(product.id) ? 'Saved' : 'Save'}</button></div><p className="status-message" role="status">{message}</p><p className="delivery-note">Complimentary shipping on orders above ₹3,000.</p><div className="product-facts"><details><summary>Fabric & care</summary><p>{product.fabric_details || 'Please enquire for details.'}</p><p>{product.care_instructions || 'Follow garment care label.'}</p></details><details><summary>Shipping & returns</summary><p>Shipping is calculated at checkout. <Link to="/shipping-policy">Read our policy</Link>.</p></details></div></div></section><section className="section section-alt"><div className="container"><div className="section-heading"><div><p className="eyebrow">Keep exploring</p><h2>More to love</h2></div><Link to="/shop" className="text-link">View all ↗</Link></div><Grid {...props} products={props.products.filter(item => item.id !== product.id).slice(0, 4)} /></div></section></main>;
}
