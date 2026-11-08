import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth import clear_login_attempts, consume_login_attempt, create_access_token, get_current_user, get_db, hash_password, verify_password
from ..models import User
from ..schemas import TokenResponse, UserLogin, UserOut, UserRegister

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post('/api/auth/register', response_model=TokenResponse)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail='User already exists')

    user = User(
        full_name=payload.full_name,
        email=payload.email.lower(),
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.flush()
        result = TokenResponse(
            access_token=create_access_token({'sub': str(user.id), 'admin': False}),
            user=UserOut(id=user.id, email=user.email, full_name=user.full_name, phone=user.phone, is_admin=user.is_admin),
        )
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail='User already exists') from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not register user')
        raise HTTPException(status_code=503, detail='Could not create account') from exc


@router.post('/api/auth/login', response_model=TokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    consume_login_attempt(db, payload.email)
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or len(payload.password.encode('utf-8')) > 72 or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')

    clear_login_attempts(db, payload.email)
    token = create_access_token(
        {'sub': str(user.id), 'admin': user.is_admin},
        expires_delta=timedelta(minutes=30) if user.is_admin else None,
    )
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, email=user.email, full_name=user.full_name, phone=user.phone, is_admin=user.is_admin),
    )


@router.get('/api/auth/me')
def get_logged_in_user(current_user: User = Depends(get_current_user)):
    return UserOut(id=current_user.id, email=current_user.email, full_name=current_user.full_name, phone=current_user.phone, is_admin=current_user.is_admin)
