import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.identity.security import utc_now
from agent.registry.models import AgentVersion
from agent.registry.schema import PublishedAgent


class PublishedVersionConflict(ValueError):
    pass


def publish(db: Session, tenant_id: UUID, agent: PublishedAgent) -> AgentVersion:
    existing = db.get(AgentVersion, (tenant_id, agent.agent_id, agent.version))
    if existing is not None:
        raise PublishedVersionConflict("Published agent versions are immutable")
    snapshot = agent.model_dump(mode="json")
    raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    row = AgentVersion(tenant_id=tenant_id, agent_id=agent.agent_id, version=agent.version,
                       snapshot=snapshot, snapshot_hash=hashlib.sha256(raw).hexdigest(), published_at=utc_now())
    db.add(row)
    db.commit()
    return row


def load(db: Session, tenant_id: UUID, agent_id: str, version: str) -> PublishedAgent | None:
    row = db.get(AgentVersion, (tenant_id, agent_id, version))
    if row is None:
        return None
    raw = json.dumps(row.snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if hashlib.sha256(raw).hexdigest() != row.snapshot_hash:
        raise ValueError("Published agent snapshot hash mismatch")
    return PublishedAgent.model_validate(row.snapshot)


def list_versions(db: Session, tenant_id: UUID) -> list[AgentVersion]:
    return list(db.scalars(select(AgentVersion).where(AgentVersion.tenant_id == tenant_id).order_by(AgentVersion.agent_id, AgentVersion.version)))

