"""
auth/security.py — Password hashing (bcrypt) and JWT token utilities.
All authentication logic is isolated here so no other module needs
to know about the underlying library details.
"""

from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

import config
from database import get_db
from schemas import TokenData

# ─── Password context (bcrypt) ─────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─── OAuth2 token URL ──────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ══════════════════════════════════════════════════════════════════════════════
#  Password helpers
# ══════════════════════════════════════════════════════════════════════════════

def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the plain password matches the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ══════════════════════════════════════════════════════════════════════════════
#  JWT helpers
# ══════════════════════════════════════════════════════════════════════════════

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT.
    `data` must contain at minimum: sub (username), user_id, role_id.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta if expires_delta
        else timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)


def decode_token(token: str) -> TokenData:
    """
    Decode and validate a JWT.
    Raises HTTP 401 if the token is invalid or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        username: str = payload.get("sub")
        user_id:  int = payload.get("user_id")
        role_id:  int = payload.get("role_id")
        if username is None or user_id is None:
            raise credentials_exception
        return TokenData(username=username, user_id=user_id, role_id=role_id)
    except JWTError:
        raise credentials_exception


# ══════════════════════════════════════════════════════════════════════════════
#  FastAPI Dependencies
# ══════════════════════════════════════════════════════════════════════════════

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """
    Dependency that decodes the JWT and returns the ORM User object.
    Raises HTTP 401 if token is invalid, HTTP 404 if user not found.
    """
    from models import User  # local import to avoid circular deps

    token_data = decode_token(token)
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account")
    return user


def require_doctor(current_user=Depends(get_current_user)):
    """Dependency — raises 403 if the caller is not a doctor (role_id=2)."""
    if current_user.role_id != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can perform this action",
        )
    return current_user


def require_admin(current_user=Depends(get_current_user)):
    """Dependency — raises 403 if the caller is not an admin (role_id=1)."""
    if current_user.role_id != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can perform this action",
        )
    return current_user