"""
routers/user_router.py — User management endpoints.

Routes:
    GET  /users/         — List all users (admin only)
    GET  /users/{id}     — Get a user's public profile
    PUT  /users/{id}     — Update own profile (or admin updating any)
    GET  /users/roles    — List all roles
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User, Role
from schemas import UserOut, UserUpdate, RoleOut
from auth.security import get_current_user, require_admin

router = APIRouter(prefix="/users", tags=["Users"])


# ── List all roles ─────────────────────────────────────────────────────────────
@router.get("/roles", response_model=List[RoleOut])
def list_roles(db: Session = Depends(get_db)):
    """Public endpoint — returns all available user roles for the register form."""
    return db.query(Role).all()


# ── List all users (admin only) ───────────────────────────────────────────────
@router.get("/", response_model=List[UserOut], dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)):
    """Return all registered users. Admin access required."""
    return db.query(User).order_by(User.id).all()


# ── Get single user ────────────────────────────────────────────────────────────
@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id      : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """
    Return a user's public profile.
    Regular users can only fetch their own profile; admins can fetch anyone.
    """
    if current_user.id != user_id and current_user.role_id != 1:
        raise HTTPException(403, "You can only view your own profile")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user


# ── Update user ────────────────────────────────────────────────────────────────
@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id      : int,
    payload      : UserUpdate,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """
    Update a user profile.
    - A regular user can only update their own profile.
    - An admin can update any user (including is_active flag).
    """
    if current_user.id != user_id and current_user.role_id != 1:
        raise HTTPException(403, "You can only edit your own profile")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    if payload.email is not None:
        # Check uniqueness
        existing = db.query(User).filter(
            User.email == payload.email, User.id != user_id
        ).first()
        if existing:
            raise HTTPException(400, "Email already in use")
        user.email = payload.email

    if payload.full_name is not None:
        user.full_name = payload.full_name

    # Only admins may toggle active status
    if payload.is_active is not None and current_user.role_id == 1:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return user