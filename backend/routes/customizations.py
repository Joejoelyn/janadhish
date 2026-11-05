from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import CustomRequest, User
from ..schemas import CustomRequestCreate

router = APIRouter()


@router.post('/api/customizations')
def create_customization(
    request_data: CustomRequestCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if not request_data.garment_category:
        raise HTTPException(status_code=400, detail='Garment category is required')

    custom_request = CustomRequest(
        user_id=current_user.id if current_user else None,
        session_id='guest' if current_user is None else None,
        garment_category=request_data.garment_category,
        fabric_name=request_data.fabric_name,
        design_name=request_data.design_name,
        measurements=request_data.measurements or {},
        preferences=request_data.preferences or {},
        special_instructions=request_data.special_instructions,
        estimated_price=float(request_data.estimated_price or 0),
    )
    db.add(custom_request)
    db.commit()
    db.refresh(custom_request)

    return {
        'id': custom_request.id,
        'garment_category': custom_request.garment_category,
        'status': custom_request.status,
        'estimated_price': custom_request.estimated_price,
    }
