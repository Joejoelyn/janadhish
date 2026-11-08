import { useEffect, useRef, useState } from 'react';
import { Route, Routes, useLocation } from 'react-router';
import { api, cartKey, readCart, readWishlist } from './lib';
import { Layout } from './Layout';
import { Home, ProductPage, Shop } from './Catalog';
import { Account, AdminPayments, CartPage, Checkout, Login, Register } from './Commerce';
import { AdminInbox } from './AdminInbox';
import { AdminCatalog } from './AdminCatalog';
import { AdminFulfillment } from './AdminFulfillment';
import { About, Contact, CustomMade, Faq, Policy } from './Content';
import type { CartItem, Product } from './types';

export default function App() {
  const location = useLocation();
  const [products, setProducts] = useState<Product[]>([]);
  const [catalogError, setCatalogError] = useState('');
  const [loading, setLoading] = useState(true);
  const [cart, setCart] = useState<CartItem[]>(readCart);
  const cartRef = useRef(cart);
  const [wishlist, setWishlist] = useState<number[]>(readWishlist);
  const [addedItem, setAddedItem] = useState<{ product: Product; item: CartItem } | null>(null);
  const [, setSessionRevision] = useState(0);

  const refreshProducts = async () => {
    try { setProducts(await api<Product[]>('/api/products')); setCatalogError(''); }
    catch (error) { setCatalogError(error instanceof Error ? error.message : 'Collection unavailable'); }
  };
  useEffect(() => { void refreshProducts().finally(() => setLoading(false)); }, []);
  useEffect(() => { cartRef.current = cart; localStorage.setItem('janadhishCart', JSON.stringify(cart)); }, [cart]);
  useEffect(() => { localStorage.setItem('janadhishWishlist', JSON.stringify(wishlist)); }, [wishlist]);
  useEffect(() => {
    const updateSession = () => setSessionRevision(current => current + 1);
    window.addEventListener('janadhish-session-change', updateSession);
    return () => window.removeEventListener('janadhish-session-change', updateSession);
  }, []);
  useEffect(() => { window.scrollTo(0, 0); setAddedItem(null); }, [location.pathname, location.search]);

  const updateCart = (change: (current: CartItem[]) => CartItem[]) => {
    const next = change(cartRef.current);
    cartRef.current = next;
    setCart(next);
  };
  const addToCart = (item: CartItem): boolean => {
    if (!Number.isInteger(item.quantity) || item.quantity < 1 || item.quantity > 100) return false;
    const stock = products.find(product => product.id === item.product_id)?.stock_quantity || 0;
    const count = cartRef.current.filter(existing => existing.product_id === item.product_id).reduce((total, existing) => total + existing.quantity, 0);
    const matchingLine = cartRef.current.find(existing => cartKey(existing) === cartKey(item));
    if (count + item.quantity > stock || (matchingLine?.quantity || 0) + item.quantity > 100) return false;
    updateCart(current => {
    const key = cartKey(item);
    const index = current.findIndex(existing => cartKey(existing) === key);
    if (index < 0) return [...current, item];
    return current.map((existing, position) => position === index ? { ...existing, quantity: existing.quantity + item.quantity } : existing);
    });
    const product = products.find(value => value.id === item.product_id);
    if (product) setAddedItem({ product, item });
    return true;
  };
  const changeQuantity = (index: number, delta: number) => updateCart(current => {
    const selected = current[index];
    if (!selected) return current;
    const stock = products.find(product => product.id === selected.product_id)?.stock_quantity || 0;
    const count = current.filter(item => item.product_id === selected.product_id).reduce((total, item) => total + item.quantity, 0);
    if (delta > 0 && (count + delta > stock || selected.quantity + delta > 100)) return current;
    return current.map((item, position) => position === index ? { ...item, quantity: item.quantity + delta } : item)
      .filter(item => item.quantity > 0);
  });
  const removeItem = (index: number) => updateCart(current => current.filter((_, position) => position !== index));
  const toggleWishlist = (id: number) => setWishlist(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]);

  return <Layout cartCount={cart.reduce((total, item) => total + item.quantity, 0)} addedItem={addedItem} dismissAdded={() => setAddedItem(null)}>
    <Routes>
      <Route path="/" element={<Home products={products} loading={loading} error={catalogError} add={addToCart} wishlist={wishlist} toggleWishlist={toggleWishlist} />} />
      <Route path="/shop" element={<Shop products={products} loading={loading} error={catalogError} add={addToCart} wishlist={wishlist} toggleWishlist={toggleWishlist} />} />
      <Route path="/product/:id" element={<ProductPage products={products} loading={loading} error={catalogError} refreshProducts={refreshProducts} add={addToCart} wishlist={wishlist} toggleWishlist={toggleWishlist} />} />
      <Route path="/cart" element={<CartPage products={products} cart={cart} loading={loading} catalogError={catalogError} refreshProducts={refreshProducts} changeQuantity={changeQuantity} removeItem={removeItem} />} />
      <Route path="/checkout" element={<Checkout products={products} cart={cart} loading={loading} catalogError={catalogError} clearCart={() => updateCart(() => [])} refreshProducts={refreshProducts} />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/account" element={<Account products={products} wishlist={wishlist} toggleWishlist={toggleWishlist} />} />
      <Route path="/admin/payments" element={<AdminPayments />} />
      <Route path="/admin/fulfillment" element={<AdminFulfillment />} />
      <Route path="/admin/inbox" element={<AdminInbox />} />
      <Route path="/admin/catalog" element={<AdminCatalog refreshProducts={refreshProducts} />} />
      <Route path="/about" element={<About />} />
      <Route path="/custom-made" element={<CustomMade />} />
      <Route path="/contact" element={<Contact />} />
      <Route path="/faq" element={<Faq />} />
      <Route path="/privacy-policy" element={<Policy kind="privacy" />} />
      <Route path="/terms" element={<Policy kind="terms" />} />
      <Route path="/shipping-policy" element={<Policy kind="shipping" />} />
      <Route path="*" element={<main className="simple-page"><h1>Page not found</h1><a className="button button-primary" href="/">Return home</a></main>} />
    </Routes>
  </Layout>;
}
