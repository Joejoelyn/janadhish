from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth import get_current_admin_user, get_db
from ..models import CheckoutAttempt, Fulfillment, Order, PaymentReference, PaymentRefund, PaymentReview, Product, User, utc_now

router = APIRouter()
logger = logging.getLogger(__name__)


class PaymentSubmission(BaseModel):
    reference: str = Field(..., min_length=8, max_length=60, pattern=r'^[A-Za-z0-9-]+$')
    payer_name: str = Field(..., min_length=2, max_length=150)


class PaymentToken(BaseModel):
    checkout_token: str = Field(..., min_length=16, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')


class PaymentSubmissionRequest(PaymentSubmission, PaymentToken):
    pass


class PaymentDecision(BaseModel):
    decision: Literal['approve', 'reject', 'cancel']
    statement_reference: str | None = None
    statement_amount_paise: int | None = None
    statement_checked: bool = False
    note: str | None = Field(default=None, max_length=1000)
    statement_checked_no_payment: bool = False


class RefundRecord(BaseModel):
    amount_paise: int = Field(..., gt=0)
    outgoing_reference: str = Field(..., min_length=8, max_length=100, pattern=r'^[A-Za-z0-9/_-]+$')
    reason: str = Field(..., min_length=5, max_length=1000)
    transfer_confirmed: bool = False


def refund_history(db: Session, order_id: int) -> list[dict]:
    rows = db.query(PaymentRefund).filter_by(order_id=order_id).order_by(PaymentRefund.created_at.asc(), PaymentRefund.id.asc()).all()
    return [{
        'id': row.id, 'amount_paise': row.amount_paise,
        'outgoing_reference': row.outgoing_reference, 'reason': row.reason,
        'created_at': row.created_at.isoformat(),
    } for row in rows]


def payment_response(db: Session, order: Order, attempt: CheckoutAttempt) -> dict:
    fulfillment = db.query(Fulfillment).filter_by(order_id=order.id).first() if order.status == 'paid' else None
    return {
        'order_id': order.id,
        'total': order.total,
        'status': order.status,
        'payment_method': order.payment_method,
        'checkout_token': attempt.public_token,
        'payment_reference': attempt.payment_reference,
        'review_note': attempt.review_note,
        'refunded_amount_paise': order.refunded_amount_paise,
        'refunds': refund_history(db, order.id) if order.refunded_amount_paise else [],
        'fulfillment': ({
            'status': fulfillment.status if fulfillment else 'processing',
            'carrier': fulfillment.carrier if fulfillment else None,
            'tracking_reference': fulfillment.tracking_reference if fulfillment else None,
        } if order.status == 'paid' else None),
        'upi': {'qr_image_url': '/assets/images/payments/janadhish-upi.jpeg', 'payee_name': 'Kiran Lodha'},
    }


def get_attempt(db: Session, token: str) -> CheckoutAttempt:
    attempt = db.query(CheckoutAttempt).filter_by(public_token=token).first()
    if attempt is None:
        raise HTTPException(status_code=404, detail='Checkout not found')
    return attempt


@router.get('/api/payments/{token}')
def payment_status(token: str, db: Session = Depends(get_db)):
    attempt = get_attempt(db, token)
    return payment_response(db, db.get(Order, attempt.order_id), attempt)


@router.post('/api/payments/{token}/submit')
def submit_payment(token: str, payload: PaymentSubmission, db: Session = Depends(get_db)):
    attempt = get_attempt(db, token)
    if attempt.status not in ('awaiting_payment', 'cancellation_requested', 'payment_submitted'):
        raise HTTPException(status_code=409, detail='This order cannot accept a payment reference')
    reference = payload.reference.upper()
    if len(payload.payer_name.strip()) < 2:
        raise HTTPException(status_code=400, detail='Enter the name shown on the payment')
    if attempt.status == 'payment_submitted':
        if attempt.payment_reference == reference:
            return payment_response(db, db.get(Order, attempt.order_id), attempt)
        raise HTTPException(status_code=409, detail='A reference is already under review. Contact support or wait for the review result.')
    try:
        db.add(PaymentReference(attempt_id=attempt.id, reference=reference))
        db.flush()
        changed = db.execute(update(CheckoutAttempt).where(
            CheckoutAttempt.id == attempt.id,
            CheckoutAttempt.status == attempt.status,
        ).values(status='payment_submitted'))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail='Order status changed. Refresh and try again.')
        attempt.payment_reference = reference
        attempt.payer_name = payload.payer_name.strip()
        attempt.submitted_at = utc_now()
        attempt.review_note = None
        attempt.status = 'payment_submitted'
        order = db.get(Order, attempt.order_id)
        order.status = 'payment_submitted'
        db.commit()
        return payment_response(db, order, attempt)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='This transaction reference has already been submitted') from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not submit payment reference')
        raise HTTPException(status_code=503, detail='Could not submit payment reference') from exc


def release_stock(db: Session, order: Order) -> None:
    for item in order.items:
        db.execute(update(Product).where(Product.id == item.product_id).values(stock_quantity=Product.stock_quantity + item.quantity))


@router.post('/api/payments/{token}/cancel')
def cancel_unpaid_order(token: str, db: Session = Depends(get_db)):
    attempt = get_attempt(db, token)
    if attempt.status == 'cancellation_requested':
        return payment_response(db, db.get(Order, attempt.order_id), attempt)
    if attempt.status != 'awaiting_payment':
        raise HTTPException(status_code=409, detail='Payment was submitted or this order is closed. Contact support for help.')
    try:
        changed = db.execute(update(CheckoutAttempt).where(CheckoutAttempt.id == attempt.id, CheckoutAttempt.status == 'awaiting_payment').values(status='cancellation_requested'))
        if changed.rowcount != 1:
            raise HTTPException(status_code=409, detail='Order status changed. Refresh and try again.')
        order = db.get(Order, attempt.order_id)
        order.status = 'cancellation_requested'
        db.commit()
        return payment_response(db, order, attempt)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not cancel unpaid order')
        raise HTTPException(status_code=503, detail='Could not cancel order') from exc


@router.post('/api/payments/status')
def payment_status_private(payload: PaymentToken, db: Session = Depends(get_db)) -> dict:
    return payment_status(payload.checkout_token, db)


@router.post('/api/payments/submit')
def submit_payment_private(payload: PaymentSubmissionRequest, db: Session = Depends(get_db)) -> dict:
    return submit_payment(payload.checkout_token, payload, db)


@router.post('/api/payments/cancel')
def cancel_unpaid_order_private(payload: PaymentToken, db: Session = Depends(get_db)) -> dict:
    return cancel_unpaid_order(payload.checkout_token, db)


@router.get('/api/admin/payments')
def list_payments(
    view: Literal['review', 'awaiting', 'closed'] = Query(default='review'),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> dict:
    del admin
    statuses = (
        ['payment_submitted'] if view == 'review'
        else ['cancellation_requested', 'awaiting_payment'] if view == 'awaiting'
        else ['paid', 'cancelled']
    )
    query = db.query(CheckoutAttempt).filter(CheckoutAttempt.status.in_(statuses))
    if view == 'review':
        query = query.order_by(CheckoutAttempt.submitted_at.asc(), CheckoutAttempt.id.asc())
    elif view == 'awaiting':
        query = query.order_by(case((CheckoutAttempt.status == 'cancellation_requested', 0), else_=1), CheckoutAttempt.created_at.asc(), CheckoutAttempt.id.asc())
    else:
        query = query.order_by(CheckoutAttempt.reviewed_at.desc(), CheckoutAttempt.id.desc())
    attempts = query.offset(offset).limit(limit + 1).all()
    visible = attempts[:limit]
    orders = {order.id: order for order in db.query(Order).filter(Order.id.in_([attempt.order_id for attempt in visible])).all()} if visible else {}
    reviews: dict[int, list[dict]] = {attempt.id: [] for attempt in visible}
    refunds: dict[int, list[dict]] = {attempt.order_id: [] for attempt in visible}
    if visible:
        for review in db.query(PaymentReview).filter(PaymentReview.attempt_id.in_(reviews)).order_by(PaymentReview.created_at.asc(), PaymentReview.id.asc()).all():
            reviews[review.attempt_id].append({
                'decision': review.decision, 'reference': review.reference,
                'note': review.note, 'created_at': review.created_at.isoformat(),
            })
        for refund in db.query(PaymentRefund).filter(PaymentRefund.order_id.in_(refunds)).order_by(PaymentRefund.created_at.asc(), PaymentRefund.id.asc()).all():
            refunds[refund.order_id].append({
                'id': refund.id, 'amount_paise': refund.amount_paise,
                'outgoing_reference': refund.outgoing_reference, 'reason': refund.reason,
                'created_at': refund.created_at.isoformat(),
            })
    return {'items': [{
        'order_id': attempt.order_id,
        'customer_name': order.customer_name,
        'email': order.email,
        'total': order.total,
        'status': order.status,
        'payment_reference': attempt.payment_reference,
        'payer_name': attempt.payer_name,
        'submitted_at': attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        'created_at': attempt.created_at.isoformat(),
        'review_note': attempt.review_note,
        'reviews': reviews[attempt.id],
        'refunded_amount_paise': order.refunded_amount_paise,
        'refunds': refunds[order.id],
    } for attempt in visible for order in [orders[attempt.order_id]]],
        'has_more': len(attempts) > limit,
    }


@router.post('/api/admin/payments/{order_id}/refunds')
def record_refund(
    order_id: int, payload: RefundRecord,
    db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user),
) -> dict:
    attempt = db.query(CheckoutAttempt).filter_by(order_id=order_id).first()
    if attempt is None:
        raise HTTPException(status_code=404, detail='Order not found')
    if attempt.status != 'paid':
        raise HTTPException(status_code=409, detail='Only verified paid orders can have a recorded refund')
    if not payload.transfer_confirmed:
        raise HTTPException(status_code=400, detail='Confirm the refund was completed through the bank or UPI app')
    if len(payload.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail='Enter a refund reason')
    try:
        changed = db.execute(update(Order).where(
            Order.id == order_id, Order.status == 'paid',
            Order.refunded_amount_paise + payload.amount_paise <= attempt.amount_paise,
        ).values(refunded_amount_paise=Order.refunded_amount_paise + payload.amount_paise))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail='Refund exceeds the verified order amount or order changed')
        refund = PaymentRefund(
            order_id=order_id, amount_paise=payload.amount_paise,
            outgoing_reference=payload.outgoing_reference.upper(),
            reason=payload.reason.strip(), recorded_by_user_id=admin.id,
        )
        db.add(refund)
        db.commit()
        return {'id': refund.id, 'refunded_amount_paise': db.get(Order, order_id).refunded_amount_paise}
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='This outgoing refund reference was already recorded') from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not record refund for order %s', order_id)
        raise HTTPException(status_code=503, detail='Could not record refund') from exc


@router.post('/api/admin/payments/{order_id}/review')
def review_payment(order_id: int, payload: PaymentDecision, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    attempt = db.query(CheckoutAttempt).filter_by(order_id=order_id).first()
    if attempt is None:
        raise HTTPException(status_code=404, detail='Order not found')
    if payload.decision == 'approve':
        if attempt.status != 'payment_submitted':
            raise HTTPException(status_code=409, detail='No pending payment submission')
        if not payload.statement_checked:
            raise HTTPException(status_code=400, detail='Confirm the receiving bank statement was checked')
        if (payload.statement_reference or '').upper() != attempt.payment_reference or payload.statement_amount_paise != attempt.amount_paise:
            raise HTTPException(status_code=400, detail='Bank statement reference and exact amount must match this order')
        expected_status = 'payment_submitted'
        next_status = 'paid'
    else:
        if not payload.note or not payload.note.strip():
            raise HTTPException(status_code=400, detail='A review note is required')
        expected_status = 'payment_submitted' if payload.decision == 'reject' else attempt.status
        if payload.decision == 'cancel' and expected_status not in ('awaiting_payment', 'cancellation_requested', 'payment_submitted'):
            raise HTTPException(status_code=409, detail='This order cannot be cancelled')
        if payload.decision == 'cancel' and not payload.statement_checked_no_payment:
            raise HTTPException(status_code=400, detail='Check the receiving account before cancelling the order')
        next_status = 'awaiting_payment' if payload.decision == 'reject' else 'cancelled'
    try:
        changed = db.execute(update(CheckoutAttempt).where(CheckoutAttempt.id == attempt.id, CheckoutAttempt.status == expected_status).values(status=next_status))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail='Order status changed. Refresh and try again.')
        order = db.get(Order, order_id)
        order.status = next_status
        reviewed_reference = attempt.payment_reference
        attempt.review_note = payload.note.strip() if payload.note else None
        attempt.reviewed_at = utc_now()
        attempt.reviewed_by_user_id = admin.id
        if payload.decision == 'reject':
            attempt.payment_reference = None
            attempt.payer_name = None
            attempt.submitted_at = None
        if next_status == 'cancelled':
            release_stock(db, order)
        db.add(PaymentReview(
            attempt_id=attempt.id, reviewer_user_id=admin.id, decision=payload.decision,
            reference=reviewed_reference, note=attempt.review_note,
        ))
        db.commit()
        return payment_response(db, order, attempt)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not review payment')
        raise HTTPException(status_code=503, detail='Could not review payment') from exc
