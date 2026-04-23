from __future__ import annotations

import binascii
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from redis import Redis
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import AuditEventType, write_audit_log
from app.core.config import settings
from app.core.errors import AppException
from app.core.license_crypto import LicenseCrypto, sha256_text
from app.core.security import hash_password, verify_password
from app.modules.issue.models import Activation, Lease, License, Operator, VerifyLog
from app.modules.issue.schemas import (
    ActivationRequest,
    ActivationResponse,
    ActivationRecordResponse,
    LeaseRecordResponse,
    LeaseRenewRequest,
    LeaseRenewResponse,
    LicenseIssueRequest,
    LicenseIssueResponse,
    LicenseResponse,
    OfflineActivationRequestBundle,
    OfflineActivationResponseBundle,
    OfflineRenewRequestBundle,
    OfflineRenewResponseBundle,
    ProcessOfflineRenewRequestBody,
    ProcessOfflineRequestBody,
    RevokeRequest,
    SignedDocument,
    VerifyLogResponse,
    VerifyRequest,
    VerifyResponse,
)

OFFLINE_REQUEST_NONCE_TTL = settings.offline_request_ttl_seconds


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def isoformat(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return to_utc(value).isoformat()


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate(self, email: str, password: str) -> Operator | None:
        operator = self.db.query(Operator).filter(Operator.email == email).first()
        if not operator or not operator.is_active:
            return None
        if not verify_password(password, operator.password_hash):
            return None
        operator.last_login_at = utcnow()
        self.db.commit()
        return operator

    def create_operator(self, email: str, username: str, password: str) -> Operator:
        operator = Operator(
            email=email,
            username=username,
            password_hash=hash_password(password),
        )
        self.db.add(operator)
        self.db.commit()
        self.db.refresh(operator)
        return operator

    def get_by_email(self, email: str) -> Operator | None:
        return self.db.query(Operator).filter(Operator.email == email).first()


class LicenseService:
    def __init__(self, db: Session):
        self.db = db
        self.crypto = LicenseCrypto()

    def issue(
        self,
        req: LicenseIssueRequest,
        operator_id: uuid.UUID | None = None,
        client_ip: str | None = None,
    ) -> LicenseIssueResponse:
        if req.idempotency_key:
            existing = self.db.query(License).filter(License.idempotency_key == req.idempotency_key).first()
            if existing:
                return self._build_issue_response(existing)

        license_record = License(
            license_key=self._generate_license_key(),
            customer_name=req.customer_name,
            product_code=req.product_code,
            edition=req.edition,
            cluster_id=req.cluster_id,
            activation_mode=req.activation_mode,
            binding_policy=req.binding_policy,
            max_activations=req.max_activations,
            max_nodes=req.max_nodes,
            max_gpus=req.max_gpus,
            features=req.features,
            valid_from=req.valid_from,
            expires_at=req.expires_at,
            grace_period_days=req.grace_period_days,
            online_lease_ttl_hours=req.online_lease_ttl_hours,
            offline_lease_ttl_days=req.offline_lease_ttl_days,
            key_id=self.crypto.kid,
            schema_version="license.v2",
            certificate_payload={},
            signature="",
            idempotency_key=req.idempotency_key,
        )

        self.db.add(license_record)
        self.db.flush()

        payload = self._build_license_payload(license_record)
        certificate = self.crypto.sign_document(payload)
        license_record.certificate_payload = certificate["payload"]
        license_record.signature = certificate["signature"]

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if req.idempotency_key:
                existing = self.db.query(License).filter(License.idempotency_key == req.idempotency_key).first()
                if existing:
                    return self._build_issue_response(existing)
            raise AppException(409, "License 签发冲突，请重试") from exc

        self.db.refresh(license_record)
        self._write_audit(
            event_type=AuditEventType.LICENSE_ISSUED,
            license_key=license_record.license_key,
            operator_id=operator_id,
            client_ip=client_ip,
            cluster_id=license_record.cluster_id,
            detail={
                "license_id": str(license_record.id),
                "customer_name": license_record.customer_name,
                "activation_mode": license_record.activation_mode,
            },
        )
        self.db.commit()
        return self._build_issue_response(license_record)

    def list_licenses(self, page: int, size: int) -> tuple[Sequence[LicenseResponse], int]:
        total = self.db.query(func.count(License.id)).scalar() or 0
        licenses = (
            self.db.query(License)
            .order_by(desc(License.created_at))
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return [self._build_license_response(item) for item in licenses], total

    def get_license(self, license_id: uuid.UUID) -> License | None:
        return self.db.query(License).filter(License.id == license_id).first()

    def get_by_key(self, license_key: str) -> License | None:
        return self.db.query(License).filter(License.license_key == license_key).first()

    def get_license_detail(self, license_id: uuid.UUID) -> tuple[
        LicenseResponse,
        SignedDocument,
        list[ActivationRecordResponse],
        list[LeaseRecordResponse],
        list[VerifyLogResponse],
    ] | None:
        license_record = self.get_license(license_id)
        if not license_record:
            return None

        activations = (
            self.db.query(Activation)
            .filter(Activation.license_id == license_id)
            .order_by(desc(Activation.activated_at))
            .all()
        )
        leases = (
            self.db.query(Lease)
            .filter(Lease.license_id == license_id)
            .order_by(desc(Lease.created_at))
            .limit(20)
            .all()
        )
        logs = self.get_verify_logs(license_record.license_key)

        activation_items = [
            ActivationRecordResponse(
                id=item.id,
                cluster_id=item.cluster_id,
                machine_name=item.machine_name,
                install_key_fingerprint=item.install_key_fingerprint,
                mode=item.mode,
                status=item.status,
                activated_at=to_utc(item.activated_at),
                last_seen_at=to_utc(item.last_seen_at),
                last_lease_expires_at=to_utc(item.last_lease_expires_at) if item.last_lease_expires_at else None,
            )
            for item in activations
        ]
        lease_items = [
            LeaseRecordResponse(
                id=item.id,
                activation_id=item.activation_id,
                request_id=item.request_id,
                mode=item.mode,
                lease_expires_at=to_utc(item.lease_expires_at),
                created_at=to_utc(item.created_at),
            )
            for item in leases
        ]
        log_items = [
            VerifyLogResponse(
                id=item.id,
                license_key=item.license_key,
                cluster_id=item.cluster_id,
                client_ip=item.client_ip,
                result=item.result,
                created_at=to_utc(item.created_at),
            )
            for item in logs
        ]
        return (
            self._build_license_response(license_record, activations=activations),
            SignedDocument(
                schema_version=license_record.schema_version,
                kid=license_record.key_id,
                payload=license_record.certificate_payload,
                signature=license_record.signature,
            ),
            activation_items,
            lease_items,
            log_items,
        )

    def revoke(
        self,
        license_id: uuid.UUID,
        req: RevokeRequest,
        operator_id: uuid.UUID | None = None,
        client_ip: str | None = None,
    ) -> License | None:
        license_record = self.get_license(license_id)
        if not license_record:
            return None
        if license_record.revoked_at is not None:
            raise ValueError("License already revoked")

        now = utcnow()
        license_record.revoked_at = now
        license_record.revoked_reason = req.reason
        license_record.is_active = False
        (
            self.db.query(Activation)
            .filter(Activation.license_id == license_id, Activation.status == "active")
            .update({"status": "revoked", "updated_at": now})
        )
        self.db.commit()
        self.db.refresh(license_record)
        self._write_verify_log(license_record.license_key, license_record.cluster_id, None, "revoked")
        self._write_audit(
            event_type=AuditEventType.LICENSE_REVOKED,
            license_key=license_record.license_key,
            operator_id=operator_id,
            client_ip=client_ip,
            cluster_id=license_record.cluster_id,
            detail={"reason": req.reason},
        )
        self.db.commit()
        return license_record

    def delete_license(
        self,
        license_id: uuid.UUID,
        operator_id: uuid.UUID | None = None,
        client_ip: str | None = None,
    ) -> bool:
        record = self.db.query(License).filter(License.id == license_id).first()
        if not record:
            return False
        license_key = record.license_key
        customer_name = record.customer_name
        self.db.query(VerifyLog).filter(VerifyLog.license_key == license_key).delete()
        self.db.delete(record)
        self._write_audit(
            event_type=AuditEventType.LICENSE_DELETED,
            license_key=license_key,
            operator_id=operator_id,
            client_ip=client_ip,
            detail={"customer_name": customer_name},
        )
        self.db.commit()
        return True

    def activate(self, req: ActivationRequest, client_ip: str | None = None) -> ActivationResponse:
        license_record: License | None = None
        activation: Activation | None = None
        lease_request_id = req.request_id or f"activate-{uuid.uuid4()}"

        try:
            license_record = self._resolve_license_certificate(req.license_certificate)
            self._assert_license_active(license_record)
            self._assert_mode_supported(license_record, req.mode)

            binding_hash = self._build_binding_hash(license_record, req.cluster_id, req.fingerprint)
            install_key_fingerprint = self.crypto.public_key_fingerprint(req.install_public_key)
            activation = (
                self.db.query(Activation)
                .filter(Activation.license_id == license_record.id, Activation.fingerprint_hash == binding_hash)
                .first()
            )

            now = utcnow()
            if activation:
                if activation.install_key_fingerprint != install_key_fingerprint:
                    raise AppException(409, "该环境已绑定其他安装密钥")
                if activation.status != "active":
                    raise AppException(409, "该环境绑定已失效")
                activation.last_seen_at = now
            else:
                self._assert_prebound_cluster(license_record, req.cluster_id)
                current_activations = (
                    self.db.query(func.count(Activation.id))
                    .filter(Activation.license_id == license_record.id, Activation.status == "active")
                    .scalar()
                    or 0
                )
                if current_activations >= license_record.max_activations:
                    raise AppException(409, "已达到最大激活数")

                activation = Activation(
                    license_id=license_record.id,
                    fingerprint_hash=binding_hash,
                    cluster_id=req.cluster_id,
                    machine_name=req.machine_name,
                    install_public_key=req.install_public_key,
                    install_key_fingerprint=install_key_fingerprint,
                    mode=req.mode,
                    status="active",
                    lease_counter=0,
                    activated_at=now,
                    last_seen_at=now,
                )
                self.db.add(activation)
                self.db.flush()

            lease = self._issue_lease(license_record, activation, req.mode, lease_request_id)

            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                existing = self.db.query(Lease).filter(Lease.request_id == lease_request_id).first()
                if existing and activation and existing.activation_id == activation.id:
                    lease = existing
                    activation = self.db.query(Activation).filter(Activation.id == existing.activation_id).first()
                    if not activation:
                        raise AppException(409, "激活冲突，请重试") from exc
                else:
                    raise AppException(409, "激活冲突，请重试") from exc

            activation_certificate = self.crypto.sign_document(self._build_activation_payload(license_record, activation))
            self._detect_suspicious_activity(license_record, activation.cluster_id, client_ip)
            self._write_verify_log(license_record.license_key, activation.cluster_id, client_ip, f"activated_{req.mode}")
            self._write_audit(
                event_type=(
                    AuditEventType.ACTIVATION_SUCCESS_OFFLINE
                    if req.mode == "offline"
                    else AuditEventType.ACTIVATION_SUCCESS_ONLINE
                ),
                license_key=license_record.license_key,
                activation_id=activation.id,
                client_ip=client_ip,
                cluster_id=activation.cluster_id,
                detail={"mode": req.mode, "request_id": lease_request_id},
            )
            self.db.commit()

            return ActivationResponse(
                license_id=license_record.id,
                license_key=license_record.license_key,
                activation_id=activation.id,
                activation_certificate=SignedDocument.model_validate(activation_certificate),
                lease=self._signed_document_from_lease(lease),
            )
        except AppException as exc:
            self.db.rollback()
            self._write_audit(
                event_type=AuditEventType.ACTIVATION_FAILED,
                license_key=license_record.license_key if license_record else self._extract_license_key(req.license_certificate),
                client_ip=client_ip,
                cluster_id=req.cluster_id,
                detail={"mode": req.mode, "reason": exc.detail, "request_id": lease_request_id},
            )
            self.db.commit()
            raise

    def renew(
        self,
        req: LeaseRenewRequest,
        client_ip: str | None = None,
        *,
        skip_proof_verification: bool = False,
    ) -> LeaseRenewResponse:
        activation: Activation | None = None
        license_record: License | None = None

        try:
            activation = self.db.query(Activation).filter(Activation.id == req.activation_id).first()
            if not activation:
                raise AppException(404, "Activation 不存在")

            license_record = self.get_license(activation.license_id)
            if not license_record or license_record.license_key != req.license_key:
                raise AppException(404, "License 不存在")
            self._assert_license_active(license_record)
            self._assert_mode_supported(license_record, req.mode)
            if activation.status != "active":
                raise AppException(409, "Activation 已失效")

            existing_lease = self.db.query(Lease).filter(Lease.request_id == req.request_id).first()
            if existing_lease:
                if existing_lease.activation_id != activation.id:
                    raise AppException(409, "request_id 已被其他激活使用")
                return LeaseRenewResponse(
                    license_id=license_record.id,
                    license_key=license_record.license_key,
                    activation_id=activation.id,
                    lease=self._signed_document_from_lease(existing_lease),
                )

            if not skip_proof_verification:
                now = utcnow()
                client_time = to_utc(req.client_time)
                if abs((now - client_time).total_seconds()) > settings.proof_tolerance_seconds:
                    raise AppException(400, "续签证明已过期，请重新生成请求")

                proof_payload = self.build_renewal_proof_payload(
                    activation_id=activation.id,
                    license_key=license_record.license_key,
                    request_id=req.request_id,
                    client_time=client_time,
                    mode=req.mode,
                )
                try:
                    self.crypto.verify_proof(activation.install_public_key, proof_payload, req.proof)
                except (ValueError, binascii.Error) as exc:
                    raise AppException(401, "续签证明无效") from exc

            lease = self._issue_lease(license_record, activation, req.mode, req.request_id)
            self.db.commit()
            self._write_verify_log(license_record.license_key, activation.cluster_id, client_ip, f"renewed_{req.mode}")
            self._write_audit(
                event_type=(
                    AuditEventType.RENEWAL_SUCCESS_OFFLINE
                    if req.mode == "offline"
                    else AuditEventType.RENEWAL_SUCCESS_ONLINE
                ),
                license_key=license_record.license_key,
                activation_id=activation.id,
                client_ip=client_ip,
                cluster_id=activation.cluster_id,
                detail={"mode": req.mode, "request_id": req.request_id},
            )
            self.db.commit()

            return LeaseRenewResponse(
                license_id=license_record.id,
                license_key=license_record.license_key,
                activation_id=activation.id,
                lease=self._signed_document_from_lease(lease),
            )
        except AppException as exc:
            self.db.rollback()
            self._write_audit(
                event_type=AuditEventType.RENEWAL_FAILED,
                license_key=license_record.license_key if license_record else req.license_key,
                activation_id=req.activation_id,
                client_ip=client_ip,
                cluster_id=activation.cluster_id if activation else None,
                detail={"mode": req.mode, "reason": exc.detail, "request_id": req.request_id},
            )
            self.db.commit()
            raise

    def process_offline_activation(
        self,
        body: ProcessOfflineRequestBody,
        redis_client: Redis,
        operator_id: uuid.UUID | None = None,
        client_ip: str | None = None,
    ) -> OfflineActivationResponseBundle:
        bundle = body.request_bundle
        now = utcnow()
        request_time = to_utc(bundle.request_time)
        nonce_key = f"offline_nonce:{bundle.request_nonce}"

        if abs((now - request_time).total_seconds()) > OFFLINE_REQUEST_NONCE_TTL:
            self._write_audit(
                event_type=AuditEventType.ACTIVATION_FAILED,
                license_key=bundle.license_key,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=bundle.cluster_id,
                detail={"reason": "offline_request_expired", "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise AppException(400, "离线激活请求已过期，请重新在客户端生成请求包")

        if redis_client.exists(nonce_key):
            self._write_audit(
                event_type=AuditEventType.ACTIVATION_FAILED,
                license_key=bundle.license_key,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=bundle.cluster_id,
                detail={"reason": "offline_nonce_reused", "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise AppException(409, "该请求包已被处理过，请在客户端重新生成")

        if not bundle.cluster_id and not bundle.fingerprint:
            self._write_audit(
                event_type=AuditEventType.ACTIVATION_FAILED,
                license_key=bundle.license_key,
                operator_id=operator_id,
                client_ip=client_ip,
                detail={"reason": "missing_binding_value", "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise AppException(422, "cluster_id 和 fingerprint 至少提供一个")

        proof_payload = self.build_offline_activation_proof_payload(bundle)
        try:
            self.crypto.verify_proof(bundle.install_public_key, proof_payload, bundle.client_signature)
        except (ValueError, binascii.Error) as exc:
            self._write_audit(
                event_type=AuditEventType.INVALID_SIGNATURE,
                license_key=bundle.license_key,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=bundle.cluster_id,
                detail={"purpose": "offline_activation_request", "request_nonce": bundle.request_nonce},
            )
            self._write_audit(
                event_type=AuditEventType.ACTIVATION_FAILED,
                license_key=bundle.license_key,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=bundle.cluster_id,
                detail={"reason": "invalid_client_signature", "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise AppException(401, "客户端签名验证失败，请求包可能已被篡改") from exc

        license_record = self.get_by_key(bundle.license_key)
        if not license_record:
            self._write_audit(
                event_type=AuditEventType.ACTIVATION_FAILED,
                license_key=bundle.license_key,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=bundle.cluster_id,
                detail={"reason": "license_not_found", "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise AppException(404, "License 不存在")

        try:
            self._assert_license_active(license_record)
            self._assert_mode_supported(license_record, "offline")
        except AppException as exc:
            self._write_audit(
                event_type=AuditEventType.ACTIVATION_FAILED,
                license_key=bundle.license_key,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=bundle.cluster_id,
                detail={"reason": exc.detail, "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise

        activation_req = ActivationRequest(
            license_certificate=SignedDocument(
                schema_version=license_record.schema_version,
                kid=license_record.key_id,
                payload=license_record.certificate_payload,
                signature=license_record.signature,
            ),
            fingerprint=bundle.fingerprint,
            cluster_id=bundle.cluster_id,
            machine_name=bundle.machine_name,
            install_public_key=bundle.install_public_key,
            mode="offline",
            request_id=f"offline-activate-{bundle.request_nonce}",
        )
        result = self.activate(activation_req, client_ip=client_ip)

        redis_client.setex(nonce_key, OFFLINE_REQUEST_NONCE_TTL, "used")
        self._write_audit(
            event_type=AuditEventType.OFFLINE_BUNDLE_PROCESSED,
            license_key=result.license_key,
            activation_id=result.activation_id,
            operator_id=operator_id,
            client_ip=client_ip,
            cluster_id=bundle.cluster_id,
            detail={"request_nonce": bundle.request_nonce},
        )
        self.db.commit()

        return OfflineActivationResponseBundle(
            activation_certificate=result.activation_certificate,
            lease=result.lease,
            license_key=result.license_key,
            activation_id=result.activation_id,
            issued_at=now,
            expires_at=to_utc(license_record.expires_at),
        )

    def process_offline_renewal(
        self,
        body: ProcessOfflineRenewRequestBody,
        redis_client: Redis,
        operator_id: uuid.UUID | None = None,
        client_ip: str | None = None,
    ) -> OfflineRenewResponseBundle:
        bundle = body.request_bundle
        now = utcnow()
        request_time = to_utc(bundle.request_time)
        nonce_key = f"offline_nonce:{bundle.request_nonce}"

        if abs((now - request_time).total_seconds()) > OFFLINE_REQUEST_NONCE_TTL:
            self._write_audit(
                event_type=AuditEventType.RENEWAL_FAILED,
                license_key=bundle.license_key,
                activation_id=bundle.activation_id,
                operator_id=operator_id,
                client_ip=client_ip,
                detail={"reason": "offline_request_expired", "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise AppException(400, "离线续期请求已过期，请重新生成请求包")

        if redis_client.exists(nonce_key):
            self._write_audit(
                event_type=AuditEventType.RENEWAL_FAILED,
                license_key=bundle.license_key,
                activation_id=bundle.activation_id,
                operator_id=operator_id,
                client_ip=client_ip,
                detail={"reason": "offline_nonce_reused", "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise AppException(409, "该续期请求包已被处理过")

        activation = self.db.query(Activation).filter(Activation.id == bundle.activation_id).first()
        if not activation or activation.status != "active":
            self._write_audit(
                event_type=AuditEventType.RENEWAL_FAILED,
                license_key=bundle.license_key,
                activation_id=bundle.activation_id,
                operator_id=operator_id,
                client_ip=client_ip,
                detail={"reason": "activation_not_found_or_inactive", "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise AppException(404, "Activation 不存在或已失效")

        license_record = self.get_license(activation.license_id)
        if not license_record or license_record.license_key != bundle.license_key:
            self._write_audit(
                event_type=AuditEventType.RENEWAL_FAILED,
                license_key=bundle.license_key,
                activation_id=bundle.activation_id,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=activation.cluster_id,
                detail={"reason": "license_not_found", "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise AppException(404, "License 不存在")

        try:
            self._assert_license_active(license_record)
            self._assert_mode_supported(license_record, "offline")
        except AppException as exc:
            self._write_audit(
                event_type=AuditEventType.RENEWAL_FAILED,
                license_key=bundle.license_key,
                activation_id=bundle.activation_id,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=activation.cluster_id,
                detail={"reason": exc.detail, "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise

        if activation.last_lease_expires_at is None:
            self._write_audit(
                event_type=AuditEventType.RENEWAL_FAILED,
                license_key=bundle.license_key,
                activation_id=bundle.activation_id,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=activation.cluster_id,
                detail={"reason": "missing_current_lease", "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise AppException(409, "Activation 当前没有可续期的 Lease")

        current_lease_expires_at = to_utc(activation.last_lease_expires_at)
        bundle_lease_expires_at = to_utc(bundle.current_lease_expires_at)
        if abs((current_lease_expires_at - bundle_lease_expires_at).total_seconds()) > 1:
            self._write_audit(
                event_type=AuditEventType.RENEWAL_FAILED,
                license_key=bundle.license_key,
                activation_id=bundle.activation_id,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=activation.cluster_id,
                detail={
                    "reason": "stale_offline_lease",
                    "request_nonce": bundle.request_nonce,
                    "server_last_lease_expires_at": isoformat(current_lease_expires_at),
                    "bundle_current_lease_expires_at": isoformat(bundle_lease_expires_at),
                },
            )
            self.db.commit()
            raise AppException(409, "当前 Lease 不是最新版本，请先导入最新响应包")

        proof_payload = self.build_offline_renewal_proof_payload(bundle)
        try:
            self.crypto.verify_proof(activation.install_public_key, proof_payload, bundle.client_signature)
        except (ValueError, binascii.Error) as exc:
            self._write_audit(
                event_type=AuditEventType.INVALID_SIGNATURE,
                license_key=bundle.license_key,
                activation_id=bundle.activation_id,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=activation.cluster_id,
                detail={"purpose": "offline_renewal_request", "request_nonce": bundle.request_nonce},
            )
            self._write_audit(
                event_type=AuditEventType.RENEWAL_FAILED,
                license_key=bundle.license_key,
                activation_id=bundle.activation_id,
                operator_id=operator_id,
                client_ip=client_ip,
                cluster_id=activation.cluster_id,
                detail={"reason": "invalid_client_signature", "request_nonce": bundle.request_nonce},
            )
            self.db.commit()
            raise AppException(401, "客户端签名验证失败") from exc

        request_id = f"offline-renew-{bundle.request_nonce}"
        renew_req = LeaseRenewRequest(
            activation_id=bundle.activation_id,
            license_key=bundle.license_key,
            request_id=request_id,
            client_time=bundle.request_time,
            proof=bundle.client_signature,
            mode="offline",
        )
        result = self.renew(renew_req, client_ip=client_ip, skip_proof_verification=True)

        redis_client.setex(nonce_key, OFFLINE_REQUEST_NONCE_TTL, "used")
        self._write_audit(
            event_type=AuditEventType.OFFLINE_RENEWAL_PROCESSED,
            license_key=result.license_key,
            activation_id=result.activation_id,
            operator_id=operator_id,
            client_ip=client_ip,
            cluster_id=activation.cluster_id,
            detail={"request_nonce": bundle.request_nonce},
        )
        self.db.commit()

        lease_record = self.db.query(Lease).filter(Lease.request_id == request_id).first()
        return OfflineRenewResponseBundle(
            lease=result.lease,
            license_key=result.license_key,
            activation_id=result.activation_id,
            new_expires_at=to_utc(lease_record.lease_expires_at) if lease_record else to_utc(license_record.expires_at),
        )

    def get_verify_logs(self, license_key: str, limit: int = 10) -> Sequence[VerifyLog]:
        return (
            self.db.query(VerifyLog)
            .filter(VerifyLog.license_key == license_key)
            .order_by(desc(VerifyLog.created_at))
            .limit(limit)
            .all()
        )

    def build_renewal_proof_payload(
        self,
        activation_id: uuid.UUID,
        license_key: str,
        request_id: str,
        client_time: datetime,
        mode: str,
    ) -> dict[str, str]:
        return {
            "purpose": "lease_renewal",
            "activation_id": str(activation_id),
            "license_key": license_key,
            "request_id": request_id,
            "client_time": to_utc(client_time).isoformat(),
            "mode": mode,
        }

    def build_offline_activation_proof_payload(self, bundle: OfflineActivationRequestBundle) -> dict[str, object]:
        return {
            "purpose": "offline_activation_request",
            "license_key": bundle.license_key,
            "fingerprint": bundle.fingerprint,
            "cluster_id": bundle.cluster_id,
            "machine_name": bundle.machine_name,
            "install_public_key": bundle.install_public_key,
            "request_nonce": bundle.request_nonce,
            "request_time": to_utc(bundle.request_time).isoformat(),
        }

    def build_offline_renewal_proof_payload(self, bundle: OfflineRenewRequestBundle) -> dict[str, object]:
        return {
            "purpose": "offline_renewal_request",
            "activation_id": str(bundle.activation_id),
            "license_key": bundle.license_key,
            "current_lease_expires_at": to_utc(bundle.current_lease_expires_at).isoformat(),
            "request_nonce": bundle.request_nonce,
            "request_time": to_utc(bundle.request_time).isoformat(),
        }

    def _resolve_license_certificate(self, document: SignedDocument) -> License:
        try:
            payload = self.crypto.verify_document(document.model_dump())
        except (KeyError, ValueError, binascii.Error) as exc:
            raise AppException(400, "License 证书签名无效") from exc

        if payload.get("document_type") != "license":
            raise AppException(400, "证书类型不支持激活")

        license_id = payload.get("license_id")
        if not license_id:
            raise AppException(400, "证书缺少 license_id")

        try:
            parsed_license_id = uuid.UUID(str(license_id))
        except ValueError as exc:
            raise AppException(400, "证书中的 license_id 无效") from exc

        license_record = self.get_license(parsed_license_id)
        if not license_record or license_record.license_key != payload.get("license_key"):
            raise AppException(404, "License 不存在")

        if license_record.signature != document.signature or license_record.certificate_payload != document.payload:
            raise AppException(409, "当前 License 证书已更新，请使用最新版本")
        return license_record

    def _build_license_payload(self, license_record: License) -> dict[str, object]:
        return {
            "document_type": "license",
            "license_id": str(license_record.id),
            "license_key": license_record.license_key,
            "customer_name": license_record.customer_name,
            "product_code": license_record.product_code,
            "edition": license_record.edition,
            "activation_mode": license_record.activation_mode,
            "binding_policy": license_record.binding_policy,
            "binding_hint": {"cluster_id": license_record.cluster_id},
            "max_activations": license_record.max_activations,
            "max_nodes": license_record.max_nodes,
            "max_gpus": license_record.max_gpus,
            "features": license_record.features,
            "valid_from": isoformat(license_record.valid_from),
            "issued_at": isoformat(license_record.issued_at),
            "expires_at": isoformat(license_record.expires_at),
            "grace_period_days": license_record.grace_period_days,
            "online_lease_ttl_hours": license_record.online_lease_ttl_hours,
            "offline_lease_ttl_days": license_record.offline_lease_ttl_days,
            "nonce": secrets.token_hex(16),
        }

    def _build_activation_payload(self, license_record: License, activation: Activation) -> dict[str, object]:
        return {
            "document_type": "activation",
            "activation_id": str(activation.id),
            "license_id": str(license_record.id),
            "license_key": license_record.license_key,
            "fingerprint_hash": activation.fingerprint_hash,
            "cluster_id": activation.cluster_id,
            "install_key_fingerprint": activation.install_key_fingerprint,
            "mode": activation.mode,
            "activated_at": isoformat(activation.activated_at),
            "expires_at": isoformat(license_record.expires_at),
            "nonce": secrets.token_hex(16),
        }

    def _build_lease_payload(
        self,
        license_record: License,
        activation: Activation,
        lease_id: uuid.UUID,
        lease_expires_at: datetime,
        mode: str,
        sequence: int,
    ) -> dict[str, object]:
        result = {
            "document_type": "lease",
            "lease_id": str(lease_id),
            "license_id": str(license_record.id),
            "license_key": license_record.license_key,
            "activation_id": str(activation.id),
            "fingerprint_hash": activation.fingerprint_hash,
            "cluster_id": activation.cluster_id,
            "mode": mode,
            "sequence": sequence,
            "issued_at": isoformat(utcnow()),
            "expires_at": isoformat(lease_expires_at),
            "grace_period_days": license_record.grace_period_days,
            "nonce": secrets.token_hex(16),
        }
        if mode == "offline":
            result["offline_hard_deadline"] = isoformat(lease_expires_at)
        return result

    def _issue_lease(self, license_record: License, activation: Activation, mode: str, request_id: str) -> Lease:
        existing = self.db.query(Lease).filter(Lease.request_id == request_id).first()
        if existing:
            if existing.activation_id != activation.id:
                raise AppException(409, "request_id 已被其他激活使用")
            return existing

        self.db.query(Activation).filter(Activation.id == activation.id).update(
            {Activation.lease_counter: func.coalesce(Activation.lease_counter, 0) + 1},
            synchronize_session=False,
        )
        self.db.flush()
        self.db.refresh(activation, attribute_names=["lease_counter"])
        sequence = activation.lease_counter

        now = utcnow()
        lease_ttl = (
            timedelta(hours=license_record.online_lease_ttl_hours)
            if mode == "online"
            else timedelta(days=license_record.offline_lease_ttl_days)
        )
        lease_expires_at = min(to_utc(license_record.expires_at), now + lease_ttl)
        lease_id = uuid.uuid4()
        payload = self._build_lease_payload(license_record, activation, lease_id, lease_expires_at, mode, sequence)
        signed = self.crypto.sign_document(payload)

        lease = Lease(
            id=lease_id,
            license_id=license_record.id,
            activation_id=activation.id,
            request_id=request_id,
            mode=mode,
            key_id=signed["kid"],
            schema_version=signed["schema_version"],
            lease_sequence=sequence,
            certificate_payload=signed["payload"],
            signature=signed["signature"],
            lease_expires_at=lease_expires_at,
            created_at=now,
        )
        self.db.add(lease)

        activation.last_seen_at = now
        activation.last_lease_expires_at = lease_expires_at
        return lease

    def _signed_document_from_lease(self, lease: Lease) -> SignedDocument:
        return SignedDocument(
            schema_version=lease.schema_version,
            kid=lease.key_id,
            payload=lease.certificate_payload,
            signature=lease.signature,
        )

    def _build_license_response(
        self,
        license_record: License,
        activations: Optional[Sequence[Activation]] = None,
    ) -> LicenseResponse:
        activation_items = list(activations) if activations is not None else self._get_activations_for_license(license_record.id)
        current_activations = len([item for item in activation_items if item.status == "active"])
        ordered_activations = sorted(activation_items, key=lambda item: item.activated_at)
        first_activation = ordered_activations[0] if ordered_activations else None
        latest_lease_expires_at = None
        for item in activation_items:
            if item.last_lease_expires_at and (
                latest_lease_expires_at is None or item.last_lease_expires_at > latest_lease_expires_at
            ):
                latest_lease_expires_at = item.last_lease_expires_at

        return LicenseResponse(
            id=license_record.id,
            license_key=license_record.license_key,
            customer_name=license_record.customer_name,
            product_code=license_record.product_code,
            edition=license_record.edition,
            cluster_id=license_record.cluster_id,
            activation_mode=license_record.activation_mode,
            binding_policy=license_record.binding_policy,
            max_activations=license_record.max_activations,
            current_activations=current_activations,
            max_nodes=license_record.max_nodes,
            max_gpus=license_record.max_gpus,
            features=license_record.features,
            valid_from=to_utc(license_record.valid_from) if license_record.valid_from else None,
            issued_at=to_utc(license_record.issued_at),
            expires_at=to_utc(license_record.expires_at),
            used_at=to_utc(first_activation.activated_at) if first_activation else None,
            used_by_cluster_id=first_activation.cluster_id if first_activation else None,
            revoked_at=to_utc(license_record.revoked_at) if license_record.revoked_at else None,
            revoked_reason=license_record.revoked_reason,
            is_active=license_record.is_active,
            created_at=to_utc(license_record.created_at),
            grace_period_days=license_record.grace_period_days,
            online_lease_ttl_hours=license_record.online_lease_ttl_hours,
            offline_lease_ttl_days=license_record.offline_lease_ttl_days,
            key_id=license_record.key_id,
            schema_version=license_record.schema_version,
            latest_lease_expires_at=to_utc(latest_lease_expires_at) if latest_lease_expires_at else None,
        )

    def _build_issue_response(self, license_record: License) -> LicenseIssueResponse:
        document = SignedDocument(
            schema_version=license_record.schema_version,
            kid=license_record.key_id,
            payload=license_record.certificate_payload,
            signature=license_record.signature,
        )
        return LicenseIssueResponse(
            license_id=license_record.id,
            license_key=license_record.license_key,
            payload=license_record.certificate_payload,
            signature=license_record.signature,
            certificate=document,
        )

    def _get_activations_for_license(self, license_id: uuid.UUID) -> list[Activation]:
        return (
            self.db.query(Activation)
            .filter(Activation.license_id == license_id)
            .order_by(Activation.activated_at.asc())
            .all()
        )

    def _assert_license_active(self, license_record: License) -> None:
        now = utcnow()
        if license_record.revoked_at is not None or not license_record.is_active:
            raise AppException(409, "License 已吊销")
        if license_record.valid_from is not None and now < to_utc(license_record.valid_from):
            raise AppException(409, "License 尚未生效")
        if now > to_utc(license_record.expires_at):
            raise AppException(409, "License 已过期")

    def _assert_mode_supported(self, license_record: License, mode: str) -> None:
        supported = license_record.activation_mode
        if supported == "hybrid":
            return
        if supported != mode:
            raise AppException(409, f"该 License 不支持 {mode} 模式")

    def _assert_prebound_cluster(self, license_record: License, cluster_id: str | None) -> None:
        if license_record.cluster_id and cluster_id != license_record.cluster_id:
            raise AppException(409, "cluster_id 与许可预绑定值不一致")

    def _build_binding_hash(self, license_record: License, cluster_id: str | None, fingerprint: str | None) -> str:
        binding_policy = license_record.binding_policy

        if binding_policy == "cluster":
            if not cluster_id:
                raise AppException(422, "该 License 要求 cluster_id 绑定")
            self._assert_prebound_cluster(license_record, cluster_id)
            return sha256_text(f"cluster:{cluster_id}")

        if binding_policy == "fingerprint":
            if not fingerprint:
                raise AppException(422, "该 License 要求 fingerprint 绑定")
            return sha256_text(f"fingerprint:{fingerprint}")

        if license_record.cluster_id and cluster_id is None:
            cluster_id = license_record.cluster_id
        if cluster_id:
            self._assert_prebound_cluster(license_record, cluster_id)

        components = []
        if cluster_id:
            components.append(f"cluster:{cluster_id}")
        if fingerprint:
            components.append(f"fingerprint:{fingerprint}")
        if not components:
            raise AppException(422, "缺少有效的环境指纹")
        return sha256_text("|".join(components))

    def _generate_license_key(self) -> str:
        """
        Format: NVM-{UUID prefix}-{16 hex random chars}.
        The UUID prefix helps physical uniqueness and the random part adds 64-bit entropy.
        """
        for _ in range(5):
            uid_prefix = uuid.uuid4().hex[:8].upper()
            rand_part = secrets.token_hex(8).upper()
            candidate = f"NVM-{uid_prefix}-{rand_part}"
            exists = self.db.query(License.id).filter(License.license_key == candidate).first()
            if not exists:
                return candidate
        raise AppException(500, "生成 License Key 失败，请重试")

    def _write_verify_log(
        self,
        license_key: str,
        cluster_id: str | None,
        client_ip: str | None,
        result: str,
    ) -> None:
        self.db.add(
            VerifyLog(
                license_key=license_key,
                cluster_id=cluster_id,
                client_ip=client_ip,
                result=result,
            )
        )

    def _write_audit(
        self,
        *,
        event_type: str,
        license_key: str | None = None,
        activation_id: uuid.UUID | None = None,
        operator_id: uuid.UUID | None = None,
        client_ip: str | None = None,
        cluster_id: str | None = None,
        detail: dict[str, object] | None = None,
    ) -> None:
        write_audit_log(
            self.db,
            event_type=event_type,
            license_key=license_key,
            activation_id=activation_id,
            operator_id=operator_id,
            client_ip=client_ip,
            cluster_id=cluster_id,
            detail=detail,
        )

    def _extract_license_key(self, document: SignedDocument) -> str | None:
        license_key = document.payload.get("license_key")
        return str(license_key) if license_key else None

    def _detect_suspicious_activity(
        self,
        license_record: License,
        new_cluster_id: str | None,
        client_ip: str | None,
    ) -> None:
        if not client_ip:
            return

        recent_ips = (
            self.db.query(VerifyLog.client_ip)
            .filter(
                VerifyLog.license_key == license_record.license_key,
                VerifyLog.result.in_(["activated_online", "activated_offline"]),
                VerifyLog.created_at >= utcnow() - timedelta(hours=24),
                VerifyLog.client_ip.isnot(None),
            )
            .distinct()
            .all()
        )
        ip_set = {row[0] for row in recent_ips if row[0]}
        if client_ip in ip_set:
            return
        if len(ip_set) >= settings.suspicious_ip_threshold:
            self._write_audit(
                event_type=AuditEventType.SUSPICIOUS_MULTI_REGION,
                license_key=license_record.license_key,
                client_ip=client_ip,
                cluster_id=new_cluster_id,
                detail={"existing_ips": sorted(ip_set), "new_ip": client_ip, "cluster_id": new_cluster_id},
            )


class LicenseVerifier:
    def __init__(self, db: Session):
        self.db = db
        self.crypto = LicenseCrypto()

    def verify(self, req: VerifyRequest, client_ip: str | None = None) -> VerifyResponse:
        license_data = req.license_data
        try:
            payload = self.crypto.verify_document(license_data)
        except KeyError:
            self._log(req, "invalid_format", client_ip)
            return VerifyResponse(valid=False, reason="invalid_format")
        except (ValueError, binascii.Error):
            self._log(req, "invalid_signature", client_ip)
            return VerifyResponse(valid=False, reason="invalid_signature")

        document_type = str(payload.get("document_type") or "license")
        if document_type == "license":
            return self._verify_license_document(payload, req, client_ip)
        if document_type == "lease":
            return self._verify_lease_document(payload, req, client_ip)

        self._log(req, "unsupported_document", client_ip)
        return VerifyResponse(valid=False, reason="unsupported_document", payload=payload, document_type=document_type)

    def _verify_license_document(self, payload: dict[str, object], req: VerifyRequest, client_ip: str | None) -> VerifyResponse:
        license_record = self._find_license_from_payload(payload)
        if not license_record:
            self._log(req, "invalid_key", client_ip)
            return VerifyResponse(valid=False, reason="invalid_key", payload=payload, document_type="license")

        now = utcnow()
        if license_record.revoked_at is not None or not license_record.is_active:
            self._log(req, "revoked", client_ip)
            return VerifyResponse(valid=False, reason="revoked", payload=payload, document_type="license")
        if license_record.valid_from is not None and now < to_utc(license_record.valid_from):
            self._log(req, "not_started", client_ip)
            return VerifyResponse(valid=False, reason="not_started", payload=payload, document_type="license")
        if now > to_utc(license_record.expires_at):
            self._log(req, "expired", client_ip)
            return VerifyResponse(valid=False, reason="expired", payload=payload, document_type="license")

        if license_record.binding_policy in {"cluster", "hybrid"} and license_record.cluster_id:
            if req.cluster_id and req.cluster_id != license_record.cluster_id:
                self._log(req, "binding_mismatch", client_ip)
                return VerifyResponse(valid=False, reason="binding_mismatch", payload=payload, document_type="license")

        self._log(req, "success", client_ip)
        return VerifyResponse(valid=True, payload=payload, document_type="license")

    def _verify_lease_document(self, payload: dict[str, object], req: VerifyRequest, client_ip: str | None) -> VerifyResponse:
        lease_id = payload.get("lease_id")
        if not lease_id:
            self._log(req, "invalid_key", client_ip)
            return VerifyResponse(valid=False, reason="invalid_key", payload=payload, document_type="lease")

        try:
            parsed_lease_id = uuid.UUID(str(lease_id))
        except ValueError:
            self._log(req, "invalid_key", client_ip)
            return VerifyResponse(valid=False, reason="invalid_key", payload=payload, document_type="lease")

        lease = self.db.query(Lease).filter(Lease.id == parsed_lease_id).first()
        if not lease:
            self._log(req, "invalid_key", client_ip)
            return VerifyResponse(valid=False, reason="invalid_key", payload=payload, document_type="lease")

        license_record = self.db.query(License).filter(License.id == lease.license_id).first()
        if not license_record:
            self._log(req, "invalid_key", client_ip)
            return VerifyResponse(valid=False, reason="invalid_key", payload=payload, document_type="lease")

        now = utcnow()
        if license_record.revoked_at is not None or not license_record.is_active:
            self._log(req, "revoked", client_ip)
            return VerifyResponse(valid=False, reason="revoked", payload=payload, document_type="lease")
        if now > to_utc(lease.lease_expires_at):
            self._log(req, "expired", client_ip)
            return VerifyResponse(valid=False, reason="expired", payload=payload, document_type="lease")
        if payload.get("mode") == "offline":
            hard_deadline_str = payload.get("offline_hard_deadline")
            if hard_deadline_str:
                try:
                    hard_deadline = datetime.fromisoformat(str(hard_deadline_str))
                    hard_deadline = to_utc(hard_deadline)
                    if now > hard_deadline:
                        self._log(req, "offline_hard_deadline_exceeded", client_ip)
                        return VerifyResponse(
                            valid=False,
                            reason="offline_hard_deadline_exceeded",
                            payload=payload,
                            document_type="lease",
                        )
                except (ValueError, TypeError):
                    pass

        activation = self.db.query(Activation).filter(Activation.id == lease.activation_id).first()
        if not activation or activation.status != "active":
            self._log(req, "activation_invalid", client_ip)
            return VerifyResponse(valid=False, reason="activation_invalid", payload=payload, document_type="lease")

        payload_sequence = payload.get("sequence")
        if payload_sequence is not None:
            try:
                parsed_sequence = int(payload_sequence)
            except (TypeError, ValueError):
                self._log(req, "sequence_mismatch", client_ip)
                return VerifyResponse(valid=False, reason="sequence_mismatch", payload=payload, document_type="lease")
            if parsed_sequence != lease.lease_sequence:
                self._log(req, "sequence_mismatch", client_ip)
                return VerifyResponse(valid=False, reason="sequence_mismatch", payload=payload, document_type="lease")

        self._log(req, "success", client_ip)
        return VerifyResponse(valid=True, payload=payload, document_type="lease")

    def _find_license_from_payload(self, payload: dict[str, object]) -> License | None:
        license_id = payload.get("license_id")
        if license_id:
            try:
                parsed_id = uuid.UUID(str(license_id))
            except ValueError:
                return None
            return self.db.query(License).filter(License.id == parsed_id).first()
        license_key = payload.get("license_key")
        if license_key:
            return self.db.query(License).filter(License.license_key == str(license_key)).first()
        return None

    def _log(self, req: VerifyRequest, result: str, client_ip: Optional[str]):
        payload = req.license_data.get("payload", {}) if isinstance(req.license_data, dict) else {}
        license_key = str(payload.get("license_key", "unknown"))
        log = VerifyLog(
            license_key=license_key,
            cluster_id=req.cluster_id,
            client_ip=client_ip,
            result=result,
        )
        self.db.add(log)
        if result == "invalid_signature":
            write_audit_log(
                self.db,
                event_type=AuditEventType.INVALID_SIGNATURE,
                license_key=license_key,
                client_ip=client_ip,
                cluster_id=req.cluster_id,
                detail={"source": "public_verify"},
            )
        self.db.commit()
