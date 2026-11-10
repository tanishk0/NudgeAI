import hashlib
import os
import time
from typing import Any, Dict, Optional, Tuple
import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import UserRecord

security_scheme = HTTPBearer(auto_error=False)

# Short-lived cache for Supabase /auth/v1/user verification: token_hash -> (expires_at, user_dict)
_TOKEN_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _get_supabase_config() -> Tuple[str, str, str]:
    supabase_url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    supabase_key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
        or ""
    ).strip()
    jwt_secret = (os.getenv("SUPABASE_JWT_SECRET") or "").strip()
    return supabase_url, supabase_key, jwt_secret


async def verify_supabase_token(token: str) -> Dict[str, Any]:
    """
    Verify a Supabase access token and return normalized user claims:
    `{ "id": str, "email": str, "display_name": str | None, "avatar_url": str | None }`
    Supports both HS256 local JWT verification and Supabase `/auth/v1/user` verification
    (for ES256 / asymmetric project keys).
    """
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = time.time()

    cached = _TOKEN_CACHE.get(token_hash)
    if cached and cached[0] > now:
        return cached[1]

    supabase_url, supabase_key, jwt_secret = _get_supabase_config()

    # 1. Try local HS256 verification if SUPABASE_JWT_SECRET is present
    if jwt_secret:
        try:
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            sub = payload.get("sub")
            email = payload.get("email")
            if sub and email:
                meta = payload.get("user_metadata") or {}
                user_info = {
                    "id": str(sub),
                    "email": str(email),
                    "display_name": meta.get("full_name")
                    or meta.get("name")
                    or meta.get("display_name"),
                    "avatar_url": meta.get("avatar_url"),
                }
                exp = float(payload.get("exp", now + 300))
                _TOKEN_CACHE[token_hash] = (min(exp, now + 300), user_info)
                return user_info
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session token has expired. Please sign in again.",
            )
        except jwt.PyJWTError:
            # Fall through to Supabase Auth API check (e.g. ES256 asymmetric token)
            pass

    # 2. Verify directly against Supabase Auth API (/auth/v1/user)
    if not supabase_url or not supabase_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase Auth configuration missing on backend.",
        )

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            f"{supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": supabase_key,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Supabase authentication token.",
        )

    data = resp.json()
    sub = data.get("id")
    email = data.get("email")
    if not sub or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase token did not contain a valid user identity.",
        )

    meta = data.get("user_metadata") or {}
    user_info = {
        "id": str(sub),
        "email": str(email),
        "display_name": meta.get("full_name")
        or meta.get("name")
        or meta.get("display_name")
        or email.split("@")[0],
        "avatar_url": meta.get("avatar_url"),
    }
    _TOKEN_CACHE[token_hash] = (now + 300, user_info)
    return user_info


def sync_user_in_db(db: Session, user_info: Dict[str, Any]) -> UserRecord:
    """Upsert the authenticated Supabase user into the PostgreSQL `users` table."""
    user_id = user_info["id"]
    email = user_info["email"]
    display_name = user_info.get("display_name")
    avatar_url = user_info.get("avatar_url")

    record = db.query(UserRecord).filter(UserRecord.id == user_id).first()
    if not record:
        # Also check if a user record with same email exists
        record = db.query(UserRecord).filter(UserRecord.email == email).first()

    if record:
        record.email = email
        if display_name:
            record.display_name = display_name
        if avatar_url:
            record.avatar_url = avatar_url
    else:
        record = UserRecord(
            id=user_id,
            email=email,
            display_name=display_name or email.split("@")[0],
            avatar_url=avatar_url,
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return record


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> UserRecord:
    """FastAPI dependency requiring a valid Supabase Bearer token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Bearer token.",
        )

    user_info = await verify_supabase_token(credentials.credentials)
    return sync_user_in_db(db, user_info)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> Optional[UserRecord]:
    """FastAPI dependency that returns the authenticated user if a valid token is provided, or None."""
    if not credentials or not credentials.credentials:
        return None
    try:
        user_info = await verify_supabase_token(credentials.credentials)
        return sync_user_in_db(db, user_info)
    except HTTPException:
        return None

