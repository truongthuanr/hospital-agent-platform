# Agent runtime

- **Status:** detailed design baseline
- **Scope:** execution persistence and state transitions, MVP v1.0; cancellation/fencing extension in v1.1
- **ADRs:** [001](../adr/001-runtime-state-machine.md), [003](../adr/003-idempotent-side-effects.md)

## Boundary and ports

Runtime owns execution state, checkpoints, events, attempts, input/approval requests, and transition CAS. It does not select a model, own hospital tables, or call MCP. Workflow orchestration supplies a validated `StepDecision`; runtime validates it against the pinned transition graph and commits it.

| Port | Input | Output |
|---|---|---|
| `create_execution` | `ActorContext`, agent snapshot, canonical request hash | Committed `ExecutionRef` and initial job |
| `load_execution` | Tenant and execution ID | Current state, latest checkpoint, pinned refs |
| `commit_decision` | Expected version, job ID, validated decision, optional current fencing token | New version/event and successor job or waiting/terminal state |
| `submit_input` / `decide_approval` | Actor, request/decision ID, expected version, payload | Consumed request and committed resume job |
| `record_reconciliation` | Operation ID, proven result or unresolved reason | Resumed or reviewable execution state |

## Owned schema

| Table | Key fields and constraints |
|---|---|
| `executions` | UUID PK, tenant, owner session, agent/version, pinned workflow/prompt/model/policy/tool/hospital refs, status, current step, `version bigint >= 0`, trace ID, timestamps |
| `checkpoints` | `(execution_id, version)` PK, tenant, `schema_version`, minimal `state_json`, timestamp |
| `execution_events` | UUID PK, tenant, execution, monotonic `sequence`; unique `(execution_id, sequence)`; redacted payload |
| `step_attempts` | UUID PK, tenant, execution, step, attempt number, status/error class, start/end; unique `(execution_id, step_id, attempt_no)` |
| `input_requests` | UUID PK, tenant, execution/version, keyed token hash, kind, expiry, consumed event ID and consumed payload hash; unique `(execution_id, execution_version)` |
| `approvals` | UUID PK, tenant, execution/version, action/scope, decision/decision ID, actor/time; unique `(tenant_id, decision_id)` |

Checkpoints contain `workflow_step`, input/output references, pending input/approval IDs, retry count/due time, and stable operation IDs. Hospital procedure version/current step may appear as opaque hospital-owned state. No full conversation history or raw patient text is stored in checkpoints. Future schema changes use explicit readers/upcasters for old checkpoints and never rewrite historical rows.

## State machine

| From | To | Condition |
|---|---|---|
| `PENDING` | `RUNNING` | Valid start job |
| `RUNNING` | `RUNNING` | Valid next step |
| `RUNNING` | `WAITING_INPUT` / `WAITING_APPROVAL` | Checkpoint and one-time request committed; worker slot released |
| `RUNNING` | `RETRY_SCHEDULED` | Classified transient error, budget remains, due job inserted |
| `RUNNING` | `RECONCILIATION_REQUIRED` | External outcome unknown; no effect retry |
| `RUNNING` | `COMPLETED` / `FAILED` | Valid final result or permanent/budget failure |
| `WAITING_INPUT` / `WAITING_APPROVAL` | `RUNNING` | Authorized, deduplicated input/decision; rejection follows pinned branch |
| `RETRY_SCHEDULED` | `RUNNING` | Due job claimed |
| `RECONCILIATION_REQUIRED` | `RUNNING` / `FAILED` | Proven outcome plus authorized resolution |

`COMPLETED` and `FAILED` are terminal in v1.0. `CANCELLED` is terminal in v1.1 after effect certainty is resolved. An operator rerun creates a linked new execution, never reopens a terminal row.

In v1.1, cancellation is first a durable request. Queued or waiting work may transition to `CANCELLED` after authorization and state checks. A running worker checks cancellation before its next step. If a side effect is prepared or uncertain, runtime waits for Tool/MCP reconciliation before the pinned workflow applies its cancellation branch. Cancellation never asserts that an in-flight external effect was rolled back.

## Transactions

Create: lock/insert the scoped API idempotency row, resolve immutable snapshots, insert `PENDING` execution at version 0, initial checkpoint/event, and one `READY` job in the same PostgreSQL transaction. Return `202` only after commit. No LLM or MCP call runs inside it.

Transition: execute `UPDATE executions SET ..., version=version+1 WHERE id=:id AND tenant_id=:tenant AND version=:expected`. In that same transaction update the attempt and current job, insert checkpoint/event and any next job or waiting request. Allocate event sequence under the execution row lock. On zero updated rows, roll back, reload and discard the stale decision; do not repeat an external effect because CAS failed. In v1.1 a worker transition also checks the current fencing token.

Waiting: generate a cryptographically random input token, store only its keyed hash, and commit the waiting state before returning a prompt. Input and approval handlers lock request and execution, verify actor, tenant, state/version, unconsumed ID and payload schema, then consume and enqueue resume in one transaction. Identical duplicate IDs return the original result; conflicting duplicates return `409`.

## Failure and verification

Missing pinned configuration fails the run; runtime never substitutes a newer version. Permanent validation/policy errors do not retry. An uncertain remote result enters `RECONCILIATION_REQUIRED` via the [Tool/MCP](tool-mcp.md) result contract. Test invalid transitions, concurrent CAS, restart while waiting, duplicate input/approval, configuration update during a run, and remote success before local checkpoint.
