from sqlalchemy.orm import Session

from app.models import Asset, Attachment

MODULE = "inventory"


def shape_asset(a: Asset) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "branch": a.branch,
        "category": a.category,
        "model": a.model,
        "color": a.color,
        "qty": a.qty,
        "status": a.status,
        "serialNumber": a.serial_number,
        "notes": a.notes,
        "purchaseDate": a.purchase_date,
        "amount": a.amount,
        "invoice": a.invoice,
        "created": a.created_at.isoformat() if a.created_at else "",
    }


def list_assets(db: Session) -> list[dict]:
    rows = db.query(Asset).order_by(Asset.id.desc()).all()
    return [shape_asset(a) for a in rows]


def get_asset(db: Session, item_id: int) -> Asset | None:
    return db.query(Asset).filter(Asset.id == item_id).first()


def create_asset(db: Session, fields: dict) -> Asset:
    asset = Asset(**fields)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def update_asset(db: Session, item_id: int, fields: dict) -> Asset | None:
    asset = get_asset(db, item_id)
    if not asset:
        return None
    for k, v in fields.items():
        setattr(asset, k, v)
    db.commit()
    db.refresh(asset)
    return asset


def delete_asset(db: Session, item_id: int) -> bool:
    asset = get_asset(db, item_id)
    if not asset:
        return False
    db.delete(asset)
    # clean up any attached photo too
    db.query(Attachment).filter(Attachment.module == MODULE, Attachment.item_id == item_id).delete()
    db.commit()
    return True


def get_photo(db: Session, item_id: int) -> Attachment | None:
    return (
        db.query(Attachment)
        .filter(Attachment.module == MODULE, Attachment.item_id == item_id)
        .order_by(Attachment.id.desc())
        .first()
    )


def set_photo(db: Session, item_id: int, filename: str, content_type: str, content: bytes, uploaded_by: str) -> None:
    # one photo per asset - replace any existing one
    db.query(Attachment).filter(Attachment.module == MODULE, Attachment.item_id == item_id).delete()
    db.add(Attachment(
        module=MODULE, item_id=item_id, file_name=filename,
        content_type=content_type, data=content, uploaded_by=uploaded_by,
    ))
    db.commit()
