from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Operator(Base):
    __tablename__ = "operators"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_code: Mapped[str] = mapped_column(String(100), default="naviam")
    edition: Mapped[str] = mapped_column(String(50), default="enterprise")
    cluster_id: Mapped[Optional[str]] = mapped_column(String(128))
    activation_mode: Mapped[str] = mapped_column(String(20), default="hybrid")
    binding_policy: Mapped[str] = mapped_column(String(20), default="hybrid")
    max_activations: Mapped[int] = mapped_column(Integer, default=1)
    max_nodes: Mapped[int] = mapped_column(Integer, default=0)
    max_gpus: Mapped[int] = mapped_column(Integer, default=0)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grace_period_days: Mapped[int] = mapped_column(Integer, default=settings.license_grace_period_days)
    online_lease_ttl_hours: Mapped[int] = mapped_column(Integer, default=settings.online_lease_ttl_hours)
    offline_lease_ttl_days: Mapped[int] = mapped_column(Integer, default=settings.offline_lease_ttl_days)
    key_id: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), default="license.v2")
    certificate_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Activation(Base):
    __tablename__ = "license_activations"
    __table_args__ = (
        UniqueConstraint("license_id", "fingerprint_hash", name="uq_activation_license_fingerprint"),
        UniqueConstraint("license_id", "install_key_fingerprint", name="uq_activation_license_install_key"),
        Index("ix_activation_license_status", "license_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("licenses.id", ondelete="CASCADE"),
        nullable=False,
    )
    fingerprint_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    cluster_id: Mapped[Optional[str]] = mapped_column(String(128))
    machine_name: Mapped[Optional[str]] = mapped_column(String(255))
    install_public_key: Mapped[str] = mapped_column(Text, nullable=False)
    install_key_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="online")
    status: Mapped[str] = mapped_column(String(20), default="active")
    lease_counter: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Lease(Base):
    __tablename__ = "license_leases"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_lease_request_id"),
        Index("ix_lease_activation_created", "activation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("licenses.id", ondelete="CASCADE"),
        nullable=False,
    )
    activation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("license_activations.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="online")
    key_id: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), default="license.v2")
    lease_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    certificate_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VerifyLog(Base):
    __tablename__ = "verify_logs"
    __table_args__ = (Index("ix_verify_logs_license_created", "license_key", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    license_key: Mapped[str] = mapped_column(String(255), nullable=False)
    cluster_id: Mapped[Optional[str]] = mapped_column(String(128))
    client_ip: Mapped[Optional[str]] = mapped_column(String(45))
    result: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_event_created", "event_type", "created_at"),
        Index("ix_audit_logs_license_key", "license_key"),
        Index("ix_audit_logs_operator", "operator_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    license_key: Mapped[Optional[str]] = mapped_column(String(255))
    activation_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    operator_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    client_ip: Mapped[Optional[str]] = mapped_column(String(45))
    cluster_id: Mapped[Optional[str]] = mapped_column(String(128))
    detail: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
