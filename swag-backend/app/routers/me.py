from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.local_auth import CurrentUser, get_current_user
from app.database import get_db
from app.models import UserRole

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("")
def get_my_access(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(UserRole).filter(UserRole.email == current.email).all()
    return {
        "email": current.email,
        "name": current.name,
        "modules": {r.module: {"role": r.role, "branches": r.branches} for r in rows},
        "is_admin_anywhere": any(r.role == "admin" for r in rows),
    }
