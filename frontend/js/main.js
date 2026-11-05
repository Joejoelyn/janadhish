const API_BASE = '';

function getCart() {
  try {
    return JSON.parse(localStorage.getItem('janadhishCart') || '[]');
  } catch {
    return [];
  }
}

function saveCart(items) {
  localStorage.setItem('janadhishCart', JSON.stringify(items));
  updateCartCount();
}

function updateCartCount() {
  const count = getCart().reduce((sum, item) => sum + Number(item.quantity || 0), 0);
  document.querySelectorAll('.cart-count').forEach((node) => {
    node.textContent = count;
  });
}

function formatPrice(value) {
  const amount = Number(value || 0);
  return `₹${amount.toLocaleString('en-IN')}`;
}

function parseQueryString() {
  const params = new URLSearchParams(window.location.search);
  return Object.fromEntries(params.entries());
}

document.addEventListener('DOMContentLoaded', () => {
  const searchToggle = document.getElementById('searchToggle');
  const searchWrapper = document.getElementById('searchWrapper');

  if (searchToggle && searchWrapper) {
    searchToggle.addEventListener('click', () => {
      searchWrapper.classList.toggle('hidden');
    });
  }

  const siteSearch = document.getElementById('siteSearch');
  const searchButton = document.getElementById('searchButton');
  if (siteSearch && searchButton) {
    searchButton.addEventListener('click', () => {
      const value = siteSearch.value.trim();
      if (value) {
        window.location.href = `/shop?search=${encodeURIComponent(value)}`;
      }
    });
  }

  updateCartCount();

});
