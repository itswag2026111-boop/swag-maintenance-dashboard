from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.rbac import AuthorizedUser, require_module_access
from app.database import get_db
from app.models import AuditLog
from app.services import finance_service

router = APIRouter(prefix="/api/finance", tags=["finance"])

MODULE = "finance"


class StatusIn(BaseModel):
    status: str  # 'approved' | 'rejected' | 'waiting for approval'


class RecordIn(BaseModel):
    branch: str
    category: str
    cost: str
    request_id: int | None = None


@router.get("")
def get_finance(user: AuthorizedUser = Depends(require_module_access(MODULE, "viewer")), db: Session = Depends(get_db)):
    return {"finance": finance_service.list_finance(db), "role": user.role}


@router.post("")
def create_finance_record(
    payload: RecordIn,
    user: AuthorizedUser = Depends(require_module_access(MODULE, "editor")),
    db: Session = Depends(get_db),
):
    row = finance_service.create_record(db, payload.branch, payload.category, payload.cost, payload.request_id)
    db.add(AuditLog(email=user.email, module=MODULE, action="create", item_id=str(row.id), detail=f"{payload.branch} / {payload.category}"))
    db.commit()
    return finance_service.shape_record(row)


@router.patch("/{item_id}/status")
def set_finance_status(
    item_id: int,
    payload: StatusIn,
    user: AuthorizedUser = Depends(require_module_access(MODULE, "editor")),
    db: Session = Depends(get_db),
):
    ok = finance_service.set_status(db, item_id, payload.status, approved_by=user.name)
    if not ok:
        raise HTTPException(status_code=404, detail="Finance record not found")
    db.add(AuditLog(email=user.email, module=MODULE, action="set_status", item_id=str(item_id), detail=payload.status))
    db.commit()
    return {"ok": True}
