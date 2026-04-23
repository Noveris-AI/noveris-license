from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.modules.issue.models import AuditLog


class AuditEventType:
    LICENSE_ISSUED = "license_issued"
    LICENSE_REVOKED = "license_revoked"

    ACTIVATION_SUCCESS_ONLINE = "activation_success_online"
    ACTIVATION_SUCCESS_OFFLINE = "activation_success_offline"
    ACTIVATION_FAILED = "activation_failed"

    RENEWAL_SUCCESS_ONLINE = "renewal_success_online"
    RENEWAL_SUCCESS_OFFLINE = "renewal_success_offline"
    RENEWAL_FAILED = "renewal_failed"

    OFFLINE_BUNDLE_PROCESSED = "offline_bundle_processed"
    OFFLINE_RENEWAL_PROCESSED = "offline_renewal_processed"

    OPERATOR_LOGIN = "operator_login"
    OPERATOR_LOGIN_FAILED = "operator_login_failed"
    OPERATOR_LOGOUT = "operator_logout"

    LICENSE_DELETED = "license_deleted"

    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_SIGNATURE = "invalid_signature"
    SUSPICIOUS_MULTI_REGION = "suspicious_multi_region"


def write_audit_log(
    db: Session,
    *,
    event_type: str,
    license_key: Optional[str] = None,
    activation_id: Optional[uuid.UUID] = None,
    operator_id: Optional[uuid.UUID] = None,
    client_ip: Optional[str] = None,
    cluster_id: Optional[str] = None,
    detail: Optional[dict[str, Any]] = None,
) -> AuditLog:
    log = AuditLog(
        event_type=event_type,
        license_key=license_key,
        activation_id=activation_id,
        operator_id=operator_id,
        client_ip=client_ip,
        cluster_id=cluster_id,
        detail=detail,
    )
    db.add(log)
    return log
