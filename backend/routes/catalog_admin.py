import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth import get_current_admin_user, get_db
from ..models import Product, ProductAudit, User
from .products import serialize_product

router = APIRouter()
logger = logging.getLogger(__name__)


class ProductEdit(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    short_description: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=5000)
    fabric_details: str | None = Field(default=None, max_length=2000)
    care_instructions: str | None = Field(default=None, max_length=2000)
    without_pads_price: Decimal = Field(..., gt=0, le=1000000, decimal_places=2)
    with_pads_price: Decimal | None = Field(default=None, gt=0, le=1000000, decimal_places=2)
    stock_quantity: int = Field(..., ge=0, le=1000000)
    expected_stock_quantity: int = Field(..., ge=0, le=1000000)
    is_new_arrival: bool
    is_best_seller: bool
    is_featured: bool
    is_active: bool

    @model_validator(mode='after')
    def valid_product(self) -> 'ProductEdit':
        if not self.name.strip():
            raise ValueError('Product name is required')
        if self.with_pads_price is not None and self.with_pads_price <= self.without_pads_price:
            raise ValueError('With-pads price must be greater than the standard price')
        return self


def audit_snapshot(product: Product) -> dict[str, str | float | int | bool | None]:
    return {
        'name': product.name,
        'short_description': product.short_description,
        'description': product.description,
        'fabric_details': product.fabric_details,
        'care_instructions': product.care_instructions,
        'price': product.price,
        'sale_price': product.sale_price,
        'stock_quantity': product.stock_quantity,
        'is_new_arrival': product.is_new_arrival,
        'is_best_seller': product.is_best_seller,
        'is_featured': product.is_featured,
        'is_active': product.is_active,
    }


@router.get('/api/admin/products')
def list_admin_products(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)) -> list[dict[str, object]]:
    del admin
    return [serialize_product(product) for product in db.query(Product).order_by(Product.name).all()]


@router.put('/api/admin/products/{product_id}')
def edit_product(product_id: int, payload: ProductEdit, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)) -> dict[str, object]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail='Product not found')
    before = audit_snapshot(product)
    try:
        changed = db.execute(
            update(Product)
            .where(Product.id == product_id, Product.stock_quantity == payload.expected_stock_quantity)
            .values(stock_quantity=payload.stock_quantity)
        )
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail='Available stock changed. Refresh products before saving.')
        db.refresh(product)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not reserve catalog stock update for product %s', product_id)
        raise HTTPException(status_code=503, detail='Could not save product') from exc
    product.name = payload.name.strip()
    product.short_description = payload.short_description.strip() if payload.short_description else None
    product.description = payload.description.strip() if payload.description else None
    product.fabric_details = payload.fabric_details.strip() if payload.fabric_details else None
    product.care_instructions = payload.care_instructions.strip() if payload.care_instructions else None
    product.price = float(payload.with_pads_price or payload.without_pads_price)
    product.sale_price = float(payload.without_pads_price) if payload.with_pads_price is not None else None
    product.stock_quantity = payload.stock_quantity
    product.is_new_arrival = payload.is_new_arrival
    product.is_best_seller = payload.is_best_seller
    product.is_featured = payload.is_featured
    product.is_active = payload.is_active
    after = audit_snapshot(product)
    try:
        if before != after:
            db.add(ProductAudit(product_id=product.id, editor_user_id=admin.id, before=before, after=after))
        db.commit()
        db.refresh(product)
        return serialize_product(product)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not update product %s', product_id)
        raise HTTPException(status_code=503, detail='Could not save product') from exc


@router.get('/api/admin/products/{product_id}/history')
def product_history(product_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)) -> list[dict[str, object]]:
    del admin
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail='Product not found')
    rows = db.query(ProductAudit).filter_by(product_id=product_id).order_by(ProductAudit.created_at.desc()).limit(20).all()
    return [{
        'id': row.id, 'editor_user_id': row.editor_user_id, 'before': row.before,
        'after': row.after, 'created_at': row.created_at.isoformat(),
    } for row in rows]
