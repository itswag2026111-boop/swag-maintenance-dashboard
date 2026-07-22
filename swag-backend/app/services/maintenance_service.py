from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import MaintenanceRequest, Attachment, FinanceRecord, AuditLog

MODULE = "maintenance"
SLA_DAYS = 3  # requests open longer than this are flagged overdue, matches the original app's SLA_DAYS

# The real request lifecycle: branch submits -> admin reviews -> admin verifies
# and forwards to finance (THIS is the only moment a FinanceRecord gets created,
# via send_to_finance() below - so Finance's queue only ever contains requests
# an admin has actually checked) -> finance approves/rejects, which flows back
# onto the request (via sync_status_from_finance) so the branch that raised it
# can see exactly where things stand without needing Finance access.
STATUS_WAITING = "Waiting"
STATUS_IN_PROGRESS = "In Progress"
STATUS_SENT_TO_FINANCE = "Sent to Finance"
STATUS_APPROVED = "Approved"
STATUS_REJECTED = "Rejected"
STATUS_COMPLETED = "Completed"
STATUS_CANCELLED = "Cancelled"

ALL_STATUSES = [
    STATUS_WAITING, STATUS_IN_PROGRESS, STATUS_SENT_TO_FINANCE,
    STATUS_APPROVED, STATUS_REJECTED, STATUS_COMPLETED, STATUS_CANCELLED,
]


def shape_request(r: MaintenanceRequest) -> dict:
    is_open = r.status not in (STATUS_COMPLETED, STATUS_CANCELLED)
    days_old = (datetime.now(timezone.utc) - r.created_at).days if r.created_at else 0
    return {
        "id": r.id,
        "company": r.company,
        "branch": r.branch,
        "category": r.category,
        "detail": r.detail,
        "status": r.status,
        "priority": r.priority,
        "assignees": [e.strip() for e in (r.assignees or "").split(",") if e.strip()],
        "createdBy": r.created_by,
        "created": r.created_at.isoformat() if r.created_at else "",
        "daysOld": days_old,
        "isOverdue": is_open and days_old > SLA_DAYS,
    }


def list_requests(db: Session) -> list[dict]:
    rows = db.query(MaintenanceRequest).order_by(MaintenanceRequest.id.desc()).all()
    return [shape_request(r) for r in rows]


def get_request(db: Session, item_id: int) -> MaintenanceRequest | None:
    return db.query(MaintenanceRequest).filter(MaintenanceRequest.id == item_id).first()


def create_request(db: Session, company: str, branch: str, category: str, detail: str, priority: str = "Normal", created_by: str = "") -> MaintenanceRequest:
    req = MaintenanceRequest(
        company=company, branch=branch, category=category, detail=detail,
        priority=priority, status=STATUS_WAITING, created_by=created_by,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def update_status(db: Session, item_id: int, status: str) -> bool:
    """Plain status updates (Waiting/In Progress/Completed/Cancelled) - does
    NOT touch Finance. Forwarding to Finance only happens via send_to_finance()."""
    req = get_request(db, item_id)
    if not req:
        return False
    req.status = status
    db.commit()
    return True


def sync_status_from_finance(db: Session, item_id: int, finance_status: str) -> None:
    """Called by the finance router when a linked record is approved/rejected -
    reflects that back onto the original request."""
    req = get_request(db, item_id)
    if not req:
        return
    if finance_status == "approved":
        req.status = STATUS_APPROVED
    elif finance_status == "rejected":
        req.status = STATUS_REJECTED
    db.commit()


def assign_technicians(db: Session, item_id: int, emails: list[str]) -> bool:
    req = get_request(db, item_id)
    if not req:
        return False
    req.assignees = ", ".join(e.strip() for e in emails if e.strip())
    db.commit()
    return True


def send_to_finance(db: Session, item_id: int, cost: str) -> FinanceRecord | None:
    """
    The core workflow step: an admin reviews a maintenance request and,
    once satisfied, forwards it to Finance with a cost estimate. This is
    the ONLY place a FinanceRecord gets created - Finance never sees
    anything that hasn't been verified first.
    """
    req = get_request(db, item_id)
    if not req:
        return None

    finance_row = FinanceRecord(
        request_id=req.id, branch=req.branch, category=req.category,
        cost=cost, status="waiting for approval",
    )
    db.add(finance_row)
    req.status = STATUS_SENT_TO_FINANCE
    db.commit()
    db.refresh(finance_row)
    return finance_row


def get_activity(db: Session, item_id: int) -> list[dict]:
    """
    Full timeline for a request: everything that happened to it in
    Maintenance, PLUS whatever happened afterward in Finance once it was
    forwarded there (matched via the FinanceRecord it created).
    """
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.module == "maintenance", AuditLog.item_id == str(item_id))
        .all()
    )
    finance_ids = [str(r.id) for r in db.query(FinanceRecord).filter(FinanceRecord.request_id == item_id).all()]
    if finance_ids:
        logs += (
            db.query(AuditLog)
            .filter(AuditLog.module == "finance", AuditLog.item_id.in_(finance_ids))
            .all()
        )
    logs.sort(key=lambda l: l.created_at)
    return [
        {"email": l.email, "module": l.module, "action": l.action, "detail": l.detail, "created_at": l.created_at.isoformat()}
        for l in logs
    ]


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
