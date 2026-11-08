from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth import get_current_admin_user, get_db
from ..models import CheckoutAttempt, Fulfillment, FulfillmentEvent, Order, User, utc_now
from .orders import parse_customization_details

router = APIRouter()
logger = logging.getLogger(__name__)

NEXT_STATUS = {'processing': 'packed', 'packed': 'shipped', 'shipped': 'delivered'}


class FulfillmentUpdate(BaseModel):
    status: Literal['packed', 'shipped', 'delivered']
    expected_version: int = Field(..., ge=0)
    carrier: str | None = Field(default=None, max_length=100)
    tracking_reference: str | None = Field(default=None, max_length=100)

    @model_validator(mode='after')
    def check_shipping_details(self) -> 'FulfillmentUpdate':
        self.carrier = self.carrier.strip() if self.carrier else None
        self.tracking_reference = self.tracking_reference.strip() if self.tracking_reference else None
        if self.status == 'shipped' and (
            not self.carrier or len(self.carrier) < 2
            or not self.tracking_reference or len(self.tracking_reference) < 2
        ):
            raise ValueError('Carrier and tracking reference are required when marking shipped')
        if self.status != 'shipped' and (self.carrier or self.tracking_reference):
            raise ValueError('Shipping details can only be set when marking shipped')
        return self


def fulfillment_details(db: Session, order_id: int) -> dict:
    record = db.query(Fulfillment).filter_by(order_id=order_id).first()
    return {
        'status': record.status if record else 'processing',
        'carrier': record.carrier if record else None,
        'tracking_reference': record.tracking_reference if record else None,
        'version': record.version if record else 0,
        'updated_at': record.updated_at.isoformat() if record else None,
    }


@router.get('/api/admin/fulfillment')
def list_fulfillment(
    offset: int = Query(default=0, ge=0),
    view: Literal['open', 'delivered'] = Query(default='open'),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> dict:
    del admin
    query = db.query(Order).outerjoin(Fulfillment, Fulfillment.order_id == Order.id).filter(Order.status == 'paid')
    if view == 'open':
        query = query.filter((Fulfillment.id.is_(None)) | (Fulfillment.status != 'delivered'))
        query = query.order_by(Order.created_at.asc(), Order.id.asc())
    else:
        query = query.filter(Fulfillment.status == 'delivered')
        query = query.order_by(Order.created_at.desc(), Order.id.desc())
    orders = query.offset(offset).limit(51).all()
    return {
        'items': [{
            'order_id': order.id,
            'customer_name': order.customer_name,
            'email': order.email,
            'phone': order.phone,
            'shipping_address': order.shipping_address,
            'city': order.city,
            'state': order.state,
            'postal_code': order.postal_code,
            'country': order.country,
            'shipping_method': order.shipping_method,
            'total': order.total,
            'refunded_amount_paise': order.refunded_amount_paise,
            'created_at': order.created_at.isoformat(),
            'items': [{
                'name': item.product_name,
                'quantity': item.quantity,
                'size': item.size,
                'color': item.color,
                'customization_details': parse_customization_details(item.customization_details),
            } for item in order.items],
            'fulfillment': fulfillment_details(db, order.id),
        } for order in orders[:50]],
        'has_more': len(orders) > 50,
    }


@router.post('/api/admin/fulfillment/{order_id}')
def advance_fulfillment(
    order_id: int,
    payload: FulfillmentUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> dict:
    order = db.query(Order).filter_by(id=order_id).with_for_update(of=Order).first()
    if order is None:
        raise HTTPException(status_code=404, detail='Order not found')
    if order.status != 'paid':
        raise HTTPException(status_code=409, detail='Payment must be verified first')
    record = db.query(Fulfillment).filter_by(order_id=order_id).first()
    status = record.status if record else 'processing'
    version = record.version if record else 0
    if status in ('processing', 'packed'):
        attempt = db.query(CheckoutAttempt).filter_by(order_id=order_id).first()
        if attempt and order.refunded_amount_paise >= attempt.amount_paise:
            raise HTTPException(status_code=409, detail='This order was fully refunded and cannot be packed or shipped')
    if payload.expected_version != version or NEXT_STATUS.get(status) != payload.status:
        raise HTTPException(status_code=409, detail='Fulfillment changed. Refresh and try again.')
    try:
        if record is None:
            db.add(Fulfillment(order_id=order_id, status=payload.status, version=1))
        else:
            changed = db.execute(update(Fulfillment).where(
                Fulfillment.id == record.id, Fulfillment.version == version,
            ).values(status=payload.status, version=version + 1, updated_at=utc_now(),
                     carrier=payload.carrier or record.carrier,
                     tracking_reference=payload.tracking_reference or record.tracking_reference))
            if changed.rowcount != 1:
                db.rollback()
                raise HTTPException(status_code=409, detail='Fulfillment changed. Refresh and try again.')
        db.add(FulfillmentEvent(
            order_id=order_id, admin_user_id=admin.id, status=payload.status,
            carrier=payload.carrier, tracking_reference=payload.tracking_reference,
        ))
        db.commit()
        return fulfillment_details(db, order_id)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='Fulfillment changed. Refresh and try again.') from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not update fulfillment for order %s', order_id)
        raise HTTPException(status_code=503, detail='Could not update fulfillment') from exc
