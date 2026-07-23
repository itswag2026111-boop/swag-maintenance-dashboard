from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.auth.local_auth import CurrentUser, hash_password
from app.auth.rbac import require_any_admin
from app.database import get_db
from app.models import AuditLog, User, UserRole

router = APIRouter(prefix="/api/admin", tags=["admin"])


class RoleIn(BaseModel):
    email: str
    module: str  # 'inventory' | 'maintenance' | 'finance'
    role: str    # 'viewer' | 'editor' | 'admin'
    branches: str | None = None  # CSV, null = all branches


class CreateUserIn(BaseModel):
    email: EmailStr
    name: str = ""
    password: str

    @field_validator("password")
    @classmethod
    def _min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


@router.post("/users")
def create_user(
    payload: CreateUserIn,
    admin: CurrentUser = Depends(require_any_admin()),
    db: Session = Depends(get_db),
):
    """Admin-only account creation. Self-registration is closed, so this
    is now the only way new people get a login."""
    email = payload.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(email=email, name=payload.name or email.split("@")[0], password_hash=hash_password(payload.password))
    db.add(user)
    db.add(AuditLog(email=admin.email, module="admin", action="create_user", item_id=None, detail=email))
    db.commit()
    return {"ok": True, "email": user.email}


@router.get("/roles")
def list_roles(user: CurrentUser = Depends(require_any_admin()), db: Session = Depends(get_db)):
    rows = db.query(UserRole).order_by(UserRole.email).all()
    return [
        {"id": r.id, "email": r.email, "module": r.module, "role": r.role, "branches": r.branches}
        for r in rows
    ]


@router.post("/roles")
def create_role(payload: RoleIn, user: CurrentUser = Depends(require_any_admin()), db: Session = Depends(get_db)):
    existing = (
        db.query(UserRole)
        .filter(UserRole.email == payload.email.lower(), UserRole.module == payload.module)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="This user already has a role for this module - edit it instead")
    row = UserRole(email=payload.email.lower(), module=payload.module, role=payload.role, branches=payload.branches)
    db.add(row)
    db.add(AuditLog(email=user.email, module="admin", action="grant_role", item_id=None,
                     detail=f"{payload.email} -> {payload.module}:{payload.role}"))
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.patch("/roles/{role_id}")
def update_role(role_id: int, payload: RoleIn, user: CurrentUser = Depends(require_any_admin()), db: Session = Depends(get_db)):
    row = db.query(UserRole).filter(UserRole.id == role_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Role not found")
    row.role = payload.role
    row.branches = payload.branches
    db.add(AuditLog(email=user.email, module="admin", action="update_role", item_id=str(role_id),
                     detail=f"{row.email}/{row.module} -> {payload.role}"))
    db.commit()
    return {"ok": True}


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, user: CurrentUser = Depends(require_any_admin()), db: Session = Depends(get_db)):
    row = db.query(UserRole).filter(UserRole.id == role_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Role not found")
    db.add(AuditLog(email=user.email, module="admin", action="revoke_role", item_id=str(role_id),
                     detail=f"{row.email}/{row.module}"))
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/audit-log")
def get_audit_log(user: CurrentUser = Depends(require_any_admin()), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(500).all()
    return [
        {"id": r.id, "email": r.email, "module": r.module, "action": r.action,
         "item_id": r.item_id, "detail": r.detail, "created_at": r.created_at.isoformat()}
        for r in rows
    ]
