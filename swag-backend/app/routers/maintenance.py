from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.rbac import AuthorizedUser, require_module_access
from app.database import get_db
from app.models import AuditLog
from app.services import maintenance_service

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])

MODULE = "maintenance"


class RequestIn(BaseModel):
    company: str
    branch: str
    category: str
    detail: str
    priority: str = "Normal"


class StatusIn(BaseModel):
    status: str


class AssignIn(BaseModel):
    emails: list[str]


class SendToFinanceIn(BaseModel):
    cost: str


def _log(db: Session, user: AuthorizedUser, action: str, item_id, detail: str = ""):
    db.add(AuditLog(email=user.email, module=MODULE, action=action, item_id=str(item_id), detail=detail))
    db.commit()


@router.get("/requests")
def get_requests(user: AuthorizedUser = Depends(require_module_access(MODULE, "viewer")), db: Session = Depends(get_db)):
    requests = maintenance_service.list_requests(db)
    if user.branches:
        requests = [r for r in requests if r["branch"] in user.branches]
    return {"requests": requests, "role": user.role}


@router.get("/requests/{item_id}")
def get_request(item_id: int, user: AuthorizedUser = Depends(require_module_access(MODULE, "viewer")), db: Session = Depends(get_db)):
    req = maintenance_service.get_request(db, item_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return maintenance_service.shape_request(req)


@router.post("/requests")
def create_request(
    payload: RequestIn,
    user: AuthorizedUser = Depends(require_module_access(MODULE, "viewer")),  # any signed-in staff can raise a request
    db: Session = Depends(get_db),
):
    req = maintenance_service.create_request(db, payload.company, payload.branch, payload.category, payload.detail, payload.priority)
    _log(db, user, "create", req.id, payload.detail[:80])
    return maintenance_service.shape_request(req)


@router.patch("/requests/{item_id}/status")
def update_status(
    item_id: int,
    payload: StatusIn,
    user: AuthorizedUser = Depends(require_module_access(MODULE, "editor")),
    db: Session = Depends(get_db),
):
    ok = maintenance_service.update_status(db, item_id, payload.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Request not found")
    _log(db, user, "update_status", item_id, payload.status)
    return {"ok": True}


@router.delete("/requests/{item_id}")
def delete_request(
    item_id: int,
    user: AuthorizedUser = Depends(require_module_access(MODULE, "admin")),
    db: Session = Depends(get_db),
):
    ok = maintenance_service.delete_request(db, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Request not found")
    _log(db, user, "delete", item_id)
    return {"ok": True}


@router.patch("/requests/{item_id}/assign")
def assign_technicians(
    item_id: int,
    payload: AssignIn,
    user: AuthorizedUser = Depends(require_module_access(MODULE, "editor")),
    db: Session = Depends(get_db),
):
    ok = maintenance_service.assign_technicians(db, item_id, payload.emails)
    if not ok:
        raise HTTPException(status_code=404, detail="Request not found")
    _log(db, user, "assign", item_id, ", ".join(payload.emails))
    return {"ok": True}


@router.post("/requests/{item_id}/send-to-finance")
def send_to_finance(
    item_id: int,
    payload: SendToFinanceIn,
    user: AuthorizedUser = Depends(require_module_access(MODULE, "admin")),  # only admin verifies + forwards
    db: Session = Depends(get_db),
):
    record = maintenance_service.send_to_finance(db, item_id, payload.cost)
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")
    _log(db, user, "send_to_finance", item_id, f"cost={payload.cost}")
    return {"ok": True, "financeRecordId": record.id}


@router.get("/requests/{item_id}/activity")
def get_activity(item_id: int, user: AuthorizedUser = Depends(require_module_access(MODULE, "viewer")), db: Session = Depends(get_db)):
    return {"activity": maintenance_service.get_activity(db, item_id)}


@router.get("/requests/{item_id}/attachments")
def list_attachments(item_id: int, user: AuthorizedUser = Depends(require_module_access(MODULE, "viewer")), db: Session = Depends(get_db)):
    return {"attachments": maintenance_service.list_attachments(db, item_id)}


@router.get("/requests/{item_id}/attachments/{file_name}")
def download_attachment(
    item_id: int, file_name: str, user: AuthorizedUser = Depends(require_module_access(MODULE, "viewer")), db: Session = Depends(get_db)
):
    att = maintenance_service.get_attachment(db, item_id, file_name)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return Response(content=att.data, media_type=att.content_type)


@router.post("/requests/{item_id}/attachments")
async def upload_attachment(
    item_id: int,
    file: UploadFile = File(...),
    user: AuthorizedUser = Depends(require_module_access(MODULE, "editor")),
    db: Session = Depends(get_db),
):
    if not maintenance_service.get_request(db, item_id):
        raise HTTPException(status_code=404, detail="Request not found")
    content = await file.read()
    maintenance_service.upload_attachment(db, item_id, file.filename, file.content_type or "application/octet-stream", content, user.email)
    _log(db, user, "upload_attachment", item_id, file.filename)
    return {"ok": True}
