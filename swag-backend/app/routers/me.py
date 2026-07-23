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
        # A branch-restricted admin (e.g. admin of just their own branch's
        # inventory) should NOT get the global Access Management panel -
        # that would let them grant/revoke access for the whole system.
        # Only an unrestricted (all-branches) admin role counts here.
        "is_admin_anywhere": any(r.role == "admin" and not r.branches for r in rows),
    }
