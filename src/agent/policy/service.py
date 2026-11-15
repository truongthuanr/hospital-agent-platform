from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from agent.contracts.types import ActorContext, ActorType
from agent.identity.models import AuditRecord
from agent.identity.security import utc_now


@dataclass(frozen=True)
class PolicyResource:
    type: str
    id: str | None
    tenant_id: UUID
    owner_session_id: UUID | None = None
    state: str | None = None


def decide(actor: ActorContext, action: str, resource: PolicyResource,
           pinned_policy_version: str = "foundation-v1", tool_contract_version: str | None = None) -> bool:
    if actor.tenant_id != resource.tenant_id or pinned_policy_version != "foundation-v1":
        return False
    if tool_contract_version is not None:
        return False  # No tool contracts exist in the foundation release.
    if action == "agents:list":
        return actor.actor_type in {ActorType.PATIENT, ActorType.STAFF}
    if action == "agents:publish":
        return actor.actor_type == ActorType.STAFF and "agent_developer" in actor.roles
    if action == "execution:read":
        return resource.owner_session_id == actor.session_id or (actor.actor_type == ActorType.STAFF and "staff" in actor.roles)
    if action == "handoff:read":
        return actor.actor_type == ActorType.STAFF and "staff" in actor.roles
    return False


def authorize(db: Session, actor: ActorContext, action: str, resource: PolicyResource,
              pinned_policy_version: str = "foundation-v1", tool_contract_version: str | None = None) -> bool:
    allowed = decide(actor, action, resource, pinned_policy_version, tool_contract_version)
    db.add(AuditRecord(id=uuid4(), tenant_id=actor.tenant_id, actor_id=actor.actor_id, action=action,
                       resource_type=resource.type, resource_id=resource.id, policy_result="allow" if allowed else "deny",
                       outcome="evaluated", trace_id=actor.trace_id, created_at=utc_now()))
    db.commit()
    return allowed

