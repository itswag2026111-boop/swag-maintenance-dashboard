from sqlalchemy.orm import Session

from app.models import Lookup


def list_lookups(db: Session, type_: str) -> list[dict]:
    rows = db.query(Lookup).filter(Lookup.type == type_).order_by(Lookup.value).all()
    return [{"id": r.id, "value": r.value} for r in rows]


def add_lookup(db: Session, type_: str, value: str) -> Lookup:
    row = Lookup(type=type_, value=value.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_lookup(db: Session, lookup_id: int) -> bool:
    row = db.query(Lookup).filter(Lookup.id == lookup_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
