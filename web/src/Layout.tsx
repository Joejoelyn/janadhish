import { useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { Check, Heart, Menu, Search, ShoppingBag, Sparkles, UserRound, X } from 'lucide-react';
import { api, formatPrice, getUser, priceOf } from './lib';
import type { CartItem, Product } from './types';

const navigation = [
  ['/', 'Home'], ['/shop', 'Shop All'], ['/shop?sort=new', 'New Arrivals'],
  ['/shop?sort=bestseller', 'Bestsellers'], ['/custom-made', 'Custom-Made'],
  ['/about', 'About'], ['/contact', 'Contact'],
];

export function Layout({ children, cartCount, addedItem, dismissAdded }: {
  children: ReactNode; cartCount: number;
  addedItem: { product: Product; item: CartItem } | null;
  dismissAdded: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [searchError, setSearchError] = useState('');
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessage, setChatMessage] = useState('');
  const [chatReply, setChatReply] = useState('');
  const [chatBusy, setChatBusy] = useState(false);
  const [allowExternalAi, setAllowExternalAi] = useState(false);
  const [sessionUser, setSessionUser] = useState(getUser);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const update = () => setSessionUser(getUser());
    window.addEventListener('janadhish-session-change', update);
    return () => window.removeEventListener('janadhish-session-change', update);
  }, []);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    if (!search.trim()) { setSearchError('Enter a product, fabric or style to search.'); return; }
    navigate(`/shop?search=${encodeURIComponent(search.trim())}`); setSearchOpen(false); setMenuOpen(false); setSearchError('');
  };
  const askStylist = async (event: FormEvent) => {
    event.preventDefault();
    if (!chatMessage.trim()) { setChatReply('Enter a question about the collection.'); return; }
    setChatBusy(true);
    try { const data = await api<{ response: string }>('/api/ai/chat', { method: 'POST', body: JSON.stringify({ message: chatMessage.trim(), allow_external_ai: allowExternalAi }) }); setChatReply(data.response); }
    catch (error) { setChatReply(error instanceof Error ? error.message : 'Assistant unavailable'); }
    finally { setChatBusy(false); }
  };

  return <>
    <div className="announcement"><span>Thoughtful pieces, made for you</span><span>Complimentary shipping above ₹3,000</span></div>
    <header className="site-header">
      <div className="header-main container">
        <button className="icon-button mobile-menu-button" type="button" aria-label={menuOpen ? 'Close menu' : 'Open menu'} aria-expanded={menuOpen} aria-controls="main-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={20} /> : <Menu size={20} />}</button>
        <Link to="/" className="brand-mark" aria-label="JANADHISH home"><img src="/Images/logo/logo.png" alt="JANADHISH" /></Link>
        <nav id="main-navigation" className={`main-nav ${menuOpen ? 'open' : ''}`} aria-label="Main navigation">
          {navigation.map(([href, label]) => <Link key={href} to={href} aria-current={`${location.pathname}${location.search}` === href ? 'page' : undefined} onClick={() => setMenuOpen(false)}>{label}</Link>)}
          <Link className="mobile-nav-link" to="/account" onClick={() => setMenuOpen(false)}><UserRound size={18} /> My account</Link>
          <Link className="mobile-nav-link" to="/account?section=wishlist" onClick={() => setMenuOpen(false)}><Heart size={18} /> Wishlist</Link>
          <button className="mobile-nav-link mobile-nav-button" type="button" onClick={() => { setChatOpen(true); setMenuOpen(false); }}><Sparkles size={18} aria-hidden="true" /> Ask our stylist</button>
        </nav>
        <div className="header-actions">
          <button className="icon-button" type="button" aria-label={searchOpen ? 'Close search' : 'Search products'} aria-expanded={searchOpen} onClick={() => setSearchOpen(!searchOpen)}>{searchOpen ? <X size={20} /> : <Search size={20} />}</button>
          <Link className="icon-button account-link" to="/account" aria-label="My account"><UserRound size={20} /></Link>
          <Link className="icon-button wishlist-link" to="/account?section=wishlist" aria-label="Wishlist"><Heart size={20} /></Link>
          <Link className="icon-button cart-link" to="/cart" aria-label={`Shopping bag, ${cartCount} ${cartCount === 1 ? 'item' : 'items'}`}><ShoppingBag size={20} /><span className="cart-count" key={cartCount}>{cartCount}</span></Link>
        </div>
      </div>
      {searchOpen && <form className="search-bar container" noValidate onSubmit={submitSearch}><label className="sr-only" htmlFor="site-search">Search products</label><input id="site-search" autoFocus type="search" value={search} onChange={event => { setSearch(event.target.value); setSearchError(''); }} placeholder="Search clothing, fabric or style" />{searchError && <p className="search-error" role="alert">{searchError}</p>}<button type="submit" className="button button-primary">Search</button></form>}
      {sessionUser?.is_admin && <nav className="admin-toolbar" aria-label="Store administration"><div className="container"><span>Store admin</span><Link to="/admin/payments" aria-current={location.pathname === '/admin/payments' ? 'page' : undefined}>Payment review</Link><Link to="/admin/fulfillment" aria-current={location.pathname === '/admin/fulfillment' ? 'page' : undefined}>Paid orders</Link><Link to="/admin/inbox" aria-current={location.pathname === '/admin/inbox' ? 'page' : undefined}>Customer inbox</Link><Link to="/admin/catalog" aria-current={location.pathname === '/admin/catalog' ? 'page' : undefined}>Catalog</Link></div></nav>}
    </header>
    {addedItem && <aside className="added-to-bag" aria-label="Added to bag" aria-live="polite">
      <div className="added-to-bag-heading"><span><Check size={17} aria-hidden="true" /> Added to your bag</span><button type="button" aria-label="Close bag confirmation" onClick={dismissAdded}><X size={19} /></button></div>
      <div className="added-to-bag-product"><img src={addedItem.product.image_url || ''} alt="" /><div><strong>{addedItem.product.name}</strong><p>{[addedItem.item.size, addedItem.item.color, addedItem.item.with_pads ? 'With pads' : 'Without pads'].filter(Boolean).join(' · ')}</p><span>{addedItem.item.quantity} × {formatPrice(priceOf(addedItem.product, Boolean(addedItem.item.with_pads)))}</span></div></div>
      <div className="added-to-bag-actions"><Link className="button button-primary" to="/cart" onClick={dismissAdded}>View bag ({cartCount})</Link><button className="button button-outline" type="button" onClick={dismissAdded}>Keep shopping</button></div>
    </aside>}
    {children}
    <footer className="site-footer"><div className="container footer-grid">
      <div><Link to="/" className="brand-mark"><img src="/Images/logo/logo.png" alt="JANADHISH" /></Link><p>Clothing that makes room for your story.</p></div>
      <div><h3>Explore</h3><Link to="/shop">Shop All</Link><Link to="/shop?sort=new">New Arrivals</Link><Link to="/shop?sort=bestseller">Bestsellers</Link><Link to="/custom-made">Custom-Made</Link></div>
      <div><h3>Help</h3><Link to="/contact">Contact</Link><Link to="/faq">FAQ</Link><Link to="/shipping-policy">Shipping & Returns</Link></div>
      <div><h3>JANADHISH</h3><Link to="/about">Our Story</Link><Link to="/privacy-policy">Privacy</Link><Link to="/terms">Terms</Link></div>
    </div><div className="container footer-assistant"><button type="button" className="stylist-trigger" onClick={() => setChatOpen(!chatOpen)} aria-label="Ask our stylist" aria-expanded={chatOpen}><Sparkles size={18} aria-hidden="true" /> <span>Ask our stylist</span></button></div><div className="container footer-bottom"><span>© 2026 JANADHISH</span><span>Made with care in India</span></div></footer>
    {chatOpen && <section className="stylist-panel" aria-label="Shopping assistant"><div className="stylist-title"><strong>JANADHISH stylist</strong><button type="button" aria-label="Close assistant" onClick={() => setChatOpen(false)}><X size={20} /></button></div><p>Ask about pieces in our collection. Avoid personal or payment details.</p><label className="confirm-check stylist-consent"><input type="checkbox" checked={allowExternalAi} onChange={event => setAllowExternalAi(event.target.checked)} /><span className="confirm-check-box" aria-hidden="true"><Check size={15} /></span><span>Allow an external AI provider to process my question for product advice.</span></label>{chatReply && <p className="stylist-reply" role="status">{chatReply}</p>}<form onSubmit={askStylist}><label className="sr-only" htmlFor="stylist-question">Your question</label><input id="stylist-question" value={chatMessage} maxLength={500} onChange={event => setChatMessage(event.target.value)} placeholder="What are you looking for?" /><button type="submit" disabled={chatBusy}>{chatBusy ? '...' : 'Send'}</button></form></section>}
  </>;
}

export function AdminAccess({ purpose }: { purpose: string }) {
  const location = useLocation();
  return <main className="simple-page"><h1>Access restricted</h1><p>Sign in with an administrator account to {purpose}.</p><Link to={`/login?returnTo=${encodeURIComponent(location.pathname)}`} className="button button-primary">Sign in</Link></main>;
}

export function Banner({ eyebrow, title, description }: { eyebrow: string; title: string; description?: string }) {
  return <section className="page-banner"><div className="container"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{description && <p className="banner-description">{description}</p>}</div></section>;
}

export function Status({ loading, error }: { loading: boolean; error: string }) {
  if (loading) return <p className="notice" role="status">Loading the collection…</p>;
  if (error) return <p className="notice error" role="alert">{error}. Please refresh the page.</p>;
  return null;
}
