import json
import logging
import hashlib
import secrets
from math import isfinite
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db, get_optional_current_user
from ..models import CheckoutAttempt, Fulfillment, Order, OrderItem, Product, User
from ..services.pricing import product_variant_prices
from ..schemas import CheckoutRecovery, OrderCreate
from .payments import payment_response

router = APIRouter()
logger = logging.getLogger(__name__)
STANDARD_MEASUREMENTS = frozenset(('Bust / chest', 'Waist', 'Hip', 'Shoulder', 'Sleeve length', 'Garment length'))
FARSHI_MEASUREMENTS = frozenset((
    'Bust / chest', 'Top waist', 'Hip', 'Shoulder', 'Sleeve length',
    'Kurta length', 'Trouser waist', 'Trouser hip', 'Inseam',
))


def validate_item_details(details: str | dict | None, product: Product) -> dict | None:
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = {'notes': details}
    if details is None:
        return None
    if not isinstance(details, dict):
        raise HTTPException(status_code=400, detail='Invalid customization details')
    if 'unit' in details or 'values' in details:
        values = details.get('values')
        expected = FARSHI_MEASUREMENTS if product.category and product.category.slug == 'farshi-sets' else STANDARD_MEASUREMENTS
        if (set(details) != {'unit', 'values'} or details.get('unit') not in ('inches', 'cm')
                or not isinstance(values, dict) or set(values) != expected
                or any(type(value) not in (int, float) or not isfinite(value) or value < 0.1 or value > 300
                       for value in values.values())):
            raise HTTPException(status_code=400, detail='Complete valid measurements for this piece')
    return details


def parse_customization_details(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def checkout_response(db: Session, order: Order, attempt: CheckoutAttempt) -> dict:
    return payment_response(db, order, attempt)


@router.post('/api/orders/recover')
def recover_order(payload: CheckoutRecovery, db: Session = Depends(get_db)) -> dict:
    attempt = db.query(CheckoutAttempt).filter_by(checkout_key=payload.checkout_key).first()
    if attempt is None:
        raise HTTPException(status_code=404, detail='Checkout not found')
    order = db.get(Order, attempt.order_id)
    if order is None:
        raise HTTPException(status_code=404, detail='Checkout not found')
    return checkout_response(db, order, attempt)


@router.post('/api/orders')
def create_order(payload: OrderCreate, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    if payload.country.casefold() != 'india':
        raise HTTPException(status_code=400, detail='Checkout currently supports delivery within India only')
    request_hash = hashlib.sha256(json.dumps(payload.model_dump(mode='json', exclude={'checkout_key'}), sort_keys=True).encode()).hexdigest()
    prior = db.query(CheckoutAttempt).filter_by(checkout_key=payload.checkout_key).first()
    if prior:
        if prior.request_hash != request_hash:
            raise HTTPException(status_code=409, detail='Checkout reference was already used for a different order')
        return checkout_response(db, db.get(Order, prior.order_id), prior)
    try:
        open_orders = db.query(Order).filter(Order.email == payload.email.lower(), Order.status.in_(['awaiting_payment', 'cancellation_requested', 'payment_submitted'])).count()
        if open_orders >= 3:
            raise HTTPException(status_code=429, detail='Please complete or cancel an existing order before starting another')
        product_ids = sorted({item.product_id for item in payload.cart_items})
        locked_products = db.query(Product).filter(
            Product.id.in_(product_ids), Product.is_active.is_(True),
        ).order_by(Product.id).with_for_update(of=Product).all()
        products_by_id = {product.id: product for product in locked_products}
        subtotal = 0.0
        order_items = []
        for item in payload.cart_items:
            product = products_by_id.get(item.product_id)
            if product is None:
                raise HTTPException(status_code=404, detail=f'Product {item.product_id} is unavailable')
            sizes = product.sizes.split(',') if product.sizes else []
            colors = product.colors.split(',') if product.colors else []
            if (sizes or item.size) and item.size not in sizes:
                raise HTTPException(status_code=400, detail=f'Invalid size for {product.name}')
            if (colors or item.color) and item.color not in colors:
                raise HTTPException(status_code=400, detail=f'Invalid color for {product.name}')

            without_pads_price, with_pads_price = product_variant_prices(product)
            if item.with_pads:
                if with_pads_price is None:
                    raise HTTPException(status_code=400, detail=f'Pads option unavailable for {product.name}')
                unit_price = with_pads_price
            else:
                unit_price = without_pads_price

            updated = db.execute(
                update(Product)
                .where(Product.id == product.id, Product.is_active.is_(True), Product.stock_quantity >= item.quantity)
                .values(stock_quantity=Product.stock_quantity - item.quantity)
            )
            if updated.rowcount != 1:
                raise HTTPException(status_code=409, detail=f'Insufficient stock for {product.name}')

            details = validate_item_details(item.customization_details, product)
            details = {'with_pads': item.with_pads, 'measurements': details}
            if len(json.dumps(details)) > 4000:
                raise HTTPException(status_code=400, detail='Measurement details are too large')
            order_items.append({
                'product_id': product.id,
                'product_name': product.name,
                'size': item.size,
                'color': item.color,
                'quantity': item.quantity,
                'unit_price': unit_price,
                'customization_details': json.dumps(details),
            })
            subtotal += unit_price * item.quantity

        subtotal = round(subtotal, 2)
        shipping_fee = 0 if subtotal >= 3000 else 250
        total = round(subtotal + shipping_fee, 2)
        order = Order(
            user_id=current_user.id if current_user else None,
            customer_name=payload.customer_name,
            email=payload.email.lower(),
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
            status='awaiting_payment',
        )
        db.add(order)
        db.flush()
        db.add_all(OrderItem(order_id=order.id, **item_data) for item_data in order_items)
        attempt = CheckoutAttempt(
            order_id=order.id,
            checkout_key=payload.checkout_key,
            request_hash=request_hash,
            public_token=secrets.token_urlsafe(32),
            amount_paise=int(Decimal(str(total)) * 100),
            status='awaiting_payment',
        )
        db.add(attempt)
        db.commit()
        return checkout_response(db, order, attempt)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        prior = db.query(CheckoutAttempt).filter_by(checkout_key=payload.checkout_key).first()
        if prior and prior.request_hash == request_hash:
            return checkout_response(db, db.get(Order, prior.order_id), prior)
        raise HTTPException(status_code=409, detail='Checkout could not be completed. Please retry.') from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Order creation failed')
        raise HTTPException(status_code=500, detail='Could not create order') from exc


@router.get('/api/orders/my-orders')
def my_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[dict]:
    orders = db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc()).all()
    paid_order_ids = [order.id for order in orders if order.status == 'paid']
    fulfillments = db.query(Fulfillment).filter(Fulfillment.order_id.in_(paid_order_ids)).all() if paid_order_ids else []
    fulfillment_by_order = {item.order_id: item for item in fulfillments}
    order_ids = [order.id for order in orders]
    attempts = db.query(CheckoutAttempt).filter(
        CheckoutAttempt.order_id.in_(order_ids),
    ).all() if order_ids else []
    payment_tokens = {attempt.order_id: attempt.public_token for attempt in attempts}
    return [
        {
            'id': order.id,
            'customer_name': order.customer_name,
            'status': order.status,
            'total': order.total,
            'refunded_amount_paise': order.refunded_amount_paise,
            'created_at': order.created_at.isoformat(),
            'payment_token': payment_tokens.get(order.id),
            'fulfillment': ({
                'status': fulfillment_by_order[order.id].status if order.id in fulfillment_by_order else 'processing',
                'carrier': fulfillment_by_order[order.id].carrier if order.id in fulfillment_by_order else None,
                'tracking_reference': fulfillment_by_order[order.id].tracking_reference if order.id in fulfillment_by_order else None,
            } if order.status == 'paid' else None),
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
