from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.auth.local_auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User, UserRole

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str = ""

    @field_validator("password")
    @classmethod
    def _min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    name: str


@router.post("/register", response_model=AuthOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    """
    Bootstrap-only: this endpoint only works when the system has NO users
    yet (the very first setup). Once even one account exists, self-signup
    is closed forever - all further accounts must be created by an admin
    via the Admin panel (POST /api/admin/users).
    """
    any_user = db.query(User).first()
    if any_user:
        raise HTTPException(status_code=403, detail="Self-registration is closed. Ask an admin to create your account.")

    email = payload.email.lower()
    user = User(email=email, name=payload.name or email.split("@")[0], password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.email, user.name)
    return AuthOut(access_token=token, email=user.email, name=user.name)


@router.post("/bootstrap-admin", response_model=AuthOut)
def bootstrap_admin(current=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    One-time escape hatch: if NO admin exists anywhere in the system yet,
    whoever calls this (while logged in) becomes admin of every module.
    Once any admin exists, this always returns 403 - it can't be used to
    take over an already-set-up system.
    """
    any_admin = db.query(UserRole).filter(UserRole.role == "admin").first()
    if any_admin:
        raise HTTPException(status_code=403, detail="An admin already exists. Ask them to grant you access.")

    for module in ("inventory", "maintenance", "finance"):
        db.add(UserRole(email=current.email, module=module, role="admin"))
    db.commit()

    token = create_access_token(current.email, current.name)
    return AuthOut(access_token=token, email=current.email, name=current.name)


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    email = payload.email.lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user.email, user.name)
    return AuthOut(access_token=token, email=user.email, name=user.name)
