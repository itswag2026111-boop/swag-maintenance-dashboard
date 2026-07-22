from sqlalchemy.orm import Session

from app.models import MaintenanceRequest, Attachment

MODULE = "maintenance"


def shape_request(r: MaintenanceRequest) -> dict:
    return {
        "id": r.id,
        "company": r.company,
        "branch": r.branch,
        "category": r.category,
        "detail": r.detail,
        "status": r.status,
        "priority": r.priority,
        "assignees": [e.strip() for e in (r.assignees or "").split(",") if e.strip()],
        "created": r.created_at.isoformat() if r.created_at else "",
    }


def list_requests(db: Session) -> list[dict]:
    rows = db.query(MaintenanceRequest).order_by(MaintenanceRequest.id.desc()).all()
    return [shape_request(r) for r in rows]


def get_request(db: Session, item_id: int) -> MaintenanceRequest | None:
    return db.query(MaintenanceRequest).filter(MaintenanceRequest.id == item_id).first()


def create_request(db: Session, company: str, branch: str, category: str, detail: str, priority: str = "Normal") -> MaintenanceRequest:
    req = MaintenanceRequest(company=company, branch=branch, category=category, detail=detail, priority=priority, status="Waiting")
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def update_status(db: Session, item_id: int, status: str) -> bool:
    req = get_request(db, item_id)
    if not req:
        return False
    req.status = status
    db.commit()
    return True


def assign_technicians(db: Session, item_id: int, emails: list[str]) -> bool:
    req = get_request(db, item_id)
    if not req:
        return False
    req.assignees = ", ".join(e.strip() for e in emails if e.strip())
    db.commit()
    return True


def delete_request(db: Session, item_id: int) -> bool:
    req = get_request(db, item_id)
    if not req:
        return False
    db.delete(req)
    db.query(Attachment).filter(Attachment.module == MODULE, Attachment.item_id == item_id).delete()
    db.commit()
    return True


def list_attachments(db: Session, item_id: int) -> list[dict]:
    rows = db.query(Attachment).filter(Attachment.module == MODULE, Attachment.item_id == item_id).all()
    return [{"fileName": a.file_name} for a in rows]


def get_attachment(db: Session, item_id: int, file_name: str) -> Attachment | None:
    return (
        db.query(Attachment)
        .filter(Attachment.module == MODULE, Attachment.item_id == item_id, Attachment.file_name == file_name)
        .first()
    )


def upload_attachment(db: Session, item_id: int, filename: str, content_type: str, content: bytes, uploaded_by: str) -> None:
    db.add(Attachment(
        module=MODULE, item_id=item_id, file_name=filename,
        content_type=content_type, data=content, uploaded_by=uploaded_by,
    ))
    db.commit()
