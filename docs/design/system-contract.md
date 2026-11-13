# System contract

- **Status:** detailed design baseline
- **Scope:** cross-module contracts, MVP v1.0; tenant expansion in v1.1
- **ADRs:** [001](../adr/001-runtime-state-machine.md), [002](../adr/002-postgresql-work-delivery.md), [003](../adr/003-idempotent-side-effects.md), [004](../adr/004-identity-authorization-tenancy.md)

## Boundary

This module defines externally visible HTTP contracts, identity/tenant context, common identifiers, errors, and idempotency. It does not implement workflow steps, run an LLM, or perform a hospital effect. API handlers call the runtime admission/resume ports and read redacted projections.

## Shared types and invariants

| Type | Contract |
|---|---|
| `ActorContext` | Server-resolved `actor_id`, `actor_type`, `session_id`, `tenant_id`, roles, and request `trace_id`; never populated from model output or request body ownership fields |
| `ExecutionRef` | UUID `execution_id`, tenant ID, `version`, pinned agent/config references |
| `StepRef` | Stable workflow `step_id`, UUID `attempt_id`; attempt ID changes on retry |
| `OperationRef` | UUID `operation_id` assigned once per logical side effect and reused across retries/restarts |
| `JobRef` | UUID `job_id`, `expected_execution_version`, step ID, attempt number, due time |

All times are UTC `timestamptz`, compared with database time. JSON contracts are schema-versioned and validated on entry and exit. Every tenant-owned row and lookup carries `tenant_id`, including MVP's one fixed synthetic tenant. Published config snapshots are immutable. A running execution never switches pinned versions. Domain data stays outside platform core.

## HTTP contract

| Endpoint | Request | Successful result and guard |
|---|---|---|
| `POST /agents/{agent_id}/executions` | Required `Idempotency-Key`; optional published version; validated initial input | `202` only after execution, checkpoint, initial event, and job commit; returns execution ID/status/trace ID |
| `GET /executions/{id}` | Authenticated session | Redacted status, current step, version, timestamps; owner or scoped staff |
| `GET /executions/{id}/events` | Cursor and limit | Redacted, ascending sequence; same visibility as execution |
| `POST /executions/{id}/input` | Input event ID, expected version, one-time input token, schema-valid answer | Consumes one waiting request and enqueues resume atomically |
| `POST /executions/{id}/approval` | Decision ID, expected version, approval ID, decision | Authorized staff only; decision and audit commit atomically |
| `GET /hospital/handoffs[/{id}]` | Staff session | Only handoffs within staff scope |

Error body is `{error_code, message, trace_id, retry_after?, details?}`. Use `400` for malformed syntax/header, `401` for missing/invalid authentication, `403` for denied same-tenant access, `404` for absent or foreign-tenant resource, `409` for state/version or idempotency conflicts, `422` for schema-invalid content, `429` for quota pressure (v1.1), `503` for unavailable/saturated service, and `500` for unexpected errors. Error details are redacted and do not reveal other tenants.

## Request idempotency

`idempotency_records` has PK `(tenant_id, operation_type, key)` and columns `request_hash`, `status`, `result_ref`, `created_at`, `expires_at`. The key is an opaque non-empty string of at most 128 bytes. Hash the canonical UTF-8 JSON of method, route resource ID, validated body, and requested agent version with SHA-256. Canonicalization sorts keys, uses compact separators and normalized schema values, and rejects non-finite numbers. Exclude timestamps, trace ID, and volatile headers.

The create transaction inserts or row-locks the record. Same key/hash returns the prior logical result or `IN_PROGRESS`; same key with changed hash returns `409`. The record lasts at least seven days in the demo and longer while a linked run is active or uncertain. A new action uses a new key. External `operation_id` idempotency is a separate [Tool/MCP contract](tool-mcp.md).

## Identity and authorization

MVP issues opaque random sessions. `sessions` stores tenant, actor type, optional staff user, keyed token hash, expiry and revocation; it never stores the raw token. Browser sessions use `HttpOnly`, `Secure`, `SameSite=Lax` cookies plus a session-bound CSRF token on mutations; CLI uses bearer credentials. Synthetic patient sessions are bound to one tenant and own only their executions. Staff/operator sessions require provisioned demo-account authentication with secrets outside the repository. Resolve actor and tenant from a live session on every request.

The centralized policy port accepts `(actor, tenant, action, resource, current_state, pinned_policy_version, tool_contract_version)` and defaults to deny. RBAC determines candidate actions; ABAC checks ownership, tenant, assignment, action scope, state, and approval. API, worker, and Tool Manager each enforce their boundary. Audit allow/deny with redacted context. Client-supplied tenant or owner and LLM text are never authority. In v1.1, recheck current tenant membership on every request; foreign resource IDs return `404`, known same-tenant denied resources return `403`.

## Verification

Test duplicate create requests with same/different payload, response loss after commit, foreign-ID concealment, patient session isolation, staff-only approval, CSRF denial, and v1.1 membership revocation on the next request. No API handler may acknowledge work before the [runtime](agent-runtime.md) admission transaction commits.
