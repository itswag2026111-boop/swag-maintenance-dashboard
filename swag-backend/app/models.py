from sqlalchemy import Column, Integer, String, DateTime, Float, LargeBinary, func, UniqueConstraint

from app.database import Base


class User(Base):
    """
    Our own account store. No Azure AD, no Microsoft - just email +
    bcrypt-hashed password. This is what /api/auth/register creates and
    /api/auth/login checks against.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, default="")
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserRole(Base):
    """
    Replaces the old client-side ADMIN_EMAILS / DashboardAccess list.

    One row per (email, module). A user can be 'admin' in inventory
    and 'viewer' in maintenance, etc. `branches` is optional CSV scoping
    (e.g. only see certain branches) - leave blank for "all".
    """
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, index=True)
    module = Column(String, nullable=False)   # 'inventory' | 'maintenance'
    role = Column(String, nullable=False)     # 'admin' | 'editor' | 'viewer'
    branches = Column(String, nullable=True)  # CSV, null = all branches
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("email", "module", name="uq_user_module"),)


class AuditLog(Base):
    """
    Every write (create/update/delete) gets logged here server-side.
    This is the thing SharePoint's version history alone can't give you
    reliably tied to *your* app's notion of who-did-what-with-what-role.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, index=True)
    module = Column(String, nullable=False)
    action = Column(String, nullable=False)     # 'create' | 'update' | 'delete'
    item_id = Column(String, nullable=True)
    detail = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Asset(Base):
    """Inventory item. Lives entirely in our own database now."""
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    branch = Column(String, nullable=False, default="")
    category = Column(String, nullable=False, default="")
    model = Column(String, default="")
    color = Column(String, default="")
    qty = Column(Integer, default=1)
    status = Column(String, default="")
    serial_number = Column(String, default="")
    notes = Column(String, default="")
    purchase_date = Column(String, default="")
    amount = Column(Float, default=0)
    invoice = Column(String, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MaintenanceRequest(Base):
    """Maintenance/repair request. Lives entirely in our own database now."""
    __tablename__ = "maintenance_requests"

    id = Column(Integer, primary_key=True)
    company = Column(String, default="")
    branch = Column(String, default="")
    category = Column(String, default="")
    detail = Column(String, default="")
    status = Column(String, default="Waiting")
    priority = Column(String, default="Normal")
    assignees = Column(String, default="")  # CSV of emails
    created_by = Column(String, default="")  # email of whoever raised it
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FinanceRecord(Base):
    """Cost/billing line tied to a maintenance request."""
    __tablename__ = "finance_records"

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, default=None, nullable=True)
    branch = Column(String, default="")
    category = Column(String, default="")
    cost = Column(String, default="")
    status = Column(String, default="waiting for approval")
    approved_by = Column(String, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Comment(Base):
    """Chat-like discussion thread on any record (maintenance request for now)."""
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    module = Column(String, nullable=False)
    item_id = Column(Integer, nullable=False, index=True)
    email = Column(String, nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Lookup(Base):
    """
    Predefined dropdown values (branches, categories) instead of free-text
    fields - keeps data consistent and typo-free. Admin manages these from
    the Admin panel.
    """
    __tablename__ = "lookups"

    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)   # 'branch' | 'category'
    value = Column(String, nullable=False)

    __table_args__ = (UniqueConstraint("type", "value", name="uq_lookup_type_value"),)


class Attachment(Base):
    """
    Generic file storage for both modules (asset photos, request attachments).
    File bytes live directly in Postgres - simplest thing that works on any
    host without needing a separate persistent disk/volume.
    """
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True)
    module = Column(String, nullable=False)     # 'inventory' | 'maintenance'
    item_id = Column(Integer, nullable=False, index=True)
    file_name = Column(String, nullable=False)
    content_type = Column(String, default="application/octet-stream")
    data = Column(LargeBinary, nullable=False)
    uploaded_by = Column(String, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
