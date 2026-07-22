from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.local_auth import CurrentUser, get_current_user
from app.database import get_db
from app.models import AuditLog, UserRole

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def get_notifications(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    my_modules = [r.module for r in db.query(UserRole).filter(UserRole.email == current.email).all()]
    if not my_modules:
        return {"items": []}

    rows = (
        db.query(AuditLog)
        .filter(AuditLog.module.in_(my_modules))
        .order_by(AuditLog.created_at.desc())
        .limit(30)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "module": r.module,
                "action": r.action,
                "detail": r.detail,
                "email": r.email,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }
