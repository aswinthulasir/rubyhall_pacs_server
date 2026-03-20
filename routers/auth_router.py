"""
routers/auth_router.py — Authentication endpoints.

Routes:
    POST /auth/register  — Create a new user account
    POST /auth/login     — Exchange credentials for a JWT
    GET  /auth/me        — Return the currently authenticated user's profile
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import config
from database import get_db
from models import User, Role
from schemas import UserRegister, UserOut, Token
from auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ─── Register ──────────────────────────────────────────────────────────────────
@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """
    Create a new user account.
    Returns the created user's public profile (no password hash).
    """
    # Ensure username is unique
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Ensure email is unique
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Validate role
    role = db.query(Role).filter(Role.id == payload.role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role ID {payload.role_id} does not exist",
        )

    new_user = User(
        username        = payload.username,
        email           = payload.email,
        full_name       = payload.full_name,
        hashed_password = hash_password(payload.password),
        role_id         = payload.role_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ─── Login ─────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Authenticate with username + password (form data).
    Returns a Bearer JWT on success.
    """
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is disabled",
        )

    token = create_access_token(
        data={
            "sub"     : user.username,
            "user_id" : user.id,
            "role_id" : user.role_id,
        },
        expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer"}


# ─── Current user profile ──────────────────────────────────────────────────────
@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of the authenticated user."""
    return current_user