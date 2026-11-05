async function fetchAuth(url, payload) {
  const response = await fetch(`${API_BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || 'Authentication failed');
  }
  return data;
}

function setSession(token, user) {
  localStorage.setItem('janadhishToken', token);
  localStorage.setItem('janadhishUser', JSON.stringify(user));
}

document.addEventListener('DOMContentLoaded', () => {
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      try {
        const data = await fetchAuth('/api/auth/login', {
          email: document.getElementById('loginEmail').value,
          password: document.getElementById('loginPassword').value,
        });
        setSession(data.access_token, data.user);
        window.location.href = '/account';
      } catch (error) {
        alert(error.message);
      }
    });
  }

  const registerForm = document.getElementById('registerForm');
  if (registerForm) {
    registerForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      try {
        const data = await fetchAuth('/api/auth/register', {
          full_name: document.getElementById('registerName').value,
          email: document.getElementById('registerEmail').value,
          phone: document.getElementById('registerPhone').value,
          password: document.getElementById('registerPassword').value,
        });
        setSession(data.access_token, data.user);
        window.location.href = '/account';
      } catch (error) {
        alert(error.message);
      }
    });
  }

  const logoutButton = document.getElementById('logoutButton');
  if (logoutButton) {
    logoutButton.addEventListener('click', () => {
      localStorage.removeItem('janadhishToken');
      localStorage.removeItem('janadhishUser');
      window.location.href = '/login';
    });
  }

  const accountProfile = document.getElementById('accountProfile');
  const ordersList = document.getElementById('ordersList');
  if (accountProfile) {
    const user = JSON.parse(localStorage.getItem('janadhishUser') || 'null');
    if (!user) {
      window.location.href = '/login';
      return;
    }
    accountProfile.innerHTML = `<p><strong>Name:</strong> ${user.full_name}</p><p><strong>Email:</strong> ${user.email}</p><p><strong>Phone:</strong> ${user.phone || 'Not provided'}</p>`;
  }

  if (ordersList) {
    const token = localStorage.getItem('janadhishToken');
    if (!token) {
      ordersList.innerHTML = '<p>Please log in to view order history.</p>';
      return;
    }
    fetch(`${API_BASE}/api/orders/my-orders`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(async response => {
      if (!response.ok) throw new Error('Order history unavailable');
      const orders = await response.json();
      ordersList.innerHTML = orders.length ? orders.map(order => `
        <div class="summary-box">
          <p><strong>Order #${order.id}</strong></p>
          <p>Status: ${order.status}</p>
          <p>Total: ${formatPrice(order.total)}</p>
        </div>
      `).join('') : '<p>No orders yet.</p>';
    }).catch(() => {
      ordersList.innerHTML = '<p>Your order history will appear here after your first purchase.</p>';
    });
  }
});
