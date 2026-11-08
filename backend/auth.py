from __future__ import annotations

import hashlib
import hmac
import logging
import math
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import bcrypt
from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import LoginThrottle, User

if os.getenv('APP_ENV') == 'production' and not os.getenv('SECRET_KEY'):
    raise RuntimeError('SECRET_KEY is required in production')
SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_urlsafe(48)
if os.getenv('APP_ENV') == 'production' and len(SECRET_KEY) < 32:
    raise RuntimeError('SECRET_KEY must be at least 32 characters in production')
ALGORITHM = os.getenv('ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '1440'))
LOGIN_ATTEMPT_LIMIT = 10
LOGIN_ATTEMPT_WINDOW = timedelta(minutes=5)
logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def login_throttle_key(email: str) -> str:
    return hmac.new(SECRET_KEY.encode(), email.casefold().encode(), hashlib.sha256).hexdigest()


def consume_login_attempt(db: Session, email: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - LOGIN_ATTEMPT_WINDOW
    key = login_throttle_key(email)
    dialect = db.get_bind().dialect.name
    if dialect == 'postgresql':
        insert = postgresql_insert
    elif dialect == 'sqlite':
        insert = sqlite_insert
    else:
        raise HTTPException(status_code=503, detail='Sign-in temporarily unavailable')
    try:
        db.execute(delete(LoginThrottle).where(LoginThrottle.window_started_at <= cutoff))
        statement = insert(LoginThrottle).values(key_hash=key, attempts=1, window_started_at=now)
        stale = LoginThrottle.window_started_at <= cutoff
        statement = statement.on_conflict_do_update(
            index_elements=[LoginThrottle.key_hash],
            set_={
                'attempts': case((stale, 1), else_=LoginThrottle.attempts + 1),
                'window_started_at': case((stale, now), else_=LoginThrottle.window_started_at),
            },
        ).returning(LoginThrottle.attempts, LoginThrottle.window_started_at)
        attempts, started_at = db.execute(statement).one()
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not enforce sign-in attempt limit')
        raise HTTPException(status_code=503, detail='Sign-in temporarily unavailable') from exc
    if attempts > LOGIN_ATTEMPT_LIMIT:
        retry_after = max(1, math.ceil((started_at + LOGIN_ATTEMPT_WINDOW - now).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail='Too many sign-in attempts. Try again shortly.',
            headers={'Retry-After': str(retry_after)},
        )


def clear_login_attempts(db: Session, email: str) -> None:
    try:
        db.execute(delete(LoginThrottle).where(LoginThrottle.key_hash == login_throttle_key(email)))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Could not clear sign-in attempt limit')
        raise HTTPException(status_code=503, detail='Sign-in temporarily unavailable') from exc


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('ascii'))
    except (ValueError, UnicodeEncodeError):
        return False


def hash_password(password: str) -> str:
    encoded = password.encode('utf-8')
    if len(encoded) > 72:
        raise HTTPException(status_code=400, detail='Password is too long')
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode('ascii')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({'exp': expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    if not credentials or not credentials.credentials:
        return None

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM], options={'require': ['exp', 'sub']},
        )
        user_id = payload.get('sub')
        if not user_id or not str(user_id).isdigit():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
    except (jwt.PyJWTError, HTTPException) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token') from exc

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')
    return user


def get_current_user(current_user: User | None = Depends(get_optional_current_user)) -> User:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    return current_user


def get_current_admin_user(
    current_user: User = Depends(get_current_user),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Admin access required')
    try:
        token_admin = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM], options={'require': ['exp', 'sub']},
        ).get('admin') is True
    except (AttributeError, jwt.PyJWTError):
        token_admin = False
    if not token_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Sign in again for admin access')
    return current_user
