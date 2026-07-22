from sqlalchemy.orm import Session

from app.models import Group, GroupModuleAccess, UserRole


def list_groups(db: Session) -> list[dict]:
    groups = db.query(Group).order_by(Group.name).all()
    result = []
    for g in groups:
        entries = db.query(GroupModuleAccess).filter(GroupModuleAccess.group_id == g.id).all()
        result.append({
            "id": g.id,
            "name": g.name,
            "access": [{"id": e.id, "module": e.module, "role": e.role, "branches": e.branches} for e in entries],
        })
    return result


def create_group(db: Session, name: str) -> Group:
    g = Group(name=name.strip())
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def delete_group(db: Session, group_id: int) -> bool:
    g = db.query(Group).filter(Group.id == group_id).first()
    if not g:
        return False
    db.query(GroupModuleAccess).filter(GroupModuleAccess.group_id == group_id).delete()
    db.delete(g)
    db.commit()
    return True


def set_group_access(db: Session, group_id: int, module: str, role: str, branches: str | None) -> None:
    """Upsert one module's access entry within a group's template."""
    existing = (
        db.query(GroupModuleAccess)
        .filter(GroupModuleAccess.group_id == group_id, GroupModuleAccess.module == module)
        .first()
    )
    if role == "none":
        if existing:
            db.delete(existing)
    elif existing:
        existing.role = role
        existing.branches = branches
    else:
        db.add(GroupModuleAccess(group_id=group_id, module=module, role=role, branches=branches))
    db.commit()


def apply_group_to_user(db: Session, group_id: int, email: str) -> int:
    """Copies a group's permission template onto a user - creates/updates
    their UserRole rows to match. Returns how many modules were granted."""
    entries = db.query(GroupModuleAccess).filter(GroupModuleAccess.group_id == group_id).all()
    count = 0
    for e in entries:
        existing = db.query(UserRole).filter(UserRole.email == email, UserRole.module == e.module).first()
        if existing:
            existing.role = e.role
            existing.branches = e.branches
        else:
            db.add(UserRole(email=email, module=e.module, role=e.role, branches=e.branches))
        count += 1
    db.commit()
    return count
