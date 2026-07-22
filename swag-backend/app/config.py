import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Our own auth - no external identity provider anymore.
    jwt_secret_key: str = secrets.token_urlsafe(32)  # override in production via env!
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720  # 12 hours

    database_url: str
    allowed_origins: str = "http://localhost:5173"

    # Email notifications - optional. If smtp_host is blank, emails are
    # silently skipped (no crash). Works with Gmail (smtp.gmail.com, port 587,
    # use an "app password" not your real password), or any SMTP provider.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    @field_validator("database_url")
    @classmethod
    def _fix_postgres_scheme(cls, v: str) -> str:
        # Railway's Postgres add-on (and some other hosts) still hand out
        # "postgres://" - SQLAlchemy 2.x only accepts "postgresql://".
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
