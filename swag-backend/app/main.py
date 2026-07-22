from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import inventory, maintenance, finance, me, admin, notifications, auth

# create tables if they don't exist yet (fine for this size project;
# switch to Alembic migrations once the schema starts changing often)
Base.metadata.create_all(bind=engine)

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


@app.get("/health")
def health():
    return {"status": "ok"}
