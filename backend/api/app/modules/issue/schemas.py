from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional, Sequence

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    email: str
    username: str


class SignedDocument(BaseModel):
    schema_version: str = "license.v2"
    kid: str
    payload: dict[str, Any]
    signature: str


class LicenseIssueRequest(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=255)
    max_nodes: int = Field(..., ge=1, le=10000)
    max_gpus: int = Field(0, ge=0, le=10000)
    valid_from: Optional[datetime] = None
    expires_at: datetime
    cluster_id: Optional[str] = Field(None, max_length=128)
    product_code: str = Field("naviam", min_length=1, max_length=100)
    edition: str = Field("enterprise", min_length=1, max_length=50)
    features: dict[str, Any] = Field(default_factory=dict)
    activation_mode: Literal["online", "offline", "hybrid"] = "hybrid"
    binding_policy: Literal["cluster", "fingerprint", "hybrid"] = "hybrid"
    max_activations: int = Field(1, ge=1, le=100)
    grace_period_days: int = Field(7, ge=0, le=90)
    online_lease_ttl_hours: int = Field(24, ge=1, le=720)
    offline_lease_ttl_days: int = Field(30, ge=1, le=365)
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=128)

    @field_validator("expires_at")
    @classmethod
    def expires_at_must_be_future(cls, value: datetime) -> datetime:
        now = datetime.now(value.tzinfo) if value.tzinfo else datetime.now()
        if value <= now:
            raise ValueError("过期时间必须大于当前时间")
        return value

    @field_validator("valid_from")
    @classmethod
    def valid_from_must_be_before_expires(cls, value: Optional[datetime], info) -> Optional[datetime]:
        if value is None:
            return value
        expires_at = info.data.get("expires_at")
        if expires_at and value >= expires_at:
            raise ValueError("开始时间必须小于过期时间")
        return value


class LicenseResponse(BaseModel):
    id: uuid.UUID
    license_key: str
    customer_name: str
    product_code: str
    edition: str
    cluster_id: Optional[str]
    activation_mode: str
    binding_policy: str
    max_activations: int
    current_activations: int
    max_nodes: int
    max_gpus: int
    features: dict[str, Any]
    valid_from: Optional[datetime]
    issued_at: datetime
    expires_at: datetime
    used_at: Optional[datetime]
    used_by_cluster_id: Optional[str]
    revoked_at: Optional[datetime]
    revoked_reason: Optional[str]
    is_active: bool
    created_at: datetime
    grace_period_days: int
    online_lease_ttl_hours: int
    offline_lease_ttl_days: int
    key_id: str
    schema_version: str
    latest_lease_expires_at: Optional[datetime]

    @computed_field
    @property
    def status(self) -> str:
        reference_now = datetime.now(self.expires_at.tzinfo) if self.expires_at.tzinfo else datetime.now()
        if self.revoked_at is not None or not self.is_active:
            return "revoked"
        if self.valid_from is not None and reference_now < self.valid_from:
            return "not_started"
        if reference_now > self.expires_at:
            return "expired"
        return "active"


class LicenseIssueResponse(BaseModel):
    license_id: uuid.UUID
    license_key: str
    payload: dict[str, Any]
    signature: str
    certificate: SignedDocument


class LicenseListResponse(BaseModel):
    items: Sequence[LicenseResponse]
    total: int
    page: int
    size: int
    pages: int


class VerifyLogResponse(BaseModel):
    id: int
    license_key: str
    cluster_id: Optional[str]
    client_ip: Optional[str]
    result: str
    created_at: datetime


class ActivationRecordResponse(BaseModel):
    id: uuid.UUID
    cluster_id: Optional[str]
    machine_name: Optional[str]
    install_key_fingerprint: str
    mode: str
    status: str
    activated_at: datetime
    last_seen_at: datetime
    last_lease_expires_at: Optional[datetime]


class LeaseRecordResponse(BaseModel):
    id: uuid.UUID
    activation_id: uuid.UUID
    request_id: str
    mode: str
    lease_expires_at: datetime
    created_at: datetime


class LicenseDetailResponse(BaseModel):
    license: LicenseResponse
    certificate: SignedDocument
    activations: Sequence[ActivationRecordResponse]
    leases: Sequence[LeaseRecordResponse]
    verify_logs: Sequence[VerifyLogResponse]


class RevokeRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=1000)


class RevokeResponse(BaseModel):
    success: bool


class DeleteResponse(BaseModel):
    success: bool


class ActivationRequest(BaseModel):
    license_certificate: SignedDocument
    cluster_id: Optional[str] = Field(None, max_length=128)
    fingerprint: Optional[str] = Field(None, max_length=512)
    machine_name: Optional[str] = Field(None, max_length=255)
    install_public_key: str = Field(..., min_length=32)
    request_id: Optional[str] = Field(None, min_length=8, max_length=128)
    mode: Literal["online", "offline"] = "online"

    @model_validator(mode="after")
    def require_binding_value(self):
        if not self.cluster_id and not self.fingerprint:
            raise ValueError("cluster_id 和 fingerprint 至少提供一个")
        return self


class LeaseRenewRequest(BaseModel):
    activation_id: uuid.UUID
    license_key: str = Field(..., min_length=8, max_length=255)
    request_id: str = Field(..., min_length=8, max_length=128)
    client_time: datetime
    proof: str = Field(..., min_length=32)
    mode: Literal["online", "offline"] = "online"


class OfflineActivationRequestBundle(BaseModel):
    """Activation request bundle generated by the offline client."""

    license_key: str = Field(..., min_length=8, max_length=255)
    fingerprint: Optional[str] = None
    cluster_id: Optional[str] = None
    machine_name: Optional[str] = None
    install_public_key: str = Field(..., min_length=32)
    request_nonce: str = Field(..., min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    request_time: datetime
    client_signature: str = Field(..., min_length=32)


class OfflineActivationResponseBundle(BaseModel):
    """Activation response bundle generated by the platform for offline import."""

    activation_certificate: SignedDocument
    lease: SignedDocument
    license_key: str
    activation_id: uuid.UUID
    issued_at: datetime
    expires_at: datetime
    bundle_format_version: str = "v1"


class OfflineRenewRequestBundle(BaseModel):
    """Renewal request bundle generated by the offline client."""

    activation_id: uuid.UUID
    license_key: str = Field(..., min_length=8, max_length=255)
    current_lease_expires_at: datetime
    request_nonce: str = Field(..., min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    request_time: datetime
    client_signature: str = Field(..., min_length=32)


class OfflineRenewResponseBundle(BaseModel):
    """Renewal response bundle generated by the platform for offline import."""

    lease: SignedDocument
    license_key: str
    activation_id: uuid.UUID
    new_expires_at: datetime
    bundle_format_version: str = "v1"


class ProcessOfflineRequestBody(BaseModel):
    request_bundle: OfflineActivationRequestBundle


class ProcessOfflineRenewRequestBody(BaseModel):
    request_bundle: OfflineRenewRequestBundle


class ActivationResponse(BaseModel):
    license_id: uuid.UUID
    license_key: str
    activation_id: uuid.UUID
    activation_certificate: SignedDocument
    lease: SignedDocument


class LeaseRenewResponse(BaseModel):
    license_id: uuid.UUID
    license_key: str
    activation_id: uuid.UUID
    lease: SignedDocument


class VerifyRequest(BaseModel):
    license_data: dict[str, Any]
    cluster_id: Optional[str] = None
    fingerprint: Optional[str] = None


class VerifyResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    document_type: Optional[str] = None
