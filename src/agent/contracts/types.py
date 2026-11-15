from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ActorType(StrEnum):
    PATIENT = "patient"
    STAFF = "staff"


class FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ActorContext(FrozenContract):
    actor_id: UUID
    actor_type: ActorType
    session_id: UUID
    tenant_id: UUID
    roles: tuple[str, ...]
    trace_id: UUID


class ExecutionRef(FrozenContract):
    execution_id: UUID
    tenant_id: UUID
    version: int
    agent_id: str
    agent_version: str


class StepRef(FrozenContract):
    step_id: str
    attempt_id: UUID


class OperationRef(FrozenContract):
    operation_id: UUID


class JobRef(FrozenContract):
    job_id: UUID
    expected_execution_version: int
    step_id: str
    attempt_no: int
    due_at: datetime

