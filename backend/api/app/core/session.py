from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import redis
from fastapi import Request, Response

from app.core.config import settings
from app.core.errors import AppException

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

SESSION_PREFIX = "session:"


def get_redis():
    """Return the shared Redis client for nonce de-duplication and rate limiting."""
    return redis_client


def check_redis_rate_limit(key: str, limit: int, window: int) -> None:
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, window)
    if count > limit:
        raise AppException(429, "请求过于频繁，请稍后再试")


def check_login_rate_limit(client_ip: str | None) -> None:
    """Login rate limit: max attempts per IP within the configured window."""
    if not client_ip:
        return
    key = f"rate_limit:login:{client_ip}"
    check_redis_rate_limit(key, settings.login_rate_limit, settings.login_rate_window)


def create_session(operator_id: str, email: str, username: str) -> str:
    session_id = str(uuid.uuid4())
    session_data = {
        "operator_id": operator_id,
        "email": email,
        "username": username,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    key = f"{SESSION_PREFIX}{session_id}"
    redis_client.hset(key, mapping=session_data)
    redis_client.expire(key, settings.session_max_age)
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    if not session_id:
        return None
    key = f"{SESSION_PREFIX}{session_id}"
    data = redis_client.hgetall(key)
    if not data:
        return None
    # Refresh TTL on access
    redis_client.expire(key, settings.session_max_age)
    return data


def delete_session(session_id: str) -> None:
    if session_id:
        key = f"{SESSION_PREFIX}{session_id}"
        redis_client.delete(key)


def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_max_age,
        secure=settings.session_secure,
        httponly=settings.session_httponly,
        samesite=settings.session_samesite,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        secure=settings.session_secure,
        httponly=settings.session_httponly,
        samesite=settings.session_samesite,
    )


def get_current_operator(request: Request) -> Optional[dict]:
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        return None
    return get_session(session_id)
