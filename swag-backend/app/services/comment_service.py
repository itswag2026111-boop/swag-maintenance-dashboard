from sqlalchemy.orm import Session

from app.models import Comment


def list_comments(db: Session, module: str, item_id: int, channel: str = "internal") -> list[dict]:
    rows = (
        db.query(Comment)
        .filter(Comment.module == module, Comment.item_id == item_id, Comment.channel == channel)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return [
        {"id": c.id, "email": c.email, "text": c.text, "created_at": c.created_at.isoformat()}
        for c in rows
    ]


def add_comment(db: Session, module: str, item_id: int, email: str, text: str, channel: str = "internal") -> Comment:
    c = Comment(module=module, item_id=item_id, email=email, text=text, channel=channel)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c
