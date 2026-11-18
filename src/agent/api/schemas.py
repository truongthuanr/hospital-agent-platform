"""Version 1 HTTP payloads. Keep these separate from persistence and workflow models."""

import math
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, field_validator


def finite_json(value: JsonValue) -> JsonValue:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite numbers are not supported")
    if isinstance(value, dict):
        for nested in value.values():
            finite_json(nested)
    elif isinstance(value, list):
        for nested in value:
            finite_json(nested)
    return value


class VersionedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]


class VersionedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"


class HealthResponse(VersionedResponse):
    status: Literal["live", "ready"]
    trace_id: UUID | None = None


class StaffLoginRequest(VersionedRequest):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1)


class SessionResponse(VersionedResponse):
    token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: AwareDatetime


class AgentListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    version: str
    published_at: AwareDatetime


class AgentListResponse(VersionedResponse):
    agents: list[AgentListItem]


class PublishedVersionResponse(VersionedResponse):
    agent_id: str
    version: str
    snapshot_hash: str


class ExecutionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_INPUT = "WAITING_INPUT"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CreateExecutionRequest(VersionedRequest):
    agent_version: str | None = Field(default=None, min_length=1, max_length=64)
    initial_input: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("initial_input")
    @classmethod
    def check_initial_input(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        finite_json(value)
        return value


class ExecutionActionResponse(VersionedResponse):
    execution_id: UUID
    status: ExecutionStatus
    version: int = Field(ge=0)
    trace_id: UUID


class CreateExecutionResponse(ExecutionActionResponse):
    pass


class ExecutionResponse(ExecutionActionResponse):
    agent_id: str
    agent_version: str
    current_step: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class EventPageQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cursor: int | None = Field(default=None, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


class ExecutionEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    sequence: int = Field(ge=0)
    type: str = Field(min_length=1)
    payload_redacted: dict[str, JsonValue]
    timestamp: AwareDatetime


class ExecutionEventsResponse(VersionedResponse):
    execution_id: UUID
    events: list[ExecutionEventResponse]
    next_cursor: int | None = Field(default=None, ge=0)


class SubmitInputRequest(VersionedRequest):
    input_event_id: UUID
    input_request_id: UUID
    expected_version: int = Field(ge=0)
    input_token: str = Field(min_length=1)
    answer: JsonValue

    @field_validator("answer")
    @classmethod
    def check_answer(cls, value: JsonValue) -> JsonValue:
        return finite_json(value)


class ApprovalDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class DecideApprovalRequest(VersionedRequest):
    decision_id: UUID
    approval_id: UUID
    expected_version: int = Field(ge=0)
    decision: ApprovalDecision


class SubmitInputResponse(ExecutionActionResponse):
    pass


class DecideApprovalResponse(ExecutionActionResponse):
    pass
