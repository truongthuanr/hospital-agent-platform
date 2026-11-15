from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, JSON, String, Uuid, event
from sqlalchemy.orm import Mapped, mapped_column

from agent.db import Base


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)



@event.listens_for(AgentVersion, "before_update")
@event.listens_for(AgentVersion, "before_delete")
def reject_published_change(*_args: object) -> None:
    raise ValueError("Published agent versions are immutable")
