import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, Session, mapped_column

from agent.db import Base


class IdempotencyStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (Index("ix_idempotency_expires", "expires_at"),)

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), primary_key=True)
    operation_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    result_ref: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IdempotencyConflict(ValueError):
    pass


def validate_key(key: str | None) -> str:
    if key is None or not key or key != key.strip() or len(key.encode("utf-8")) > 128:
        raise ValueError("Idempotency-Key must be a nonempty opaque value of at most 128 bytes")
    if any(ord(ch) < 33 or ord(ch) > 126 for ch in key):
        raise ValueError("Idempotency-Key must contain printable ASCII without spaces")
    return key


def _reject_nonfinite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite numbers are not supported")
    if isinstance(value, dict):
        for item in value.values():
            _reject_nonfinite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_nonfinite(item)


def canonical_request_hash(method: str, resource_id: str, body: dict[str, Any], agent_version: str | None) -> str:
    value = {"method": method.upper(), "resource_id": resource_id, "body": body, "agent_version": agent_version}
    _reject_nonfinite(value)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class IdempotencyResult:
    status: IdempotencyStatus
    result_ref: str | None


def inspect_record(session: Session, tenant_id: UUID, operation_type: str, key: str, request_hash: str) -> IdempotencyResult | None:
    """Stage 1 calls this under its admission transaction and row lock."""
    validate_key(key)
    record = session.get(IdempotencyRecord, (tenant_id, operation_type, key), with_for_update=True)
    if record is None:
        return None
    if record.request_hash != request_hash:
        raise IdempotencyConflict("Idempotency key was already used with a different request")
    return IdempotencyResult(IdempotencyStatus(record.status), record.result_ref)


def minimum_expiry(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    return now.astimezone(timezone.utc) + timedelta(days=7)

