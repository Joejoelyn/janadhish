from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .data.product_catalog import PRODUCT_SEED
from .database import Base, SessionLocal, engine
from .models import Category, Design, Fabric, Product
from .routes import ai_assistant, cart, categories, contact, customizations, orders, products, users

load_dotenv(Path(__file__).resolve().parents[1] / '.env')

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / 'frontend'

app = FastAPI(title='JANADHISH', version='1.0.0', docs_url='/docs', redoc_url='/redoc')

origins = [
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

app.include_router(products.router)
app.include_router(categories.router)
app.include_router(cart.router)
app.include_router(customizations.router)
app.include_router(users.router)
app.include_router(orders.router)
app.include_router(contact.router)
app.include_router(ai_assistant.router)

app.mount('/css', StaticFiles(directory=str(FRONTEND_DIR / 'css')), name='css')
app.mount('/js', StaticFiles(directory=str(FRONTEND_DIR / 'js')), name='js')
app.mount('/assets', StaticFiles(directory=str(FRONTEND_DIR / 'assets')), name='assets')
app.mount('/Images', StaticFiles(directory=str(FRONTEND_DIR / 'Images')), name='images')


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
            product = existing_products.get(product_data['sku'])
            if product:
                for field, value in values.items():
                    setattr(product, field, value)
            else:
                db.add(Product(sku=product_data['sku'], stock_quantity=8, **values))

        for sample_sku in ('JD-1001', 'JD-2002', 'JD-3003', 'JD-4004', 'JD-5005'):
            sample_product = existing_products.get(sample_sku)
            if sample_product:
                sample_product.is_active = False
        db.commit()
    finally:
        db.close()


@app.on_event('startup')
def startup():
    Base.metadata.create_all(bind=engine)
    seed_initial_data()


@app.get('/')
def home_page():
    return FileResponse(FRONTEND_DIR / 'index.html')


@app.get('/shop')
def shop_page():
    return FileResponse(FRONTEND_DIR / 'shop.html')


@app.get('/product/{product_id}')
def product_page(product_id: int):
    return FileResponse(FRONTEND_DIR / 'product.html')


@app.get('/custom-made')
def custom_made_page():
    return FileResponse(FRONTEND_DIR / 'custom-made.html')


@app.get('/cart')
def cart_page():
    return FileResponse(FRONTEND_DIR / 'cart.html')


@app.get('/checkout')
def checkout_page():
    return FileResponse(FRONTEND_DIR / 'checkout.html')


@app.get('/login')
def login_page():
    return FileResponse(FRONTEND_DIR / 'login.html')


@app.get('/register')
def register_page():
    return FileResponse(FRONTEND_DIR / 'register.html')


@app.get('/account')
def account_page():
    return FileResponse(FRONTEND_DIR / 'account.html')


@app.get('/about')
def about_page():
    return FileResponse(FRONTEND_DIR / 'about.html')


@app.get('/contact')
def contact_page():
    return FileResponse(FRONTEND_DIR / 'contact.html')


@app.get('/faq')
def faq_page():
    return FileResponse(FRONTEND_DIR / 'faq.html')


@app.get('/privacy-policy')
def privacy_page():
    return FileResponse(FRONTEND_DIR / 'privacy.html')


@app.get('/terms')
def terms_page():
    return FileResponse(FRONTEND_DIR / 'terms.html')


@app.get('/shipping-policy')
def shipping_page():
    return FileResponse(FRONTEND_DIR / 'shipping.html')


@app.get('/api/fabrics')
def get_fabrics():
    return [
        {'id': 1, 'name': 'Cotton Silk', 'description': 'Lightweight and graceful.', 'additional_price': 350, 'image_url': '/assets/images/fabrics/cotton-silk.svg'},
        {'id': 2, 'name': 'Handloom Cotton', 'description': 'Breathable and artisan-made.', 'additional_price': 200, 'image_url': '/assets/images/fabrics/handloom-cotton.svg'},
        {'id': 3, 'name': 'Organza', 'description': 'Soft drape with a delicate finish.', 'additional_price': 450, 'image_url': '/assets/images/fabrics/organza.svg'},
    ]


@app.get('/api/designs')
def get_designs():
    return [
        {'id': 1, 'name': 'Floral Chikankari', 'description': 'Delicate floral embroidery detail.', 'image_url': '/assets/images/designs/floral-chikankari.svg'},
        {'id': 2, 'name': 'Aari Work', 'description': 'Traditional artistry with a contemporary cut.', 'image_url': '/assets/images/designs/aari-work.svg'},
        {'id': 3, 'name': 'Minimalist Block Print', 'description': 'Clean lines and warm tonality.', 'image_url': '/assets/images/designs/minimalist-block.svg'},
    ]


@app.get('/favicon.ico')
def favicon():
    return FileResponse(FRONTEND_DIR / 'assets' / 'images' / 'logo' / 'brand-mark.svg')


app.mount('/', StaticFiles(directory=str(FRONTEND_DIR), html=True), name='frontend')
