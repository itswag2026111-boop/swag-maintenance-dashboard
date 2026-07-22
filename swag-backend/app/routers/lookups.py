from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.auth.local_auth import CurrentUser, get_current_user
from app.auth.rbac import require_any_admin
from app.database import get_db
from app.services import lookup_service

router = APIRouter(prefix="/api/lookups", tags=["lookups"])


class LookupIn(BaseModel):
    type: str  # 'branch' | 'category'
    value: str


@router.get("/{type_}")
def get_lookups(type_: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": lookup_service.list_lookups(db, type_)}


@router.post("")
def create_lookup(payload: LookupIn, current: CurrentUser = Depends(require_any_admin()), db: Session = Depends(get_db)):
    try:
        row = lookup_service.add_lookup(db, payload.type, payload.value)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This value already exists")
    return {"id": row.id, "value": row.value}


@router.delete("/{lookup_id}")
def delete_lookup(lookup_id: int, current: CurrentUser = Depends(require_any_admin()), db: Session = Depends(get_db)):
    ok = lookup_service.delete_lookup(db, lookup_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}
