from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_db
from ..models import ContactMessage
from ..schemas import ContactCreate

router = APIRouter()


@router.post('/api/contact')
def submit_contact_form(payload: ContactCreate, db: Session = Depends(get_db)):
    entry = ContactMessage(
        name=payload.name,
        email=payload.email.lower(),
        phone=payload.phone,
        subject=payload.subject,
        message=payload.message,
    )
    db.add(entry)
    db.commit()
    return {'message': 'Your message has been received. We will get back to you soon.'}
