"""
Our own login system. No Azure AD, no Microsoft - just email + password,
hashed with bcrypt, and a JWT we sign ourselves with our own secret key.
"""
import time

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=True)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(email: str, name: str) -> str:
    now = int(time.time())
    payload = {
        "sub": email,
        "name": name,
        "iat": now,
        "exp": now + settings.jwt_expire_minutes * 60,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class CurrentUser:
    def __init__(self, email: str, name: str):
        self.email = email
        self.name = name


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    token = creds.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token")

    email = (payload.get("sub") or "").lower()
    if not email:
        raise HTTPException(status_code=401, detail="Malformed token")

    return CurrentUser(email=email, name=payload.get("name", email))
