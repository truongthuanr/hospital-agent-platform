# Platform operations

- **Status:** detailed design baseline
- **Scope:** deployment, tenancy, admission, observability, migrations, verification
- **ADRs:** [002](../adr/002-postgresql-work-delivery.md), [004](../adr/004-identity-authorization-tenancy.md)

## Boundary

Platform Operations owns deployment configuration, tenant membership/quotas in v1.1, admission counters, telemetry, migration and recovery procedures. It observes but does not decide workflow transitions or hospital facts. PostgreSQL remains authoritative for execution, checkpoint, job, retry due time and idempotency.

## Deployment and recovery

MVP Docker Compose runs FastAPI, a singleton worker/scheduler, PostgreSQL with pgvector, and the mock hospital MCP service. An LLM stub is used for infrastructure tests; a real model demo is separate. API and worker may share a container but not durable in-memory state. The worker holds a PostgreSQL advisory leadership lock; readiness fails for a duplicate leader. Restart reclaims `RUNNING` jobs only after acquiring the lock. A prepared effect first follows [Tool/MCP reconciliation](tool-mcp.md). Shutdown stops new claims and leaves unfinished jobs recoverable. Multiple live worker replicas require v1.1 leases/fencing in [Orchestration](workflow-orchestration.md).

Readiness checks database connectivity and, for worker processes, leadership and scheduler loop health; it does not create/claim a probe job. Liveness reports process health only. A dependency outage never turns an uncertain remote effect into a known failure.

## Tenant and membership (v1.1)

`tenants` has unique ID/name and active status. `tenant_memberships` has `(tenant_id, user_id)` key, role, status and version; tenant quotas have explicit config versions. The active tenant comes from authenticated session and currently valid membership on every scoped request. A patient session is bound to one tenant. Revocation blocks the next request. Workers reload tenant-owned execution and pinned config and audit wrong-tenant jobs. Tenant-owned child tables use composite `(tenant_id, parent_id)` foreign keys and tenant-leading indexes for RAG, memory, events, jobs, appointments, queue records and audit. Platform operators see tenant metadata by default; content access requires membership and is audited.

## Admission and capacity (v1.1)

Use PostgreSQL `admission_buckets` keyed by user/tenant/global scope and minute window, `capacity_counters`, and unique `capacity_reservations` by execution/job. Before `202`, lock relevant buckets/counters in stable order, check request budgets and pending-job capacity, and commit the reservation with execution and job. Rollback releases it. A worker separately reserves an active slot when claiming a job; completion/release decrements exactly once by reservation ID. API and worker replicas share these rows. Provider RPM/TPM and concurrency budgets are independent of worker slots.

The v1.1 demo profile uses 30 create requests/minute/user, 100 pending jobs globally, and 20 active executions globally, as specified in requirements. Tenant quotas and provider limits are configuration, with reserved tenant capacity so one tenant cannot consume another's share. Quota pressure returns `429`; service saturation returns `503`; include `Retry-After` when known. These values are demo targets and require measurement, not production SLOs.

## Telemetry, security and data lifecycle

Every API response/step carries `trace_id`; worker logs add execution, step, attempt, job and operation IDs when present. Audit records actor, action, resource, policy result, outcome and redacted context. No raw patient text, credentials or unredacted MCP payloads appear in logs/events/traces. Secrets come from environment or secret store. API, LLM and MCP input/output schemas are validated. v1.1 adds OpenTelemetry spans, queue depth/age, worker occupancy, retries/errors, provider usage/cost and a protected `/metrics` endpoint. Circuit breakers and graceful shutdown are v1.1.

Alembic migrations use expand-then-contract: add compatible columns/tables, backfill, enforce constraints, then remove old representation. Published config and historical events stay immutable. Demo API idempotency records last at least seven days and longer while an execution is active or uncertain. Per-data-type retention/deletion is required before production data use. The demo imports only synthetic patient data.

## Verification and release gates

| Area | Required evidence |
|---|---|
| Admission/restart | Kill after commit before HTTP response; replay key yields one execution; kill after claim and recover job |
| Concurrency | Two transitions compete; one CAS wins; duplicate job and remote effect do not duplicate state/effect |
| Tenant (v1.1) | Two synthetic hospitals; foreign API/RAG/memory/tool/worker/audit access denied; revocation next request |
| Capacity (v1.1) | Two replicas obey global/tenant/user limits; one tenant's saturation does not consume another's reserve |
| Safety | Fixed warning-indicator suite has zero missed handoffs and zero unauthorized effects; qualified reviewer signs off fallback |
| Operations | Queue depth/age, failures and trace IDs observable; redaction and secret scan pass |

Record fixture/agent versions, environment, hardware, sample size and limitations with evaluation results. Docker Compose benchmark uses a fixed LLM stub; real-model latency/cost is measured separately. Demo results do not establish a production SLO. A runbook must document failure recovery, operator reconciliation, per-data-type retention and tested operational values before production use.
