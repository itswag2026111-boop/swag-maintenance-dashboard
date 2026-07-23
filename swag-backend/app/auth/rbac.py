"""
Server-side RBAC. This is the fix for the old apps' biggest gap:
role was only ever checked in JavaScript, so any authenticated user
could call the SharePoint API directly and bypass hidden buttons.

Here, EVERY route decides required role BEFORE touching the database.
There is no client-side bypass because the client never talks to
the database directly - only to this backend.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.local_auth import CurrentUser, get_current_user
from app.database import get_db
from app.models import UserRole

ROLE_RANK = {"viewer": 0, "editor": 1, "admin": 2}


class AuthorizedUser(CurrentUser):
    def __init__(self, current: CurrentUser, module: str, role: str, branches: str | None):
        super().__init__(current.email, current.name)
        self.module = module
        self.role = role
        self.branches = [b.strip() for b in branches.split(",")] if branches else None  # None = all

    def can_write(self) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK["editor"]

    def is_admin(self) -> bool:
        return self.role == "admin"


def require_module_access(module: str, min_role: str = "viewer"):
    """
    Usage:
        @router.get("/assets", dependencies=[])
        def list_assets(user: AuthorizedUser = Depends(require_module_access("inventory"))):
            ...

        @router.post("/assets")
        def create_asset(user: AuthorizedUser = Depends(require_module_access("inventory", "editor"))):
            ...
    """

    def _dependency(
        current: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> AuthorizedUser:
        row = (
            db.query(UserRole)
            .filter(UserRole.email == current.email, UserRole.module == module)
            .first()
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{current.email} has no access to '{module}'. Ask an admin to grant a role.",
            )
        if ROLE_RANK.get(row.role, -1) < ROLE_RANK.get(min_role, 99):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"'{row.role}' role is not sufficient for this action (needs '{min_role}' or higher).",
            )
        return AuthorizedUser(current, module, row.role, row.branches)

    return _dependency


def require_any_admin():
    """Gate for the role-management panel: user must be 'admin' in at
    least one module WITH NO branch restriction (a branch-scoped admin,
    e.g. admin of only their own branch's inventory, must not be able to
    grant/revoke access for the whole system)."""

    def _dependency(
        current: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        is_admin = (
            db.query(UserRole)
            .filter(UserRole.email == current.email, UserRole.role == "admin", UserRole.branches.is_(None))
            .first()
            is not None
        )
        if not is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
        return current

    return _dependency
