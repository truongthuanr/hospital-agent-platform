# Workflow orchestration and durable scheduling

- **Status:** detailed design baseline
- **Scope:** workflow definition, step dispatch, jobs, retries; MVP v1.0 and multi-replica v1.1
- **ADRs:** [001](../adr/001-runtime-state-machine.md), [002](../adr/002-postgresql-work-delivery.md)

## Boundary and ports

Orchestration owns the published workflow graph, step handlers, scheduler, job claims, and retry classification. It asks [Agent Runtime](agent-runtime.md) to commit transitions. It does not mutate execution tables outside runtime ports and does not perform a side effect outside [Tool/MCP](tool-mcp.md).

The registry submodule owns `agent_versions` with `(tenant_id, agent_id, version)` primary key, immutable published snapshot JSON/hash, and publication time. Publication resolves and validates workflow, prompt, model, policy, tool-contract, and hospital configuration references as one versioned snapshot. Runtime reads the pinned snapshot but does not edit registry records.

Each published step declares `step_id`, step type (`RULE`, `LLM`, `RAG`, `TOOL`, `WAIT_INPUT`, `WAIT_APPROVAL`, or `FINAL`), input/output schema versions, allowed successors, timeout, retry policy, required tool and policy action. Publication rejects missing successors, unbounded loops, incompatible contracts, or a tool step without an allowlist entry. A handler returns a typed `StepDecision(next_state, next_step?, checkpoint_delta, output_ref?, retry_due_at?, operation_id?)`; runtime validates it against the pinned graph.

## Durable job contract

`durable_jobs` has UUID PK, tenant, execution ID, expected version, step ID, attempt number, `due_at`, `status`, `claimed_at`, and `completed_at`; unique `(execution_id, expected_version, step_id, attempt_no)`. A partial `(due_at, id)` index on `READY` jobs supports due claims. It is the MVP transactional outbox work intent. A separate publication outbox appears only if a later ADR selects a transport.

One singleton worker deployment holds a PostgreSQL advisory leadership lock in MVP. The scheduler row-locks the oldest `READY` job with `due_at <= database_now` using `SKIP LOCKED`, marks it `RUNNING`, and dispatches it locally. The worker reloads execution, tenant, expected version, step, pinned config, and any prepared invocation before executing. A stale job is marked completed without a new transition. Job completion and the successor job are committed with the runtime transition. A claimed job is never considered proof of a completed step.

The in-process supervisor catches task errors and persists a classified retry/failure or returns the job to `READY`. On restart, after acquiring singleton leadership, it returns old `RUNNING` jobs to `READY`; an invocation in `PREPARED` or uncertain state goes to reconciliation before any effect retry. This startup recovery is allowed only for the v1.0 one-deployment profile. A shutdown stops new claims and leaves unfinished work recoverable.

## Retry policy

| Setting | MVP demo default | Rule |
|---|---:|---|
| Step attempts | 3 total | Includes first attempt |
| Backoff | 1 s base, 30 s cap, ±20% jitter | Exponential; persist chosen `due_at`; honor larger valid `Retry-After` |
| LLM timeout | 20 s | Schema repair at most once; invalid output after repair fails |
| Read-only MCP timeout | 5 s | Retry transient failures within budget |
| Effecting MCP timeout | 10 s | Treat as unknown outcome; reconcile before retry |

Retry only classified timeouts, transport failures, rate limits, and selected 5xx. Validation errors, policy denial, bad permissions, and unsafe decisions are permanent. The scheduler never runs a retry before persisted `due_at`, including after restart. Exhausted known non-effect goes to `FAILED`; uncertain effect goes to `RECONCILIATION_REQUIRED`. The demo values must be measured and are not production SLOs.

## v1.1 worker leases

`worker_leases` uses `(tenant_id, job_id)` as key with owner, monotonic fencing token, expiry, and heartbeat. Claim/reclaim increments the token after expiry in one transaction. A worker heartbeats only its token; runtime commit requires both current token and execution-version CAS. A stale worker can still have called a remote tool, so lease loss triggers operation-ID reconciliation rather than a blind retry. Multiple API/worker replicas use the same database source of truth.

## Verification

Kill after execution commit but before claim; kill after claim; restart before retry due time; race duplicate claims; change agent config while waiting; kill after remote effect; and in v1.1 expire a lease while an old worker is alive. Verify one committed transition per version, no lost acknowledged work, and no duplicate supported remote effect.
