from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import CartItem, Product, User
from ..schemas import CartItemCreate

router = APIRouter()


@router.post('/api/cart')
def add_to_cart(item: CartItemCreate, db: Session = Depends(get_db), current_user: User | None = Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == item.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')

    if item.quantity <= 0:
        raise HTTPException(status_code=400, detail='Quantity must be greater than zero')

    cart_item = db.query(CartItem).filter(
        CartItem.user_id == (current_user.id if current_user else None),
        CartItem.product_id == item.product_id,
        CartItem.size == item.size,
        CartItem.color == item.color,
    ).first()

    if cart_item:
        cart_item.quantity += item.quantity
    else:
        cart_item = CartItem(
            user_id=current_user.id if current_user else None,
            session_id='guest' if current_user is None else None,
            product_id=item.product_id,
            product_name=product.name,
            size=item.size,
            color=item.color,
            quantity=item.quantity,
            unit_price=float(product.sale_price or product.price),
        )
        db.add(cart_item)

    db.commit()
    db.refresh(cart_item)
    return {'message': 'Item added to cart', 'cart_item': {'id': cart_item.id, 'quantity': cart_item.quantity}}


@router.get('/api/cart')
def get_cart(db: Session = Depends(get_db), current_user: User | None = Depends(get_current_user)):
    user_id = current_user.id if current_user else None
    cart_items = db.query(CartItem).filter(CartItem.user_id == user_id).all() if user_id else []
    subtotal = sum((item.unit_price * item.quantity) for item in cart_items)
    return {'items': [
        {
            'id': item.id,
            'product_id': item.product_id,
            'product_name': item.product_name,
            'size': item.size,
            'color': item.color,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'image_url': item.product.image_url,
        }
        for item in cart_items
    ], 'subtotal': subtotal, 'shipping': 0, 'total': subtotal}
