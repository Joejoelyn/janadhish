from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from collections.abc import Awaitable, Callable

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import get_db
from .data.product_catalog import PRODUCT_SEED
from .database import SessionLocal
from .models import Category, Design, Fabric, Product
from .routes import ai_assistant, cart, catalog_admin, categories, contact, customizations, fulfillment, inbox, orders, payments, products, users

load_dotenv(Path(__file__).resolve().parents[1] / '.env')

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / 'frontend'
WEB_DIST_DIR = ROOT_DIR / 'web' / 'dist'
IS_PRODUCTION = os.getenv('APP_ENV') == 'production'
mimetypes.add_type('image/webp', '.webp')

app = FastAPI(
    title='JANADHISH', version='1.0.0',
    docs_url=None if IS_PRODUCTION else '/docs',
    redoc_url=None if IS_PRODUCTION else '/redoc',
    openapi_url=None if IS_PRODUCTION else '/openapi.json',
)

origins = [] if IS_PRODUCTION else [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://127.0.0.1:5500',
    'http://localhost:5500',
    'https://janadhish.co.in',
    'https://www.janadhish.co.in',
]
configured_origins = os.getenv('FRONTEND_ORIGIN', '')
origins.extend(
    origin.strip().rstrip('/')
    for origin in configured_origins.split(',')
    if origin.strip()
)
origins = list(dict.fromkeys(origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.middleware('http')
async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if (
        request.method not in ('GET', 'HEAD')
        or request.headers.get('Authorization')
        or request.url.path.startswith(('/api/payments/', '/api/admin/', '/api/orders/', '/api/auth/'))
    ):
        response.headers['Cache-Control'] = 'no-store'
    if IS_PRODUCTION:
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
    return response

app.include_router(products.router)
app.include_router(catalog_admin.router)
app.include_router(categories.router)
app.include_router(cart.router)
app.include_router(customizations.router)
app.include_router(users.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(fulfillment.router)
app.include_router(inbox.router)
app.include_router(contact.router)
app.include_router(ai_assistant.router)

app.mount('/assets', StaticFiles(directory=str(FRONTEND_DIR / 'assets')), name='assets')
app.mount('/Images', StaticFiles(directory=str(FRONTEND_DIR / 'Images')), name='images')
if (WEB_DIST_DIR / 'app-assets').is_dir():
    app.mount('/app-assets', StaticFiles(directory=str(WEB_DIST_DIR / 'app-assets')), name='app-assets')


def storefront_page() -> FileResponse:
    built_page = WEB_DIST_DIR / 'index.html'
    if not built_page.is_file():
        raise HTTPException(status_code=503, detail='Storefront build is unavailable')
    return FileResponse(built_page)


def seed_initial_data():
    db: Session = SessionLocal()
    try:
        default_categories = [
            {'name': 'Sarees', 'slug': 'sarees', 'description': 'Elegant drapes for every occasion.'},
            {'name': 'Kurta Sets', 'slug': 'kurta-sets', 'description': 'Structured pieces for refined everyday ease.'},
            {'name': 'Fusion', 'slug': 'fusion', 'description': 'Modern silhouettes with a heritage sensibility.'},
            {'name': 'Occasion Wear', 'slug': 'occasion-wear', 'description': 'Statement styles for events and celebrations.'},
            {'name': 'Kurtis', 'slug': 'kurtis', 'description': 'Softly tailored kurtis for everyday polish.'},
            {'name': 'Tops', 'slug': 'tops', 'description': 'Everyday prints and elevated staple silhouettes.'},
            {'name': 'Farshi Sets', 'slug': 'farshi-sets', 'description': 'Statement farshi salwar sets for festive dressing.'},
        ]

        category_map = {item.slug: item for item in db.query(Category).all()}
        for data in default_categories:
            if data['slug'] not in category_map:
                db.add(Category(**data))
        db.commit()

        if db.query(Fabric).count() == 0:
            fabrics = [
                Fabric(name='Cotton Silk', description='Lightweight and graceful.', additional_price=350, image_url='/assets/images/fabrics/cotton-silk.svg'),
                Fabric(name='Handloom Cotton', description='Breathable and artisan-made.', additional_price=200, image_url='/assets/images/fabrics/handloom-cotton.svg'),
                Fabric(name='Organza', description='Soft drape with a delicate finish.', additional_price=450, image_url='/assets/images/fabrics/organza.svg'),
                Fabric(name='Maheshwari Cotton', description='Textured cotton with a premium handloom feel.', additional_price=150, image_url='/assets/images/fabrics/cotton-silk.svg'),
                Fabric(name='Pure Cotton', description='Breathable cotton designed for everyday comfort.', additional_price=100, image_url='/assets/images/fabrics/handloom-cotton.svg'),
                Fabric(name='Modal Silk', description='Smooth drape and a soft luxe finish.', additional_price=250, image_url='/assets/images/fabrics/organza.svg'),
            ]
            db.add_all(fabrics)
            db.commit()

        if db.query(Design).count() == 0:
            designs = [
                Design(name='Floral Chikankari', description='Delicate floral embroidery detail.', image_url='/assets/images/designs/floral-chikankari.svg'),
                Design(name='Aari Work', description='Traditional artistry with a contemporary cut.', image_url='/assets/images/designs/aari-work.svg'),
                Design(name='Minimalist Block Print', description='Clean lines and warm tonality.', image_url='/assets/images/designs/minimalist-block.svg'),
            ]
            db.add_all(designs)
            db.commit()

        existing_products = {product.sku: product for product in db.query(Product).all()}
        category_lookup = {item.slug: item for item in db.query(Category).all()}
        for product_data in PRODUCT_SEED:
            without_pads = float(product_data['without_pads_price'])
            with_pads = float(product_data.get('with_pads_price') or without_pads)
            values = {
                'name': product_data['name'],
                'short_description': product_data['short_description'],
                'description': product_data['description'],
                'fabric_details': product_data['fabric_details'],
                'care_instructions': product_data['care_instructions'],
                'price': max(without_pads, with_pads),
                'sale_price': without_pads if with_pads > without_pads else None,
                'sizes': product_data['sizes'],
                'colors': product_data['colors'],
                'category_id': category_lookup[product_data['category_slug']].id,
                'image_url': product_data['image_url'],
                'gallery': product_data['gallery'],
                'is_new_arrival': product_data['is_new_arrival'],
                'is_best_seller': product_data['is_best_seller'],
                'is_featured': product_data['is_featured'],
                'is_active': product_data['is_active'],
            }
            if product_data['sku'] not in existing_products:
                if product_data['sku'] in {'JD-1001', 'JD-2002', 'JD-3003', 'JD-4004', 'JD-5005'}:
                    values['is_active'] = False
                db.add(Product(sku=product_data['sku'], stock_quantity=8, **values))
        db.commit()
    finally:
        db.close()


@app.on_event('startup')
def startup():
    seed_initial_data()


@app.get('/health')
def health(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'ok': True}


@app.get('/')
def home_page():
    return storefront_page()


@app.get('/shop')
def shop_page():
    return storefront_page()


@app.get('/product/{product_id}')
def product_page(product_id: int):
    return storefront_page()


@app.get('/custom-made')
def custom_made_page():
    return storefront_page()


@app.get('/cart')
def cart_page():
    return storefront_page()


@app.get('/checkout')
def checkout_page():
    return storefront_page()


@app.get('/login')
def login_page():
    return storefront_page()


@app.get('/register')
def register_page():
    return storefront_page()


@app.get('/account')
def account_page():
    return storefront_page()


@app.get('/admin/payments')
def admin_payments_page():
    return storefront_page()


@app.get('/admin/inbox')
def admin_inbox_page():
    return storefront_page()


@app.get('/about')
def about_page():
    return storefront_page()


@app.get('/contact')
def contact_page():
    return storefront_page()


@app.get('/faq')
def faq_page():
    return storefront_page()


@app.get('/privacy-policy')
def privacy_page():
    return storefront_page()


@app.get('/terms')
def terms_page():
    return storefront_page()


@app.get('/shipping-policy')
def shipping_page():
    return storefront_page()


@app.get('/api/fabrics')
def get_fabrics(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [
        {'id': item.id, 'name': item.name, 'description': item.description,
         'additional_price': item.additional_price, 'image_url': item.image_url}
        for item in db.query(Fabric).filter(Fabric.is_active.is_(True)).order_by(Fabric.name).all()
    ]


@app.get('/api/designs')
def get_designs(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [
        {'id': item.id, 'name': item.name, 'description': item.description, 'image_url': item.image_url}
        for item in db.query(Design).filter(Design.is_active.is_(True)).order_by(Design.name).all()
    ]


@app.get('/favicon.ico')
def favicon():
    return FileResponse(FRONTEND_DIR / 'assets' / 'images' / 'logo' / 'brand-mark.svg')


@app.get('/{full_path:path}')
def react_page(full_path: str):
    if full_path.startswith('api/') or (
        IS_PRODUCTION and (full_path in {'docs', 'redoc', 'openapi.json'} or full_path.startswith('docs/'))
    ):
        raise HTTPException(status_code=404, detail='Not found')
    return storefront_page()
