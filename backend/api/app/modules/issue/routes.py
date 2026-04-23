from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.audit import AuditEventType, write_audit_log
from app.core.config import settings
from app.core.errors import AppException
from app.core.pagination import PageParams
from app.core.session import (
    check_login_rate_limit,
    check_redis_rate_limit,
    clear_session_cookie,
    create_session,
    delete_session,
    get_current_operator,
    get_redis,
    set_session_cookie,
)
from app.modules.issue.models import get_db
from app.modules.issue.schemas import (
    ActivationRequest,
    ActivationResponse,
    DeleteResponse,
    LeaseRenewRequest,
    LeaseRenewResponse,
    LicenseDetailResponse,
    LicenseIssueRequest,
    LicenseIssueResponse,
    LicenseListResponse,
    LoginRequest,
    LoginResponse,
    OfflineActivationResponseBundle,
    OfflineRenewResponseBundle,
    ProcessOfflineRenewRequestBody,
    ProcessOfflineRequestBody,
    RevokeRequest,
    RevokeResponse,
)
from app.modules.issue.services import AuthService, LicenseService
from app.modules.verify.routes import check_rate_limit, get_client_ip

router = APIRouter()


def require_operator(request: Request) -> dict:
    operator = get_current_operator(request)
    if not operator:
        raise AppException(401, "未登录或会话已过期")
    return operator


def operator_uuid(operator: dict) -> uuid.UUID | None:
    raw_operator_id = operator.get("operator_id")
    if not raw_operator_id:
        return None
    try:
        return uuid.UUID(str(raw_operator_id))
    except ValueError:
        return None


def audit_rate_limit(db: Session, client_ip: str | None, scope: str) -> None:
    write_audit_log(
        db,
        event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
        client_ip=client_ip,
        detail={"scope": scope},
    )
    db.commit()


def check_offline_process_rate_limit(db: Session, operator: dict, client_ip: str | None) -> None:
    op_id = str(operator.get("operator_id", "unknown"))
    try:
        check_redis_rate_limit(
            f"rate_limit:offline_process:{op_id}",
            settings.offline_process_rate_limit,
            settings.offline_process_rate_window,
        )
    except AppException:
        audit_rate_limit(db, client_ip, "offline_process")
        raise


@router.post("/auth/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    try:
        check_login_rate_limit(client_ip)
    except AppException:
        audit_rate_limit(db, client_ip, "login")
        raise

    auth_service = AuthService(db)
    operator = auth_service.authenticate(req.email, req.password)
    if not operator:
        known_operator = auth_service.get_by_email(req.email)
        write_audit_log(
            db,
            event_type=AuditEventType.OPERATOR_LOGIN_FAILED,
            operator_id=known_operator.id if known_operator else None,
            client_ip=client_ip,
            detail={"email": req.email},
        )
        db.commit()
        raise AppException(401, "邮箱或密码错误")

    session_id = create_session(str(operator.id), operator.email, operator.username)
    set_session_cookie(response, session_id)
    write_audit_log(
        db,
        event_type=AuditEventType.OPERATOR_LOGIN,
        operator_id=operator.id,
        client_ip=client_ip,
        detail={"email": operator.email},
    )
    db.commit()

    return LoginResponse(email=operator.email, username=operator.username)


@router.post("/auth/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    operator = get_current_operator(request)
    client_ip = get_client_ip(request)
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        delete_session(session_id)
    if operator:
        write_audit_log(
            db,
            event_type=AuditEventType.OPERATOR_LOGOUT,
            operator_id=operator_uuid(operator),
            client_ip=client_ip,
        )
        db.commit()
    clear_session_cookie(response)
    return {"success": True}


@router.get("/auth/me")
def me(operator: dict = Depends(require_operator)):
    return {
        "operator_id": operator["operator_id"],
        "email": operator["email"],
        "username": operator["username"],
    }


@router.post("/license/issue", response_model=LicenseIssueResponse)
def issue_license(
    req: LicenseIssueRequest,
    request: Request,
    db: Session = Depends(get_db),
    operator: dict = Depends(require_operator),
):
    service = LicenseService(db)
    return service.issue(req, operator_id=operator_uuid(operator), client_ip=get_client_ip(request))


@router.post("/licenses/activate", response_model=ActivationResponse)
def activate_license(
    req: ActivationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    try:
        check_rate_limit(client_ip)
    except AppException:
        audit_rate_limit(db, client_ip, "activate")
        raise
    service = LicenseService(db)
    return service.activate(req, client_ip=client_ip)


@router.post("/licenses/renew", response_model=LeaseRenewResponse)
def renew_license(
    req: LeaseRenewRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    try:
        check_rate_limit(client_ip)
    except AppException:
        audit_rate_limit(db, client_ip, "renew")
        raise
    service = LicenseService(db)
    return service.renew(req, client_ip=client_ip)


@router.post("/licenses/offline/process-activation", response_model=OfflineActivationResponseBundle)
def process_offline_activation(
    body: ProcessOfflineRequestBody,
    request: Request,
    db: Session = Depends(get_db),
    operator: dict = Depends(require_operator),
):
    """管理员处理客户端提交的离线激活请求包，返回响应包（离线环境专用）"""
    client_ip = get_client_ip(request)
    check_offline_process_rate_limit(db, operator, client_ip)
    redis_client = get_redis()
    service = LicenseService(db)
    return service.process_offline_activation(
        body,
        redis_client,
        operator_id=operator_uuid(operator),
        client_ip=client_ip,
    )


@router.post("/licenses/offline/process-renewal", response_model=OfflineRenewResponseBundle)
def process_offline_renewal(
    body: ProcessOfflineRenewRequestBody,
    request: Request,
    db: Session = Depends(get_db),
    operator: dict = Depends(require_operator),
):
    """管理员处理客户端提交的离线续期请求包，返回新 Lease 响应包"""
    client_ip = get_client_ip(request)
    check_offline_process_rate_limit(db, operator, client_ip)
    redis_client = get_redis()
    service = LicenseService(db)
    return service.process_offline_renewal(
        body,
        redis_client,
        operator_id=operator_uuid(operator),
        client_ip=client_ip,
    )


@router.get("/licenses", response_model=LicenseListResponse)
def list_licenses(
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
    operator: dict = Depends(require_operator),
):
    del operator
    service = LicenseService(db)
    items, total = service.list_licenses(page_params.page, page_params.size)
    pages = (total + page_params.size - 1) // page_params.size

    return LicenseListResponse(
        items=items,
        total=total,
        page=page_params.page,
        size=page_params.size,
        pages=pages,
    )


@router.get("/licenses/{license_id}", response_model=LicenseDetailResponse)
def get_license(
    license_id: uuid.UUID,
    db: Session = Depends(get_db),
    operator: dict = Depends(require_operator),
):
    del operator
    service = LicenseService(db)
    detail = service.get_license_detail(license_id)
    if not detail:
        raise AppException(404, "License 不存在")

    license_item, certificate, activations, leases, logs = detail
    return LicenseDetailResponse(
        license=license_item,
        certificate=certificate,
        activations=activations,
        leases=leases,
        verify_logs=logs,
    )


@router.delete("/licenses/{license_id}", response_model=DeleteResponse)
def delete_license(
    license_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    operator: dict = Depends(require_operator),
):
    service = LicenseService(db)
    success = service.delete_license(
        license_id,
        operator_id=operator_uuid(operator),
        client_ip=get_client_ip(request),
    )
    if not success:
        raise AppException(404, "License 不存在")
    return DeleteResponse(success=True)


@router.post("/licenses/{license_id}/revoke", response_model=RevokeResponse)
def revoke_license(
    license_id: uuid.UUID,
    req: RevokeRequest,
    request: Request,
    db: Session = Depends(get_db),
    operator: dict = Depends(require_operator),
):
    service = LicenseService(db)
    try:
        license_record = service.revoke(
            license_id,
            req,
            operator_id=operator_uuid(operator),
            client_ip=get_client_ip(request),
        )
    except ValueError as exc:
        raise AppException(409, str(exc))
    if not license_record:
        raise AppException(404, "License 不存在")

    return RevokeResponse(success=True)
