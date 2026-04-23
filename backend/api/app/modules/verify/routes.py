from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.audit import AuditEventType, write_audit_log
from app.core.config import settings
from app.core.errors import AppException
from app.core.session import check_redis_rate_limit
from app.modules.issue.models import get_db
from app.modules.issue.schemas import VerifyRequest, VerifyResponse
from app.modules.issue.services import LicenseVerifier

router = APIRouter()


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def check_rate_limit(client_ip: str | None) -> None:
    if not client_ip:
        return
    key = f"rate_limit:verify:{client_ip}"
    check_redis_rate_limit(key, settings.verify_rate_limit, settings.verify_rate_window)


@router.post("/license/verify", response_model=VerifyResponse)
def verify_license(
    req: VerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    try:
        check_rate_limit(client_ip)
    except AppException:
        write_audit_log(
            db,
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            client_ip=client_ip,
            detail={"scope": "verify"},
        )
        db.commit()
        raise

    verifier = LicenseVerifier(db)
    return verifier.verify(req, client_ip)
