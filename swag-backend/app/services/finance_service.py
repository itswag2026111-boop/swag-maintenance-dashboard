from sqlalchemy.orm import Session

from app.models import FinanceRecord


def shape_record(r: FinanceRecord) -> dict:
    return {
        "id": r.id,
        "requestId": r.request_id,
        "branch": r.branch,
        "category": r.category,
        "cost": r.cost,
        "status": r.status,
        "approvedBy": r.approved_by,
    }


def list_finance(db: Session) -> list[dict]:
    rows = db.query(FinanceRecord).order_by(FinanceRecord.id.desc()).all()
    return [shape_record(r) for r in rows]


def create_record(db: Session, branch: str, category: str, cost: str, request_id: int | None = None) -> FinanceRecord:
    row = FinanceRecord(branch=branch, category=category, cost=cost, request_id=request_id, status="waiting for approval")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def set_status(db: Session, item_id: int, status: str, approved_by: str = "") -> FinanceRecord | None:
    row = db.query(FinanceRecord).filter(FinanceRecord.id == item_id).first()
    if not row:
        return None
    row.status = status
    if approved_by:
        row.approved_by = approved_by
    db.commit()
    return row
