from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from agent.api.main import app
from agent.config import get_settings
from agent.contracts.idempotency import (
    IdempotencyConflict, IdempotencyRecord, IdempotencyStatus, canonical_request_hash,
    inspect_record, minimum_expiry, validate_key,
)
from agent.contracts.types import ActorContext, ActorType
from agent.db import Base, get_session
from agent.identity.models import AuditRecord, AuthSession, DemoAccount, Tenant
from agent.identity.security import hash_password, hash_token, utc_now
from agent.policy.service import PolicyResource, decide
from agent.registry.models import AgentVersion
from agent.registry.schema import PublishedAgent, StepDefinition, StepType, VersionReferences
from agent.registry.service import PublishedVersionConflict, load, publish


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(db_engine, monkeypatch):
    from agent.api import main

    monkeypatch.setattr(main, "engine", db_engine)
    settings = get_settings()
    with Session(db_engine) as db:
        db.add(Tenant(id=settings.synthetic_tenant_id, name="Synthetic Hospital"))
        db.add(DemoAccount(id=uuid4(), tenant_id=settings.synthetic_tenant_id, username="demo_staff",
                           password_hash=hash_password(settings.demo_staff_password), role="agent_developer"))
        db.commit()

    def test_session():
        with Session(db_engine) as db:
            yield db

    app.dependency_overrides[get_session] = test_session
    try:
        yield TestClient(app), db_engine
    finally:
        app.dependency_overrides.clear()


def test_idempotency_canonicalization_and_conflict(db_engine):
    settings = get_settings()
    first = canonical_request_hash("post", "hospital_frontdesk", {"b": 2, "a": 1}, "1")
    assert first == canonical_request_hash("POST", "hospital_frontdesk", {"a": 1, "b": 2}, "1")
    assert first != canonical_request_hash("POST", "hospital_frontdesk", {"a": 1, "b": 3}, "1")
    with pytest.raises(ValueError):
        canonical_request_hash("POST", "x", {"value": float("nan")}, None)
    for invalid in ("", " bad", "a b", "x" * 129):
        with pytest.raises(ValueError):
            validate_key(invalid)
    assert validate_key("opaque-key") == "opaque-key"
    now = utc_now()
    assert minimum_expiry(now) >= now + timedelta(days=7)
    with Session(db_engine) as db:
        db.add(Tenant(id=settings.synthetic_tenant_id, name="Synthetic Hospital"))
        db.add(IdempotencyRecord(tenant_id=settings.synthetic_tenant_id, operation_type="create_execution",
                                 key="opaque-key", request_hash=first, status=IdempotencyStatus.IN_PROGRESS.value,
                                 result_ref=None, created_at=now, expires_at=minimum_expiry(now)))
        db.commit()
        assert inspect_record(db, settings.synthetic_tenant_id, "create_execution", "opaque-key", first).status == IdempotencyStatus.IN_PROGRESS
        with pytest.raises(IdempotencyConflict):
            inspect_record(db, settings.synthetic_tenant_id, "create_execution", "opaque-key", "0" * 64)


def test_workflow_validation_and_immutable_publication(db_engine):
    settings = get_settings()
    agent = PublishedAgent(agent_id="hospital_frontdesk", version="1", start_step="start",
                           steps=(StepDefinition(step_id="start", type=StepType.RULE, successors=("done",)),
                                  StepDefinition(step_id="done", type=StepType.FINAL)),
                           refs=VersionReferences(workflow="1"))
    with Session(db_engine) as db:
        db.add(Tenant(id=settings.synthetic_tenant_id, name="Synthetic Hospital"))
        db.commit()
        publish(db, settings.synthetic_tenant_id, agent)
        assert load(db, settings.synthetic_tenant_id, "hospital_frontdesk", "1") == agent
        with pytest.raises(PublishedVersionConflict):
            publish(db, settings.synthetic_tenant_id, agent)
        row = db.get(AgentVersion, (settings.synthetic_tenant_id, "hospital_frontdesk", "1"))
        row.snapshot_hash = "0" * 64
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
    with pytest.raises(ValidationError):
        PublishedAgent(agent_id="x", version="1", start_step="start",
                       steps=(StepDefinition(step_id="start", type=StepType.RULE, successors=("start",)),),
                       refs=VersionReferences(workflow="1"))


def test_sessions_policy_audit_and_api(client):
    http, engine = client
    settings = get_settings()
    assert http.get("/health/live").status_code == 200
    assert http.get("/health/ready").status_code == 200
    missing = http.get("/missing-route")
    assert missing.status_code == 404 and missing.json()["error_code"] == "not_found"
    patient_response = http.post("/session/patient")
    assert patient_response.status_code == 201
    patient_token = patient_response.json()["token"]
    assert "X-Trace-Id" in patient_response.headers
    with Session(engine) as db:
        row = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(patient_token, settings)))
        assert row is not None and row.token_hash != patient_token
        patient_session_id = row.id
    patient_headers = {"Authorization": f"Bearer {patient_token}"}
    assert http.get("/agents", headers=patient_headers).status_code == 200
    denied = http.post("/agents/versions", headers=patient_headers, json={})
    assert denied.status_code == 422  # Invalid schema is rejected before policy.
    agent = {"agent_id": "x", "version": "1", "start_step": "done", "steps": [{"step_id": "done", "type": "FINAL"}],
             "refs": {"workflow": "1"}}
    denied = http.post("/agents/versions", headers=patient_headers, json=agent)
    assert denied.status_code == 403
    assert denied.json()["error_code"] == "forbidden"
    staff = http.post("/session/staff", json={"username": "demo_staff", "password": settings.demo_staff_password})
    assert staff.status_code == 200
    staff_headers = {"Authorization": f"Bearer {staff.json()['token']}"}
    created = http.post("/agents/versions", headers=staff_headers, json=agent)
    assert created.status_code == 201
    assert http.post("/agents/versions", headers=staff_headers, json=agent).status_code == 409
    assert http.get("/agents/x/versions/1", headers=patient_headers).json()["version"] == "1"
    with Session(engine) as db:
        session = db.get(AuthSession, patient_session_id)
        session.revoked_at = utc_now()
        db.commit()
    assert http.get("/agents", headers=patient_headers).status_code == 401
    another = http.post("/session/patient").json()["token"]
    with Session(engine) as db:
        row = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(another, settings)))
        row.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert http.get("/agents", headers={"Authorization": f"Bearer {another}"}).status_code == 401
    with Session(engine) as db:
        assert db.scalar(select(AuditRecord).where(AuditRecord.action == "agents:publish", AuditRecord.policy_result == "deny")) is not None


def test_default_deny_and_ownership(db_engine):
    settings = get_settings()
    owner = uuid4()
    actor = ActorContext(actor_id=uuid4(), actor_type=ActorType.PATIENT, session_id=owner,
                         tenant_id=settings.synthetic_tenant_id, roles=("patient",), trace_id=uuid4())
    own = PolicyResource("execution", "e1", settings.synthetic_tenant_id, owner_session_id=owner)
    foreign = PolicyResource("execution", "e2", settings.synthetic_tenant_id, owner_session_id=uuid4())
    assert decide(actor, "execution:read", own)
    assert not decide(actor, "execution:read", foreign)
    assert not decide(actor, "unknown:action", own)
    assert not decide(actor, "agents:list", PolicyResource("agent", None, uuid4()))
