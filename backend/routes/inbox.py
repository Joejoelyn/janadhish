from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth import get_current_admin_user, get_db
from ..models import ContactMessage, ContactUpdate, CustomRequest, User

router = APIRouter()


class RequestReview(BaseModel):
    status: Literal['pending', 'reviewed', 'closed']
    note: str | None = Field(default=None, max_length=1000)


class ContactReview(BaseModel):
    status: Literal['received', 'in_progress', 'resolved']
    reply: str | None = Field(default=None, max_length=2000)


@router.get('/api/admin/contact-messages')
def contact_messages(
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user),
) -> dict:
    del admin
    query = db.query(ContactMessage)
    rows = query.order_by(
        case((ContactMessage.status == 'resolved', 1), else_=0),
        ContactMessage.created_at.desc(), ContactMessage.id.desc(),
    ).offset(offset).limit(limit + 1).all()
    updates: dict[int, list[dict]] = {row.id: [] for row in rows[:limit]}
    if updates:
        for item in db.query(ContactUpdate).filter(ContactUpdate.contact_id.in_(updates.keys())).order_by(
            ContactUpdate.created_at.asc(), ContactUpdate.id.asc(),
        ).all():
            updates[item.contact_id].append({
                'status': item.status, 'reply': item.reply,
                'reviewer_user_id': item.reviewer_user_id,
                'created_at': item.created_at.isoformat(),
            })
    return {
        'items': [{
            'id': row.id, 'name': row.name, 'email': row.email, 'phone': row.phone,
            'subject': row.subject, 'message': row.message, 'status': row.status,
            'created_at': row.created_at.isoformat(),
            'updates': updates[row.id],
        } for row in rows[:limit]],
        'has_more': len(rows) > limit,
    }


@router.post('/api/admin/contact-messages/{message_id}/review')
def review_contact_message(
    message_id: int, payload: ContactReview,
    db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user),
) -> dict:
    entry = db.get(ContactMessage, message_id)
    if entry is None:
        raise HTTPException(status_code=404, detail='Contact message not found')
    reply = (payload.reply or '').strip() or None
    if payload.status == 'resolved' and not reply and not db.query(ContactUpdate).filter(
        ContactUpdate.contact_id == message_id, ContactUpdate.reply.is_not(None),
    ).first():
        raise HTTPException(status_code=400, detail='Add a reply for the customer before resolving this ticket')
    previous_status = entry.status
    try:
        changed = db.execute(update(ContactMessage).where(
            ContactMessage.id == message_id, ContactMessage.status == previous_status,
        ).values(status=payload.status))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail='Ticket changed. Refresh and try again.')
        if previous_status != payload.status or reply:
            db.add(ContactUpdate(
                contact_id=message_id, reviewer_user_id=admin.id,
                status=payload.status, reply=reply,
            ))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail='Could not update contact message') from exc
    return {'id': entry.id, 'status': entry.status}


@router.get('/api/admin/custom-requests')
def custom_requests(
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user),
) -> dict:
    del admin
    query = db.query(CustomRequest)
    rows = query.order_by(CustomRequest.created_at.desc(), CustomRequest.id.desc()).offset(offset).limit(limit + 1).all()
    return {
        'items': [{
            'id': row.id, 'garment_category': row.garment_category, 'fabric_name': row.fabric_name,
            'design_name': row.design_name, 'measurements': row.measurements,
            'preferences': row.preferences, 'special_instructions': row.special_instructions,
            'status': row.status, 'created_at': row.created_at.isoformat(),
        } for row in rows[:limit]],
        'has_more': len(rows) > limit,
    }


@router.post('/api/admin/custom-requests/{request_id}/review')
def review_custom_request(
    request_id: int, payload: RequestReview,
    db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user),
) -> dict:
    del admin
    request = db.get(CustomRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail='Custom request not found')
    try:
        request.status = payload.status
        request.preferences = {**(request.preferences or {}), 'admin_note': (payload.note or '').strip()}
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail='Could not update request') from exc
    return {'id': request.id, 'status': request.status}
