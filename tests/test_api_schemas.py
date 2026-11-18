from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agent.api.main import app
from agent.api.schemas import (
    CreateExecutionRequest, CreateExecutionResponse, DecideApprovalRequest,
    EventPageQuery, ExecutionEventsResponse, ExecutionResponse, SubmitInputRequest,
)


@pytest.mark.parametrize("model,payload", [
    (CreateExecutionRequest, {"initial_input": {"reason": "synthetic"}}),
    (SubmitInputRequest, {"input_event_id": uuid4(), "input_request_id": uuid4(),
                          "expected_version": 1, "input_token": "opaque", "answer": {"choice": "yes"}}),
    (DecideApprovalRequest, {"decision_id": uuid4(), "approval_id": uuid4(),
                             "expected_version": 1, "decision": "APPROVE"}),
])
def test_execution_mutations_require_supported_version_and_forbid_unknown_fields(model, payload):
    assert model.model_validate({"schema_version": "1", **payload}).schema_version == "1"
    for changes in ({}, {"schema_version": "2"}, {"schema_version": "1", "tenant_id": str(uuid4())}):
        with pytest.raises(ValidationError):
            model.model_validate({**payload, **changes})


def test_execution_contracts_validate_versions_status_and_pagination():
    now = datetime.now(timezone.utc)
    execution_id = uuid4()
    response = CreateExecutionResponse(execution_id=execution_id, status="PENDING", version=0, trace_id=uuid4())
    assert response.model_dump(mode="json")["schema_version"] == "1"
    assert ExecutionResponse.model_validate({**response.model_dump(), "agent_id": "frontdesk",
        "agent_version": "1", "current_step": "start", "created_at": now, "updated_at": now}).version == 0
    assert ExecutionEventsResponse(execution_id=execution_id, events=[], next_cursor=None).schema_version == "1"
    assert EventPageQuery(cursor=0, limit=100).limit == 100
    for payload in ({"cursor": -1}, {"limit": 101}, {"limit": 1, "other": "x"}):
        with pytest.raises(ValidationError):
            EventPageQuery.model_validate(payload)
    for payload in ({**response.model_dump(), "status": "CANCELLED"},
                    {**response.model_dump(), "version": -1},
                    {**response.model_dump(), "schema_version": "2"},
                    {**response.model_dump(), "secret": "x"}):
        with pytest.raises(ValidationError):
            CreateExecutionResponse.model_validate(payload)
    with pytest.raises(ValidationError):
        ExecutionResponse.model_validate({**response.model_dump(), "agent_id": "frontdesk",
            "agent_version": "1", "current_step": "start", "created_at": now.replace(tzinfo=None), "updated_at": now})
    with pytest.raises(ValidationError):
        CreateExecutionRequest.model_validate({"schema_version": "1", "initial_input": {"nested": [float("nan")]}})
    with pytest.raises(ValidationError):
        SubmitInputRequest.model_validate({"schema_version": "1", "input_event_id": uuid4(),
            "input_request_id": uuid4(), "expected_version": 1, "input_token": "opaque",
            "answer": {"value": float("inf")}})


def test_foundation_routes_expose_versioned_request_and_response_schemas():
    openapi = app.openapi()
    schemas = openapi["components"]["schemas"]
    for name in ("StaffLoginRequest", "PublishedAgent"):
        assert "schema_version" in schemas[name]["required"]
        assert schemas[name]["additionalProperties"] is False
    for path, method in (("/health/live", "get"), ("/health/ready", "get"),
                         ("/session/patient", "post"), ("/session/staff", "post"),
                         ("/agents", "get"), ("/agents/versions", "post"),
                         ("/agents/{agent_id}/versions/{version}", "get")):
        response = openapi["paths"][path][method]["responses"]
        success = next(value for code, value in response.items() if code.startswith("2"))
        response_schema = success["content"]["application/json"]["schema"]
        assert "schema_version" in schemas[response_schema["$ref"].split("/")[-1]]["properties"]
