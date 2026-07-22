from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.auth.local_auth import CurrentUser
from app.auth.rbac import require_any_admin
from app.database import get_db
from app.models import AuditLog
from app.services import group_service

router = APIRouter(prefix="/api/admin/groups", tags=["groups"])


class GroupIn(BaseModel):
    name: str


class GroupAccessIn(BaseModel):
    module: str
    role: str  # 'none' | 'viewer' | 'editor' | 'admin'
    branches: str | None = None


class ApplyGroupIn(BaseModel):
    email: str


@router.get("")
def get_groups(user: CurrentUser = Depends(require_any_admin()), db: Session = Depends(get_db)):
    return group_service.list_groups(db)


@router.post("")
def create_group(payload: GroupIn, user: CurrentUser = Depends(require_any_admin()), db: Session = Depends(get_db)):
    try:
        g = group_service.create_group(db, payload.name)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A group with this name already exists")
    db.add(AuditLog(email=user.email, module="admin", action="create_group", item_id=str(g.id), detail=g.name))
    db.commit()
    return {"id": g.id, "name": g.name}


@router.delete("/{group_id}")
def delete_group(group_id: int, user: CurrentUser = Depends(require_any_admin()), db: Session = Depends(get_db)):
    ok = group_service.delete_group(db, group_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"ok": True}


@router.put("/{group_id}/access")
def set_group_access(
    group_id: int,
    payload: GroupAccessIn,
    user: CurrentUser = Depends(require_any_admin()),
    db: Session = Depends(get_db),
):
    group_service.set_group_access(db, group_id, payload.module, payload.role, payload.branches)
    return {"ok": True}


@router.post("/{group_id}/apply")
def apply_group(
    group_id: int,
    payload: ApplyGroupIn,
    user: CurrentUser = Depends(require_any_admin()),
    db: Session = Depends(get_db),
):
    count = group_service.apply_group_to_user(db, group_id, payload.email.lower())
    db.add(AuditLog(email=user.email, module="admin", action="apply_group", item_id=str(group_id), detail=f"{payload.email} ({count} modules)"))
    db.commit()
    return {"ok": True, "modulesGranted": count}
