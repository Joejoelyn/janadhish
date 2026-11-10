from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_db
from ..models import Category, Product, ProductImage
from ..services.pricing import product_variant_prices

router = APIRouter()
PRODUCT_IMAGE_ROOT = (Path(__file__).resolve().parents[2] / 'frontend' / 'Images' / 'products').resolve()


@router.get('/media/products/{product_id}/{image_id}.webp')
def product_image(product_id: int, image_id: int, request: Request, db: Session = Depends(get_db)) -> Response:
    image = db.query(ProductImage).filter_by(id=image_id, product_id=product_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail='Image not found')
    headers = {'ETag': f'"{image.sha256}"', 'Cache-Control': 'public, max-age=31536000, immutable'}
    if request.headers.get('if-none-match') == headers['ETag']:
        return Response(status_code=304, headers=headers)
    return Response(content=image.content, media_type='image/webp', headers=headers)


@lru_cache(maxsize=512)
def storefront_image_url(url: str | None) -> str | None:
    if not url:
        return url
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or not parts.path.startswith('/Images/products/'):
        return url
    source = Path(unquote(parts.path.lstrip('/')))
    if source.suffix.lower() not in {'.png', '.jpg', '.jpeg'}:
        return url
    target = (PRODUCT_IMAGE_ROOT.parent.parent / source).with_suffix('.webp').resolve()
    if not target.is_relative_to(PRODUCT_IMAGE_ROOT) or not target.is_file():
        return url
    webp_path = parts.path[:-len(source.suffix)] + '.webp'
    return urlunsplit(('', '', webp_path, parts.query, parts.fragment))


def product_prices(product: Product) -> dict[str, float | None]:
    without_pads, with_pads = product_variant_prices(product)
    return {
        'without_pads_price': without_pads,
        'with_pads_price': with_pads,
    }


def serialize_product(product: Product) -> dict[str, object]:
    return {
        'id': product.id,
        'sku': product.sku,
        'name': product.name,
        'short_description': product.short_description,
        'description': product.description,
        'fabric_details': product.fabric_details,
        'care_instructions': product.care_instructions,
        'price': float(product.price),
        'sale_price': float(product.sale_price) if product.sale_price is not None else None,
        **product_prices(product),
        'sizes': product.sizes.split(',') if product.sizes else [],
        'colors': product.colors.split(',') if product.colors else [],
        'category': {'id': product.category.id, 'name': product.category.name, 'slug': product.category.slug} if product.category else None,
        'stock_quantity': product.stock_quantity,
        'image_url': storefront_image_url(product.image_url),
        'gallery': [storefront_image_url(image) for image in product.gallery.split(',')] if product.gallery else [],
        'is_new_arrival': product.is_new_arrival,
        'is_best_seller': product.is_best_seller,
        'is_featured': product.is_featured,
        'is_active': product.is_active,
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
    effective_price = func.coalesce(Product.sale_price, Product.price)

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
        query = query.filter(effective_price >= min_price)
    if max_price is not None:
        query = query.filter(effective_price <= max_price)

    if sort == 'price_asc':
        query = query.order_by(effective_price.asc())
    elif sort == 'price_desc':
        query = query.order_by(effective_price.desc())
    elif sort == 'featured':
        query = query.order_by(Product.is_featured.desc(), Product.created_at.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    products = query.all()
    return [serialize_product(product) for product in products]


@router.get('/api/products/{product_id}')
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')

    return serialize_product(product)
