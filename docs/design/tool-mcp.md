# Tool manager and MCP integration

- **Status:** detailed design baseline
- **Scope:** tool contracts, policy gate, side effects, reconciliation
- **ADRs:** [003](../adr/003-idempotent-side-effects.md), [004](../adr/004-identity-authorization-tenancy.md), [007](../adr/007-appointment-tool.md), [008](../adr/008-hospital-service-queue.md)

## Boundary and port

The Tool Manager is the only platform path to MCP tools. It owns declared tool contracts, argument/result validation, server-side allowlist and policy checks, normalized errors, durable invocation records, and operation-ID reconciliation. The hospital MCP service owns appointment and service-queue transactions. The Tool Manager does not infer authorization from prompts, LLM output, or client-supplied tenant IDs.

`invoke(actor, execution_ref, step_ref, tool_contract_version, tool_name, args, operation_id?) -> ToolResult`. A contract declares read-only or side-effecting class, JSON input/output schemas, tenant scope, timeout, transient/permanent error mapping, idempotency scope, and lookup operation for effects. A side-effecting contract without stable operation ID and reliable lookup is not eligible for automatic uncertain-outcome retry.

## Owned persistence

`tool_invocations` has UUID PK, tenant, execution, step, operation ID, tool name, payload hash, status, result reference, and timestamps. A partial unique `(tenant_id, operation_id)` constraint applies to side-effecting invocations. Statuses are `PREPARED`, `SUCCEEDED`, `FAILED_KNOWN`, and `UNCERTAIN`; transition history is appended to redacted audit. The MCP service has its own unique `(tenant_id, operation_id)` effect record and strongly consistent lookup in the same database transaction as the effect.

## Side-effect protocol

1. Load the execution and pinned tool/policy versions. Validate actor, server-derived tenant, current step, allowlist, action/resource policy, required confirmation or approval, and input schema. Denial is audited and stops before network I/O.
2. Use a checkpointed UUID `operation_id` for one logical action. Commit `PREPARED` with payload hash before sending. Reuse with a different payload is a conflict.
3. Invoke MCP with the tenant and operation ID. The service atomically stores its effect and operation result. A repeated same operation/payload returns that result.
4. On known success/failure, commit invocation result with runtime checkpoint, event, and job completion. A timeout, transport loss, crash, or CAS loss after call requires lookup by operation ID before retry.
5. If lookup proves effect exists, record it. If lookup reliably proves absence, retry with the same ID if budget permits. If lookup is unavailable/inconclusive, enter `RECONCILIATION_REQUIRED`; never report success or blindly replay.

A lookup must be strongly consistent with the effect write; an eventually consistent empty response is not proof of absence. Exactly-once execution is not claimed. A real connector without idempotency or reliable lookup requires human resolution of uncertainty.

## Read-only calls and errors

Read-only calls have per-attempt IDs and may retry transient failures within the workflow budget. Normalize transport timeout, rate limit, selected 5xx, validation error, policy denial, and known domain rejection separately. Do not retry malformed arguments or denied permissions. MVP demo timeouts are 5 s read-only and 10 s effecting; they are configuration, not production targets.

## Hospital MCP operations

| Operation | Class | Contract |
|---|---|---|
| `list_slots` | Read-only | Tenant-scoped availability; a displayed slot is not reserved |
| `create_appointment` | Effect | Owner/confirmation/policy checked; atomic capacity; operation-ID lookup |
| `lookup_appointment_operation` | Read-only reconciliation | Returns committed result or reliable absence by tenant and operation ID |
| `register_service_queue` (v1.1) | Effect | Open service, required fields, confirmation, atomic number, operation-ID lookup |
| `get_queue_status` (v1.1) | Read-only | Patient ownership or scoped staff; backend values only |

Exact hospital schemas and transactions live in [Hospital Domain](hospital-domain.md). Test denied calls causing zero MCP requests, duplicate operation IDs, changed payload conflicts, remote success before local checkpoint, lookup unavailable, slot contention, and queue contention.
