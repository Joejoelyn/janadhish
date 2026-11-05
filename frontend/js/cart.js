document.addEventListener('DOMContentLoaded', () => {
  const cartItemsContainer = document.getElementById('cartItems');
  const subtotalValue = document.getElementById('subtotalValue');
  const shippingValue = document.getElementById('shippingValue');
  const discountValue = document.getElementById('discountValue');
  const totalValue = document.getElementById('totalValue');

  const cart = JSON.parse(localStorage.getItem('janadhishCart') || '[]');
  if (!cartItemsContainer) return;

  if (!cart.length) {
    cartItemsContainer.innerHTML = '<p class="empty-state">Your cart is empty. Explore the collection and add your favorite pieces.</p>';
    subtotalValue.textContent = '₹0';
    shippingValue.textContent = '₹0';
    discountValue.textContent = '₹0';
    totalValue.textContent = '₹0';
    return;
  }

  const products = JSON.parse(localStorage.getItem('janadhishProducts') || '[]');
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
  const mappedItems = cart.map(item => {
    const product = products.find(product => product.id === item.product_id) || null;
    return {
      ...item,
      name: product ? product.name : 'Product',
      image: product ? product.image_url : '/assets/images/logo/brand-mark.svg',
      price: product ? Number(product.sale_price || product.price) : 0,
    };
  });

  let subtotal = 0;
  cartItemsContainer.innerHTML = mappedItems.map((item) => {
    subtotal += item.price * item.quantity;
    const measurementDetails = item.measurements?.values
      ? Object.entries(item.measurements.values)
        .map(([label, value]) => `${escapeHtml(label)}: ${escapeHtml(value)} ${escapeHtml(item.measurements.unit === 'cm' ? 'cm' : 'in')}`)
        .join(' · ')
      : '';
    return `
      <div class="cart-item">
        <img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.name)}" />
        <div>
          <h3>${escapeHtml(item.name)}</h3>
          <p>Size: ${escapeHtml(item.size || 'Standard')} · Color: ${escapeHtml(item.color || 'Default')}</p>
          ${measurementDetails ? `<p class="cart-measurements"><strong>Measurements:</strong> ${measurementDetails}</p>` : ''}
          <div class="qty-control">
            <button data-action="decrease" data-id="${item.product_id}">−</button>
            <span>${item.quantity}</span>
            <button data-action="increase" data-id="${item.product_id}">+</button>
          </div>
        </div>
        <strong>${formatPrice(item.price * item.quantity)}</strong>
      </div>
    `;
  }).join('');

  const shipping = subtotal >= 3000 ? 0 : 250;
  const discount = 0;
  const total = subtotal + shipping - discount;

  subtotalValue.textContent = formatPrice(subtotal);
  shippingValue.textContent = formatPrice(shipping);
  discountValue.textContent = formatPrice(discount);
  totalValue.textContent = formatPrice(total);

  document.querySelectorAll('[data-action]').forEach(button => {
    button.addEventListener('click', () => {
      const id = Number(button.dataset.id);
      const action = button.dataset.action;
      const current = JSON.parse(localStorage.getItem('janadhishCart') || '[]');
      const index = current.findIndex(item => item.product_id === id);
      if (index === -1) return;
      if (action === 'increase') current[index].quantity += 1;
      if (action === 'decrease') current[index].quantity -= 1;
      if (current[index].quantity <= 0) current.splice(index, 1);
      localStorage.setItem('janadhishCart', JSON.stringify(current));
      location.reload();
    });
  });
});
