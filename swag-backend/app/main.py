from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, engine
from app.routers import inventory, maintenance, finance, me, admin, notifications, auth, lookups, groups

# create tables if they don't exist yet (fine for this size project;
# switch to Alembic migrations once the schema starts changing often)
Base.metadata.create_all(bind=engine)


def _sync_missing_columns():
    """
    create_all() only creates NEW tables - it never adds columns to tables
    that already exist. Since we don't have Alembic migrations set up yet,
    this does a lightweight equivalent: for every model, check Postgres for
    any column that's in the model but missing from the real table, and
    ALTER TABLE to add it. Keeps existing deployments from breaking every
    time a new field gets added to a model.
    """
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing_cols:
                    col_type = col.type.compile(engine.dialect)
                    default = "" if col.default is None or col.default.arg is None else f"DEFAULT '{col.default.arg}'"
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type} {default}'))


_sync_missing_columns()

app = FastAPI(title="Swag Secure API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(inventory.router)
app.include_router(maintenance.router)
app.include_router(finance.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(lookups.router)
app.include_router(groups.router)


@app.get("/health")
def health():
    return {"status": "ok"}
