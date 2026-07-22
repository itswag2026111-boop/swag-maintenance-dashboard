from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.rbac import AuthorizedUser, require_module_access
from app.database import get_db
from app.models import AuditLog
from app.services import inventory_service

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

MODULE = "inventory"


class AssetIn(BaseModel):
    name: str
    branch: str
    category: str
    model: str = ""
    color: str = ""
    qty: int = 1
    amount: float = 0
    status: str = "متاح"
    serial_number: str = ""
    notes: str = ""
    purchase_date: str = ""
    invoice: str = ""


def _log(db: Session, user: AuthorizedUser, action: str, item_id, detail: str = ""):
    db.add(AuditLog(email=user.email, module=MODULE, action=action, item_id=str(item_id), detail=detail))
    db.commit()


@router.get("/assets")
def get_assets(user: AuthorizedUser = Depends(require_module_access(MODULE, "viewer")), db: Session = Depends(get_db)):
    assets = inventory_service.list_assets(db)
    if user.branches:
        assets = [a for a in assets if a["branch"] in user.branches]
    return {"assets": assets, "role": user.role}


@router.get("/assets/{item_id}")
def get_asset(item_id: int, user: AuthorizedUser = Depends(require_module_access(MODULE, "viewer")), db: Session = Depends(get_db)):
    asset = inventory_service.get_asset(db, item_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return inventory_service.shape_asset(asset)


@router.post("/assets")
def create_asset(
    payload: AssetIn,
    user: AuthorizedUser = Depends(require_module_access(MODULE, "editor")),
    db: Session = Depends(get_db),
):
    asset = inventory_service.create_asset(db, payload.model_dump())
    _log(db, user, "create", asset.id, payload.name)
    return inventory_service.shape_asset(asset)


@router.patch("/assets/{item_id}")
def update_asset(
    item_id: int,
    payload: AssetIn,
    user: AuthorizedUser = Depends(require_module_access(MODULE, "editor")),
    db: Session = Depends(get_db),
):
    asset = inventory_service.update_asset(db, item_id, payload.model_dump())
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    _log(db, user, "update", item_id, payload.name)
    return inventory_service.shape_asset(asset)


@router.delete("/assets/{item_id}")
def delete_asset(
    item_id: int,
    user: AuthorizedUser = Depends(require_module_access(MODULE, "admin")),
    db: Session = Depends(get_db),
):
    ok = inventory_service.delete_asset(db, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Asset not found")
    _log(db, user, "delete", item_id)
    return {"ok": True}


@router.get("/assets/{item_id}/photo")
def get_asset_photo(item_id: int, user: AuthorizedUser = Depends(require_module_access(MODULE, "viewer")), db: Session = Depends(get_db)):
    photo = inventory_service.get_photo(db, item_id)
    if not photo:
        raise HTTPException(status_code=404, detail="No photo for this asset")
    return Response(content=photo.data, media_type=photo.content_type)


@router.post("/assets/{item_id}/photo")
async def upload_asset_photo(
    item_id: int,
    file: UploadFile = File(...),
    user: AuthorizedUser = Depends(require_module_access(MODULE, "editor")),
    db: Session = Depends(get_db),
):
    if not inventory_service.get_asset(db, item_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    content = await file.read()
    inventory_service.set_photo(db, item_id, file.filename, file.content_type or "application/octet-stream", content, user.email)
    _log(db, user, "upload_photo", item_id, file.filename)
    return {"ok": True}
