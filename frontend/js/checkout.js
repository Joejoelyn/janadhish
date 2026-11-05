document.addEventListener('DOMContentLoaded', () => {
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
  const summary = document.getElementById('checkoutSummary');
  const cart = JSON.parse(localStorage.getItem('janadhishCart') || '[]');
  const products = JSON.parse(localStorage.getItem('janadhishProducts') || '[]');

  let subtotal = 0;
  const items = cart.map(item => {
    const product = products.find(p => p.id === item.product_id) || null;
    const unitPrice = product ? Number(product.sale_price || product.price || 0) : 0;
    subtotal += unitPrice * item.quantity;
    return { product, unitPrice, quantity: item.quantity, measurements: item.measurements };
  });

  if (!summary) return;
  summary.innerHTML = items.map(item => `
    <div class="summary-row checkout-item">
      <span>${escapeHtml(item.product?.name || 'Custom item')} x${item.quantity}
        ${item.measurements?.values ? `<small>Measurements (${item.measurements.unit === 'cm' ? 'cm' : 'in'}): ${Object.entries(item.measurements.values).map(([label, value]) => `${escapeHtml(label)}: ${escapeHtml(value)}`).join(' · ')}</small>` : ''}
      </span>
      <strong>${formatPrice(item.unitPrice * item.quantity)}</strong>
    </div>
  `).join('') + `
    <div class="summary-row"><span>Subtotal</span><strong>${formatPrice(subtotal)}</strong></div>
    <div class="summary-row"><span>Shipping</span><strong>${formatPrice(subtotal >= 3000 ? 0 : 250)}</strong></div>
    <div class="summary-row total"><span>Total</span><strong>${formatPrice(subtotal + (subtotal >= 3000 ? 0 : 250))}</strong></div>
  `;

  const form = document.getElementById('checkoutForm');
  if (!form) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = {
      customer_name: form.elements.customer_name.value,
      email: form.elements.email.value,
      phone: form.elements.phone.value,
      shipping_address: form.elements.shipping_address.value,
      city: form.elements.city.value,
      state: form.elements.state.value,
      postal_code: form.elements.postal_code.value,
      country: form.elements.country.value,
      shipping_method: form.querySelector('input[name="shipping_method"]:checked')?.value || 'standard',
      payment_method: form.querySelector('input[name="payment_method"]:checked')?.value || 'test_mode',
      cart_items: cart.map(item => ({
        product_id: item.product_id,
        quantity: item.quantity,
        size: item.size,
        color: item.color,
        customization_details: item.measurements ? JSON.stringify(item.measurements) : null,
      })),
    };

    try {
      const response = await fetch(`${API_BASE}/api/orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Checkout failed');
      localStorage.removeItem('janadhishCart');
      alert(`Order placed successfully. Order ID: ${result.order_id}.`);
      window.location.href = '/account';
    } catch (error) {
      alert(error.message || 'Checkout failed');
    }
  });
});
