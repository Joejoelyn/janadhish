import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user, get_db
from ..models import CartItem, Product, User
from ..schemas import CartItemCreate
from ..services.pricing import product_variant_prices

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post('/api/cart')
def add_to_cart(
    item: CartItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    product = db.query(Product).filter(
        Product.id == item.product_id, Product.is_active.is_(True),
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail='Product is unavailable')

    sizes = product.sizes.split(',') if product.sizes else []
    colors = product.colors.split(',') if product.colors else []
    if (sizes or item.size) and item.size not in sizes:
        raise HTTPException(status_code=400, detail='Invalid size for this piece')
    if (colors or item.color) and item.color not in colors:
        raise HTTPException(status_code=400, detail='Invalid colour for this piece')
    quantity_in_cart = db.query(func.coalesce(func.sum(CartItem.quantity), 0)).filter(
        CartItem.user_id == current_user.id, CartItem.product_id == item.product_id,
    ).scalar()
    if quantity_in_cart + item.quantity > product.stock_quantity:
        raise HTTPException(status_code=409, detail='Requested quantity exceeds available stock')

    cart_item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.product_id == item.product_id,
        CartItem.size == item.size,
        CartItem.color == item.color,
    ).first()

    if cart_item:
        cart_item.quantity += item.quantity
    else:
        cart_item = CartItem(
            user_id=current_user.id,
            product_id=item.product_id,
            product_name=product.name,
            size=item.size,
            color=item.color,
            quantity=item.quantity,
            unit_price=product_variant_prices(product)[0],
        )
        db.add(cart_item)

    try:
        db.commit()
        db.refresh(cart_item)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not update cart for user %s', current_user.id)
        raise HTTPException(status_code=503, detail='Could not update cart') from exc
    return {'message': 'Item added to cart', 'cart_item': {'id': cart_item.id, 'quantity': cart_item.quantity}}


@router.get('/api/cart')
def get_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    cart_items = db.query(CartItem).options(joinedload(CartItem.product)).filter(
        CartItem.user_id == current_user.id,
    ).all()
    prices = {item.id: product_variant_prices(item.product)[0] for item in cart_items}
    subtotal = round(sum(prices[item.id] * item.quantity for item in cart_items), 2)
    shipping = 0 if subtotal >= 3000 or subtotal == 0 else 250
    return {'items': [
        {
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product_name,
            'size': item.size,
            'color': item.color,
            'quantity': item.quantity,
            'unit_price': prices[item.id],
            'image_url': item.product.image_url,
        }
        for item in cart_items
    ], 'subtotal': subtotal, 'shipping': shipping, 'total': subtotal + shipping}
