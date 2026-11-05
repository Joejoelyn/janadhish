import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import Order, OrderItem, Product, User
from ..schemas import OrderCreate

router = APIRouter()


def parse_customization_details(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


@router.post('/api/orders')
def create_order(payload: OrderCreate, db: Session = Depends(get_db), current_user: User | None = Depends(get_current_user)):
    if not payload.cart_items:
        raise HTTPException(status_code=400, detail='Cart is empty')

    subtotal = 0
    order_items = []
    for item in payload.cart_items:
        product = db.query(Product).filter(Product.id == item.get('product_id')).first()
        if not product:
            continue
        item_total = float(product.sale_price or product.price) * int(item.get('quantity', 1))
        subtotal += item_total
        order_items.append({
            'product_id': product.id,
            'product_name': product.name,
            'size': item.get('size'),
            'color': item.get('color'),
            'quantity': int(item.get('quantity', 1)),
            'unit_price': float(product.sale_price or product.price),
            'customization_details': item.get('customization_details'),
        })

    shipping_fee = 0 if subtotal >= 3000 else 250
    total = subtotal + shipping_fee

    order = Order(
        user_id=current_user.id if current_user else None,
        customer_name=payload.customer_name,
        email=payload.email,
        phone=payload.phone,
        shipping_address=payload.shipping_address,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        country=payload.country,
        shipping_method=payload.shipping_method,
        payment_method=payload.payment_method,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        discount=0,
        total=total,
        status='pending',
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    for item_data in order_items:
        order_item = OrderItem(order_id=order.id, **item_data)
        db.add(order_item)

    db.commit()

    return {'message': 'Order created successfully', 'order_id': order.id, 'total': total, 'status': order.status}


@router.get('/api/orders/my-orders')
def my_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    orders = db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc()).all()
    return [
        {
            'id': order.id,
            'customer_name': order.customer_name,
            'status': order.status,
            'total': order.total,
            'created_at': order.created_at.isoformat(),
            'items': [
                {
                    'product_name': item.product_name,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'size': item.size,
                    'color': item.color,
                    'customization_details': parse_customization_details(item.customization_details),
                }
                for item in order.items
            ],
        }
        for order in orders
    ]
