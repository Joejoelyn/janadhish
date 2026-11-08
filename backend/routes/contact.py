import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth import get_db
from ..models import ContactMessage, ContactUpdate
from ..schemas import ContactCreate

router = APIRouter()
logger = logging.getLogger(__name__)


class ContactTracking(BaseModel):
    tracking_token: str = Field(..., min_length=16, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')


@router.post('/api/contact')
def submit_contact_form(payload: ContactCreate, db: Session = Depends(get_db)):
    entry = ContactMessage(
        name=payload.name,
        email=payload.email.lower(),
        phone=payload.phone,
        subject=payload.subject,
        message=payload.message,
        public_token=secrets.token_urlsafe(24),
    )
    try:
        db.add(entry)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not save contact message')
        raise HTTPException(status_code=503, detail='Could not send your message. Please try again.') from exc
    return {
        'message': 'Your message has been received.',
        'ticket_number': f'JD-{entry.id:06d}',
        'tracking_token': entry.public_token,
    }


@router.post('/api/contact/status')
def contact_status(payload: ContactTracking, db: Session = Depends(get_db)) -> dict:
    entry = db.query(ContactMessage).filter_by(public_token=payload.tracking_token).first()
    if entry is None:
        raise HTTPException(status_code=404, detail='Request not found')
    return {
        'ticket_number': f'JD-{entry.id:06d}',
        'status': entry.status,
        'created_at': entry.created_at.isoformat(),
        'updates': [{
            'status': item.status,
            'reply': item.reply,
            'created_at': item.created_at.isoformat(),
        } for item in db.query(ContactUpdate).filter(
            ContactUpdate.contact_id == entry.id, ContactUpdate.reply.is_not(None),
        ).order_by(ContactUpdate.created_at.asc(), ContactUpdate.id.asc()).all()],
    }
