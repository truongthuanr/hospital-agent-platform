# Reliability v1.1 Implementation Checklist — Hospital Agent Platform

Start after the [MVP v1.0 completion gate](implementation-checklist-v1.0.md) passes. This release extends the existing runtime and hospital application; the v1.0 durability, authorization, and safety guarantees remain release gates. Check an item only when its implementation and verification evidence are available.

Sources: [requirements](../requirement.md), [LLD](../low-level-design.md), [Runtime](../design/agent-runtime.md), [Orchestration](../design/workflow-orchestration.md), [System Contract](../design/system-contract.md), [Platform Operations](../design/platform-operations.md), [Hospital Domain](../design/hospital-domain.md), [Tool/MCP](../design/tool-mcp.md), [RAG](../design/rag.md), [Memory](../design/memory.md), [LLM Gateway](../design/llm-gateway.md). Next release: [Platform v2.0](implementation-checklist-v2.0.md).

## 1. Multi-replica execution and cancellation

- [ ] **[Orchestration]** Add worker lease ownership, heartbeat, expiry, and monotonically increasing fencing tokens; claim and reclaim jobs transactionally across replicas.
- [ ] **[Runtime]** Require both the current fencing token and execution-version CAS on worker commits; reject stale-worker transitions.
- [ ] **[Tool/MCP + Runtime]** Reconcile any prepared or uncertain external effect after lease loss before another worker retries it.
- [ ] **[Runtime + System Contract]** Add an idempotent cancellation request for queued, waiting, and running executions; resolve effect uncertainty before a terminal `CANCELLED` claim.
- [ ] **[Orchestration]** Add general scheduled start with a persisted due time; never run a scheduled execution early after restart.
- [ ] **Verification milestone:** Two worker replicas process jobs safely; an expired worker cannot commit; crash/reclaim and cancellation during an uncertain effect do not duplicate or misreport the effect.

## 2. Tenant identity, isolation, and admission

- [ ] **[System Contract + Platform Operations]** Add tenant and membership management, role-scoped administration, active-tenant selection, and revocation checks on the next request.
- [ ] **[Platform Operations]** Apply tenant-scoped keys, foreign keys, indexes, and queries to executions, jobs, audit, Memory, RAG, tools, and hospital records; reject wrong-tenant worker jobs before effects or commits.
- [ ] **[System Contract]** Keep foreign resource IDs concealed with `404`; enforce current membership, ownership, staff scope, and audit on every relevant boundary.
- [ ] **[Platform Operations]** Add database-backed per-user, tenant, and global admission limits; bound pending jobs and active executions across replicas, with reserved tenant capacity.
- [ ] **[LLM Gateway + Platform Operations]** Enforce provider concurrency, RPM, and TPM budgets separately from worker slots; return controlled `429` or `503` responses with `Retry-After` when known.
- [ ] **Verification milestone:** Two synthetic hospitals can use the same agent ID and idempotency key independently; cross-tenant API, config, Memory, RAG, tool, worker, and audit access is denied; one tenant's saturation does not consume another's reserve.

## 3. Hospital operations

- [ ] **[Hospital Domain + Tool/MCP]** Add mock service-queue configuration, scoped counters, registrations, status events, and stable operation-ID lookup; issue a unique number only after required fields and confirmation.
- [ ] **[Hospital Domain]** Read queue status from backend state with patient ownership or scoped staff access; closed or failing services issue no number or false success.
- [ ] **[Hospital Domain + Tool/MCP]** Add appointment reschedule/cancel with ownership, configured rules, separate confirmation, new operation IDs, atomic slot-count changes, and reconciliation.
- [ ] **[Hospital Domain]** Add advanced and accessible navigation only for configured, current routes; add staff case assignment, resolution, reopening, and audit history.
- [ ] **[System Contract]** Add SSE streaming and reconnect behavior without replaying a business action.
- [ ] **Verification milestone:** Concurrent queue registrations receive unique scoped numbers; duplicate retries create one registration; uncertain results reconcile; foreign patients cannot read queue status; appointment changes preserve slot capacity.

## 4. Operations, measurement, and release gate

- [ ] **[Platform Operations]** Add graceful shutdown, inspectable poison-job/dead-letter or reconciliation records, and circuit breakers without bypassing bounded retry policy.
- [ ] **[Platform Operations]** Add OpenTelemetry spans, protected metrics, queue depth/age, worker utilization, retries/errors, and provider usage/cost measurements.
- [ ] **[RAG + Memory]** Add explicit context-budget handling and two-tenant negative tests; report retrieval recall, citation validity, and abstention with dataset versions and limitations.
- [ ] **[Evaluation]** Re-run all v1.0 failure and safety tests; run v1.1 fault tests FT-009, FT-012–FT-019, FT-023–FT-028, and FT-033–FT-034 from the requirements.
- [ ] **[Evaluation]** Benchmark the documented demo profile with a fixed LLM stub: 50 concurrent users, configurable 20 active executions, 100 pending jobs, and 30 create requests/minute/user. Record hardware, duration, data size, throughput, latency percentiles, errors, queue age, and limitations.
- [ ] **[Release]** Demonstrate worker reclaim/fencing, cancellation, tenant isolation and quotas, service-queue registration/tracking, appointment changes, staff resolution, and operational visibility. Keep the platform work queue separate from the patient service queue.
