from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_db
from ..data.product_catalog import PRODUCT_SEED
from ..models import Category, Product

router = APIRouter()
PRODUCT_PRICES_BY_SKU = {item['sku']: item for item in PRODUCT_SEED}


def product_prices(product: Product) -> dict[str, float | None]:
    prices = PRODUCT_PRICES_BY_SKU.get(product.sku)
    if not prices:
        return {'without_pads_price': None, 'with_pads_price': None}
    return {
        'without_pads_price': float(prices['without_pads_price']),
        'with_pads_price': (
            float(prices['with_pads_price'])
            if prices.get('with_pads_price') is not None
            else None
        ),
    }


@router.get('/api/products')
def list_products(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    min_price: float | None = Query(default=None),
    max_price: float | None = Query(default=None),
    sort: str = Query(default='newest'),
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(Product.is_active == True)

    if category:
        query = query.join(Category).filter(Category.slug == category)
    if search:
        term = f'%{search.lower()}%'
        query = query.filter(
            (Product.name.ilike(term)) |
            (Product.short_description.ilike(term)) |
            (Product.fabric_details.ilike(term))
        )
    if min_price is not None:
        query = query.filter((Product.sale_price if Product.sale_price is not None else Product.price) >= min_price)
    if max_price is not None:
        query = query.filter((Product.sale_price if Product.sale_price is not None else Product.price) <= max_price)

    if sort == 'price_asc':
        query = query.order_by((Product.sale_price if Product.sale_price is not None else Product.price).asc())
    elif sort == 'price_desc':
        query = query.order_by((Product.sale_price if Product.sale_price is not None else Product.price).desc())
    elif sort == 'featured':
        query = query.order_by(Product.is_featured.desc(), Product.created_at.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    products = query.all()
    response = []
    for product in products:
        response.append({
            'id': product.id,
            'sku': product.sku,
            'name': product.name,
            'short_description': product.short_description,
            'description': product.description,
            'fabric_details': product.fabric_details,
            'care_instructions': product.care_instructions,
            'price': float(product.price),
            'sale_price': float(product.sale_price) if product.sale_price else None,
            **product_prices(product),
            'sizes': product.sizes.split(',') if product.sizes else [],
            'colors': product.colors.split(',') if product.colors else [],
            'category': {'id': product.category.id, 'name': product.category.name, 'slug': product.category.slug} if product.category else None,
            'stock_quantity': product.stock_quantity,
            'image_url': product.image_url,
            'gallery': (product.gallery or '').split(',') if product.gallery else [],
            'is_new_arrival': product.is_new_arrival,
            'is_best_seller': product.is_best_seller,
            'is_featured': product.is_featured,
            'is_active': product.is_active,
        })
    return response


@router.get('/api/products/{product_id}')
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')

    return {
        'id': product.id,
        'sku': product.sku,
        'name': product.name,
        'short_description': product.short_description,
        'description': product.description,
        'fabric_details': product.fabric_details,
        'care_instructions': product.care_instructions,
        'price': float(product.price),
        'sale_price': float(product.sale_price) if product.sale_price else None,
        **product_prices(product),
        'sizes': product.sizes.split(',') if product.sizes else [],
        'colors': product.colors.split(',') if product.colors else [],
        'category': {'id': product.category.id, 'name': product.category.name, 'slug': product.category.slug} if product.category else None,
        'stock_quantity': product.stock_quantity,
        'image_url': product.image_url,
        'gallery': (product.gallery or '').split(',') if product.gallery else [],
        'is_new_arrival': product.is_new_arrival,
        'is_best_seller': product.is_best_seller,
        'is_featured': product.is_featured,
    }
