import logging
from math import isfinite

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth import get_db, get_optional_current_user
from ..models import CustomRequest, Design, Fabric, User
from ..schemas import CustomRequestCreate

router = APIRouter()
logger = logging.getLogger(__name__)
MEASUREMENT_LABELS = {
    'Saree': ('Waist', 'Hips', 'Shoulder to waist', 'Saree length', 'Pallu length'),
    'Kurta': ('Chest', 'Waist', 'Hips', 'Shoulder', 'Sleeve length', 'Kurta length'),
    'Anarkali': ('Bust', 'Waist', 'Hip', 'Shoulder', 'Sleeve length', 'Gown length'),
    'Fusion Set': ('Bust', 'Waist', 'Hip', 'Shoulder', 'Trouser waist', 'Pant length'),
    'Gown': ('Bust', 'Waist', 'Hip', 'Shoulder', 'Sleeve length', 'Gown length'),
}


@router.post('/api/customizations')
def create_customization(
    request_data: CustomRequestCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    contact_name = request_data.contact_name or (current_user.full_name if current_user else None)
    contact_email = request_data.contact_email or (current_user.email if current_user else None)
    if not contact_name or not contact_email:
        raise HTTPException(status_code=400, detail='Name and email are required so we can discuss your request')
    expected = set(MEASUREMENT_LABELS[request_data.garment_category])
    if set(request_data.measurements) != expected or any(
        not isfinite(value) or value <= 0 or value > 300 for value in request_data.measurements.values()
    ):
        raise HTTPException(status_code=400, detail='Complete the measurements for your garment')
    if not db.query(Fabric).filter(Fabric.name == request_data.fabric_name, Fabric.is_active.is_(True)).first():
        raise HTTPException(status_code=400, detail='Choose an available fabric')
    if not db.query(Design).filter(Design.name == request_data.design_name, Design.is_active.is_(True)).first():
        raise HTTPException(status_code=400, detail='Choose an available design')
    unit = request_data.preferences.get('measurement_unit', 'inches')
    style = request_data.preferences.get('style', '')
    if unit not in ('inches', 'cm') or not isinstance(style, str) or len(style) > 1000:
        raise HTTPException(status_code=400, detail='Invalid style preferences or measurement unit')
    preferences = {'style': style.strip(), 'measurement_unit': unit, 'contact': {
        'name': contact_name.strip(), 'email': str(contact_email).lower(),
        'phone': request_data.contact_phone or (current_user.phone if current_user else None),
    }}

    custom_request = CustomRequest(
        user_id=current_user.id if current_user else None,
        session_id='guest' if current_user is None else None,
        garment_category=request_data.garment_category,
        fabric_name=request_data.fabric_name,
        design_name=request_data.design_name,
        measurements=request_data.measurements or {},
        preferences=preferences,
        special_instructions=request_data.special_instructions,
        estimated_price=0,
    )
    try:
        db.add(custom_request)
        db.commit()
        db.refresh(custom_request)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not save custom request')
        raise HTTPException(status_code=503, detail='Could not send your request. Please try again.') from exc

    return {
        'id': custom_request.id,
        'garment_category': custom_request.garment_category,
        'status': custom_request.status,
        'estimated_price': custom_request.estimated_price,
    }
