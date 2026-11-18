from uuid import uuid4

from sqlalchemy import select

from agent.config import get_settings
from agent.db import SessionLocal
from agent.identity.models import DemoAccount, Tenant
from agent.identity.security import hash_password
from agent.registry.schema import PublishedAgent, StepDefinition, StepType, VersionReferences
from agent.registry.service import load, publish


def seed() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        tenant = db.get(Tenant, settings.synthetic_tenant_id)
        if tenant is None:
            db.add(Tenant(id=settings.synthetic_tenant_id, name="Synthetic Hospital"))
            db.flush()
        account = db.scalar(select(DemoAccount).where(DemoAccount.tenant_id == settings.synthetic_tenant_id,
                                                       DemoAccount.username == settings.demo_staff_username))
        if account is None:
            db.add(DemoAccount(id=uuid4(), tenant_id=settings.synthetic_tenant_id,
                               username=settings.demo_staff_username, password_hash=hash_password(settings.demo_staff_password),
                               role="agent_developer"))
        db.commit()

        if load(db, settings.synthetic_tenant_id, "hospital_frontdesk", "foundation-1") is None:
            agent = PublishedAgent(schema_version="1", agent_id="hospital_frontdesk", version="foundation-1", start_step="start",
                steps=(StepDefinition(step_id="start", type=StepType.RULE, successors=("done",)),
                       StepDefinition(step_id="done", type=StepType.FINAL)),
                refs=VersionReferences(workflow="foundation-1"))
            publish(db, settings.synthetic_tenant_id, agent)


if __name__ == "__main__":
    seed()
