let catalogProducts = [];

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
}

function createProductCard(product) {
  const withoutPads = product.without_pads_price ?? product.sale_price ?? product.price;
  const image = product.image_url || '/assets/images/logo/brand-mark.svg';
  const card = document.createElement('article');
  card.className = 'product-card';
  card.innerHTML = `
    <a class="product-card-media" href="/product/${product.id}" aria-label="View ${escapeHtml(product.name)}">
      <img src="${escapeHtml(image)}" alt="${escapeHtml(product.name)}" loading="lazy" />
      ${product.is_new_arrival ? '<span class="product-badge">Just in</span>' : ''}
    </a>
    <div class="product-card-body">
      <div class="product-meta">
        <span>${escapeHtml(product.category?.name || 'Collection')}</span>
        <span>${product.stock_quantity > 0 ? 'In stock' : 'Out of stock'}</span>
      </div>
      <h3><a href="/product/${product.id}">${escapeHtml(product.name)}</a></h3>
      <p class="product-card-description">${escapeHtml(product.short_description || '')}</p>
      <div class="product-price">
        <span>Without pads <strong>${formatPrice(withoutPads)}</strong></span>
        ${product.with_pads_price !== null && product.with_pads_price !== undefined
          ? `<span>With pads <strong>${formatPrice(product.with_pads_price)}</strong></span>`
          : ''}
      </div>
      <div class="product-actions">
        <button class="button button-primary" data-add-cart="${product.id}" ${product.stock_quantity <= 0 ? 'disabled' : ''}>Add without pads</button>
        <a class="button button-secondary" href="/product/${product.id}">Discover</a>
      </div>
    </div>
  `;

  const imageElement = card.querySelector('img');
  imageElement.addEventListener('error', () => {
    imageElement.src = '/assets/images/logo/brand-mark.svg';
  }, { once: true });
  return card;
}

function renderProductCards(container, products, emptyMessage) {
  if (!container) return;
  container.replaceChildren();
  if (!products.length) {
    const message = document.createElement('p');
    message.className = 'catalog-message';
    message.textContent = emptyMessage;
    container.append(message);
    return;
  }
  container.append(...products.map(createProductCard));
}

function renderCategories(products) {
  const container = document.getElementById('categoryGrid');
  if (!container) return;

  const categories = [...new Map(
    products.filter((product) => product.category).map((product) => [
      product.category.slug,
      { ...product.category, image: product.image_url },
    ]),
  ).values()];

  container.innerHTML = categories.map((category, index) => `
    <a class="category-card" href="/shop?category=${encodeURIComponent(category.slug)}">
      <div class="category-image">
        <img src="${escapeHtml(category.image || '/assets/images/logo/brand-mark.svg')}" alt="${escapeHtml(category.name)}" loading="lazy" />
        <span class="category-index">0${index + 1}</span>
      </div>
      <div class="category-copy">
        <h3>${escapeHtml(category.name)}</h3>
        <span>Explore collection <span aria-hidden="true">↗</span></span>
      </div>
    </a>
  `).join('');

  container.querySelectorAll('img').forEach((image) => {
    image.addEventListener('error', () => {
      image.src = '/assets/images/logo/brand-mark.svg';
    }, { once: true });
  });
}

function applyCatalogSort() {
  const container = document.getElementById('catalogGrid');
  if (!container) return;

  const sort = document.getElementById('sortSelect')?.value || 'newest';
  const params = parseQueryString();
  const search = (params.search || '').trim().toLowerCase();
  const category = params.category || '';
  let filtered = catalogProducts.filter((product) => {
    const searchable = `${product.name} ${product.short_description || ''} ${product.fabric_details || ''}`.toLowerCase();
    return (!search || searchable.includes(search)) && (!category || product.category?.slug === category);
  });

  if (sort === 'bestseller') {
    filtered = filtered.filter((product) => product.is_best_seller);
  } else if (sort === 'new') {
    filtered = filtered.filter((product) => product.is_new_arrival);
  }
  if (sort === 'newest') {
    filtered.sort((a, b) => Number(b.is_new_arrival) - Number(a.is_new_arrival));
  } else if (sort === 'price_asc') {
    filtered.sort((a, b) => Number(a.without_pads_price ?? a.price) - Number(b.without_pads_price ?? b.price));
  } else if (sort === 'price_desc') {
    filtered.sort((a, b) => Number(b.without_pads_price ?? b.price) - Number(a.without_pads_price ?? a.price));
  } else if (sort === 'featured') {
    filtered.sort((a, b) => Number(b.is_featured) - Number(a.is_featured));
  }

  renderProductCards(container, filtered, 'No pieces match those filters. Try adjusting your selection.');
  const meta = document.getElementById('catalogMeta');
  if (meta) meta.textContent = `Showing ${filtered.length} ${filtered.length === 1 ? 'piece' : 'pieces'}`;

  const query = new URLSearchParams();
  if (search) query.set('search', search);
  if (category) query.set('category', category);
  if (sort !== 'newest') query.set('sort', sort);
  const queryString = query.toString();
  const nextUrl = `${window.location.pathname}${queryString ? `?${queryString}` : ''}`;
  window.history.replaceState({}, '', nextUrl);
}

function setupCatalog(products, params) {
  if (!document.getElementById('catalogGrid')) return;

  const sortSelect = document.getElementById('sortSelect');
  if (sortSelect) {
    sortSelect.value = ['newest', 'new', 'bestseller', 'price_asc', 'price_desc', 'featured'].includes(params.sort)
      ? params.sort
      : 'newest';
    sortSelect.addEventListener('change', applyCatalogSort);
  }
  applyCatalogSort();
}

function renderProductDetail(products) {
  const summary = document.getElementById('productSummary');
  if (!summary) return;

  const productId = Number(window.location.pathname.split('/').pop());
  const product = products.find((item) => item.id === productId);
  const galleryElement = document.getElementById('productGallery');
  if (!product) {
    summary.innerHTML = '<p class="catalog-message">Product details are unavailable. Please return to the collection and choose a piece.</p>';
    return;
  }

  const gallery = product.gallery?.filter(Boolean) || [];
  if (product.image_url && !gallery.includes(product.image_url)) gallery.unshift(product.image_url);
  const galleryImages = gallery.length ? gallery : ['/assets/images/logo/brand-mark.svg'];
  const measurementLabels = product.category?.slug === 'farshi-sets'
    ? ['Bust / chest', 'Top waist', 'Hip', 'Shoulder', 'Sleeve length', 'Kurta length', 'Trouser waist', 'Trouser hip', 'Inseam']
    : ['Bust / chest', 'Waist', 'Hip', 'Shoulder', 'Sleeve length', 'Garment length'];
  summary.innerHTML = `
    <p class="eyebrow">${escapeHtml(product.category?.name || 'Signature piece')}</p>
    <h1>${escapeHtml(product.name)}</h1>
    <p class="product-detail-description">${escapeHtml(product.description || product.short_description || '')}</p>
    <div class="price-row">
      <span><small>Without pads</small>${formatPrice(product.without_pads_price ?? product.sale_price ?? product.price)}</span>
      ${product.with_pads_price !== null && product.with_pads_price !== undefined
        ? `<span><small>With pads</small>${formatPrice(product.with_pads_price)}</span>`
        : ''}
    </div>
    <section class="measurement-section" aria-labelledby="productMeasurementsTitle">
      <div class="measurement-section-heading">
        <div>
          <h2 id="productMeasurementsTitle">Your measurements</h2>
          <p>Optional — add your body measurements for a more personal fit.</p>
        </div>
        <label class="measurement-unit-control" for="productMeasurementUnit">
          <span>Unit</span>
          <select id="productMeasurementUnit" name="measurement_unit">
            <option value="inches">Inches</option>
            <option value="cm">Centimetres</option>
          </select>
        </label>
      </div>
      <div class="product-measurement-grid">
        ${measurementLabels.map((label, index) => `
          <label class="product-measurement-field" for="productMeasurement${index}">
            <span>${escapeHtml(label)}</span>
            <span class="measurement-input-wrap">
              <input id="productMeasurement${index}" type="number" min="0.1" max="300" step="0.1" inputmode="decimal" data-product-measurement="${escapeHtml(label)}" placeholder="Optional" />
              <span class="measurement-unit-suffix">in</span>
            </span>
          </label>
        `).join('')}
      </div>
      <p class="measurement-form-message" id="productMeasurementMessage" role="status" aria-live="polite"></p>
    </section>
    <div class="product-details">
      <p><strong>Fabric</strong><span>${escapeHtml(product.fabric_details || 'Please enquire for details')}</span></p>
      <p><strong>Care</strong><span>${escapeHtml(product.care_instructions || 'Follow garment care label')}</span></p>
      <p><strong>Available sizes</strong><span>${escapeHtml(product.sizes?.join(', ') || 'Available on request')}</span></p>
      <p><strong>Colour</strong><span>${escapeHtml(product.colors?.join(', ') || 'As pictured')}</span></p>
    </div>
    <p class="stock-note">${product.stock_quantity > 0 ? 'Made to be worn and loved.' : 'Currently unavailable'}</p>
    <div class="cta-row">
      <button class="button button-primary" data-product-detail-add="${product.id}" ${product.stock_quantity <= 0 ? 'disabled' : ''}>Add without pads</button>
      <a class="button button-secondary" href="/shop">Continue exploring</a>
    </div>
  `;

  summary.querySelector('#productMeasurementUnit').addEventListener('change', (event) => {
    summary.querySelectorAll('.measurement-unit-suffix').forEach((suffix) => {
      suffix.textContent = event.target.value === 'cm' ? 'cm' : 'in';
    });
  });

  if (!galleryElement) return;
  galleryElement.innerHTML = `
    <img class="product-main-image" src="${escapeHtml(galleryImages[0])}" alt="${escapeHtml(product.name)}" />
    ${galleryImages.length > 1 ? `
      <div class="product-thumbnails">
        ${galleryImages.map((image, index) => `
          <button type="button" class="product-thumbnail${index === 0 ? ' active' : ''}" data-gallery-image="${escapeHtml(image)}" aria-label="View product photo ${index + 1}">
            <img src="${escapeHtml(image)}" alt="" loading="lazy" />
          </button>
        `).join('')}
      </div>
    ` : ''}
  `;
  galleryElement.querySelectorAll('img').forEach((image) => {
    image.addEventListener('error', () => {
      image.src = '/assets/images/logo/brand-mark.svg';
    }, { once: true });
  });
}

function addToCart(productId, quantity = 1, measurements = null) {
  const product = catalogProducts.find((item) => item.id === Number(productId));
  if (!product) {
    console.error('Cannot add a product that is missing from the loaded catalog.');
    return;
  }

  const cart = getCart();
  const measurementKey = JSON.stringify(measurements);
  const existing = cart.find((item) => (
    item.product_id === Number(productId)
    && JSON.stringify(item.measurements || null) === measurementKey
  ));
  if (existing) {
    existing.quantity += quantity;
  } else {
    const defaultSize = product.sizes?.includes('M') ? 'M' : product.sizes?.[0] || 'M';
    cart.push({
      product_id: Number(productId),
      quantity,
      size: defaultSize,
      color: product.colors?.[0] || 'Default',
      ...(measurements ? { measurements } : {}),
    });
  }
  saveCart(cart);

  let notice = document.getElementById('cartNotice');
  if (!notice) {
    notice = document.createElement('div');
    notice.id = 'cartNotice';
    notice.className = 'cart-notice';
    notice.setAttribute('role', 'status');
    document.body.append(notice);
  }
  notice.textContent = `${product.name} added to your bag.`;
  notice.classList.add('is-visible');
  window.setTimeout(() => notice.classList.remove('is-visible'), 2600);
}

document.addEventListener('click', (event) => {
  const detailAddButton = event.target.closest('[data-product-detail-add]');
  if (detailAddButton) {
    const measurementInputs = [...document.querySelectorAll('[data-product-measurement]')];
    const enteredInputs = measurementInputs.filter((input) => input.value.trim());
    const message = document.getElementById('productMeasurementMessage');
    const invalidInput = enteredInputs.find((input) => !input.checkValidity());
    if (invalidInput) {
      invalidInput.reportValidity();
      return;
    }
    if (enteredInputs.length > 0 && enteredInputs.length !== measurementInputs.length) {
      message.textContent = 'Please fill in all measurements, or leave them all blank.';
      measurementInputs.find((input) => !input.value.trim())?.focus();
      return;
    }

    message.textContent = '';
    let measurements = null;
    if (enteredInputs.length) {
      measurements = {
        unit: document.getElementById('productMeasurementUnit').value,
        values: Object.fromEntries(enteredInputs.map((input) => [input.dataset.productMeasurement, Number(input.value)])),
      };
    }
    addToCart(detailAddButton.dataset.productDetailAdd, 1, measurements);
    return;
  }

  const addButton = event.target.closest('[data-add-cart]');
  if (addButton) {
    addToCart(addButton.dataset.addCart);
    return;
  }

  const thumbnail = event.target.closest('[data-gallery-image]');
  if (thumbnail) {
    const gallery = thumbnail.closest('.product-gallery');
    const mainImage = gallery?.querySelector('.product-main-image');
    if (mainImage) mainImage.src = thumbnail.dataset.galleryImage;
    gallery?.querySelectorAll('.product-thumbnail').forEach((button) => {
      button.classList.toggle('active', button === thumbnail);
    });
  }
});

window.addEventListener('DOMContentLoaded', async () => {
  try {
    catalogProducts = await fetchJson(`${API_BASE}/api/products`);
    try {
      localStorage.setItem('janadhishProducts', JSON.stringify(catalogProducts));
    } catch (error) {
      console.warn('Product details could not be cached for checkout.', error);
    }

    const params = parseQueryString();
    renderCategories(catalogProducts);
    renderProductCards(
      document.getElementById('newArrivalsGrid'),
      catalogProducts.filter((product) => product.is_new_arrival).slice(0, 4),
      'New pieces are on their way.',
    );
    renderProductCards(
      document.getElementById('bestsellerCarousel'),
      catalogProducts.filter((product) => product.is_best_seller).slice(0, 6),
      'Our collection is being refreshed.',
    );
    setupCatalog(catalogProducts, params);
    renderProductDetail(catalogProducts);
    renderProductCards(
      document.getElementById('relatedProducts'),
      catalogProducts.filter((product) => product.id !== Number(window.location.pathname.split('/').pop())).slice(0, 4),
      'Explore the full collection for more.',
    );
  } catch (error) {
    console.error('Products unavailable', error);
    for (const id of ['categoryGrid', 'newArrivalsGrid', 'bestsellerCarousel', 'catalogGrid', 'productSummary', 'relatedProducts']) {
      const container = document.getElementById(id);
      if (container) {
        container.textContent = 'The collection could not be loaded. Please refresh the page or try again shortly.';
      }
    }
  }
});
