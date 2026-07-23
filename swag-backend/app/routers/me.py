from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth.local_auth import CurrentUser, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User, UserRole

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("")
def get_my_access(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(UserRole).filter(UserRole.email == current.email).all()
    # Name/phone/avatar are read fresh from the database (not the JWT claims)
    # so a profile update shows up immediately, without needing to log in again.
    user = db.query(User).filter(User.email == current.email).first()
    return {
        "email": current.email,
        "name": user.name if user else current.name,
        "phone": user.phone if user else "",
        "avatar": user.avatar if user else None,
        "modules": {r.module: {"role": r.role, "branches": r.branches} for r in rows},
        # A branch-restricted admin (e.g. admin of just their own branch's
        # inventory) should NOT get the global Access Management panel -
        # that would let them grant/revoke access for the whole system.
        # Only an unrestricted (all-branches) admin role counts here.
        "is_admin_anywhere": any(r.role == "admin" and not r.branches for r in rows),
    }


class ProfileUpdateIn(BaseModel):
    name: str = ""
    phone: str = ""
    avatar: str | None = None  # base64 data URI, already resized client-side


@router.put("/profile")
def update_profile(payload: ProfileUpdateIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == current.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.name = payload.name.strip() or user.name
    user.phone = payload.phone.strip()
    if payload.avatar is not None:
        user.avatar = payload.avatar
    db.commit()
    return {"ok": True, "name": user.name, "phone": user.phone, "avatar": user.avatar}


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters")
        return v


@router.post("/change-password")
def change_password(payload: ChangePasswordIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == current.email).first()
    if not user or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"ok": True}
