# MVP v1.0 Implementation Checklist — Hospital Agent Platform

This checklist follows **runnable vertical slices** and identifies the responsible modules. Work from top to bottom. Check an item only when its code, required migrations, and verification evidence are in place. The scope is **MVP v1.0**, using synthetic hospital data and patient identities.

Next release: [Reliability v1.1](implementation-checklist-v1.1.md).

Design sources: [LLD](../low-level-design.md), [requirements](../requirement.md), [System Contract](../design/system-contract.md), [Agent Runtime](../design/agent-runtime.md), [Workflow Orchestration](../design/workflow-orchestration.md), [Tool/MCP](../design/tool-mcp.md), [Hospital Domain](../design/hospital-domain.md), [LLM Gateway](../design/llm-gateway.md), [Memory](../design/memory.md), [RAG](../design/rag.md), [Platform Operations](../design/platform-operations.md).

## 0. Foundation — shared infrastructure and the first execution path

Build only what is needed to implement and verify the first execution. Add schemas, services, and data specific to Tool/MCP, Memory, RAG, and Hospital Domain in their respective stages.

- [ ] **[Platform Operations]** Set up the project structure, environment configuration, dependency management, and Docker Compose for the API, singleton worker, and PostgreSQL; add a migration framework and migration command.
- [ ] **[Platform Operations]** Add basic health and readiness checks, logging with `trace_id`, secrets configured outside the repository, and minimal synthetic seed data.
- [ ] **[System Contract]** Define shared types `ActorContext`, `ExecutionRef`, `StepRef`, `JobRef`, and `OperationRef`; use UUIDs, UTC `timestamptz`, schema versions, and `tenant_id` on owned data, including in the single-tenant MVP.
- [ ] **[System Contract]** Add minimal authenticated sessions for synthetic patients and demo staff; store only token hashes, resolve actor and tenant from the session, provide a default-deny policy port, and audit allow/deny decisions with redacted context.
- [ ] **[System Contract]** Standardize HTTP errors, input/output validation, and `Idempotency-Key`; define the canonical request hash and `idempotency_records` table.
- [ ] **[Workflow Orchestration]** Add the `agent_versions` registry and one immutable workflow version containing only `RULE` and `FINAL` steps initially; reject missing successors, unbounded loops, and invalid contracts.
- [ ] **Verification milestone:** Compose starts, migrations can be rerun safely, sessions and policy work, and a published workflow version can be loaded. LLM, MCP, and pgvector are not required at this stage.

## 1. Durable execution — System Contract + Runtime + Orchestration

- [ ] **[Agent Runtime]** Create `executions`, `checkpoints`, `execution_events`, `step_attempts`, `input_requests`, and `approvals` with the specified keys, unique constraints, and tenant relationships.
- [ ] **[Orchestration]** Create `durable_jobs` with unique `(execution_id, expected_version, step_id, attempt_no)` and an index for `READY` jobs by `due_at`.
- [ ] **[Runtime + System Contract]** Implement `POST /agents/{agent_id}/executions`: in **one transaction**, write the idempotency record, version-0 execution, checkpoint, event, and initial job; return `202` only after commit. The same key and payload return the same execution; the same key with a different payload returns `409`.
- [ ] **[Runtime]** Implement the state machine and `commit_decision` with CAS on `expected_version`; in the same transaction, write the attempt, checkpoint/event, complete the current job, and create the successor job or waiting request.
- [ ] **[Orchestration]** Implement the singleton worker with a PostgreSQL advisory lock; claim due jobs with `SKIP LOCKED`, reload the execution and pinned configuration, and discard jobs with stale versions.
- [ ] **[Runtime + Orchestration]** Implement `WAITING_INPUT`, `WAITING_APPROVAL`, and resume with actor/token/version checks and duplicate handling; release the worker while waiting.
- [ ] **[Orchestration]** Classify transient and permanent errors, persist `due_at` for bounded retries, and recover `RUNNING` jobs after restart only after acquiring the leadership lock; never run a retry before its due time.
- [ ] **[System Contract]** Implement APIs to read executions/events and submit input/approval; enforce ownership, staff scope, redaction, and the specified `403`/`404`/`409` responses.
- [ ] **Verification milestone:** A `RULE → WAITING_INPUT/APPROVAL → FINAL` workflow completes through the API; a kill after commit but before response, or after claim, does not lose the execution after restart; only one of two competing CAS transitions succeeds; updating an agent version does not change the configuration pinned by an existing execution.

## 2. Safe hospital workflow without booking effects

- [ ] **[Hospital Domain]** Add schemas and synthetic fixtures with version, approval, and effective-date metadata for hospital information, procedures, locations, and handoff cases; keep hospital business models out of platform core.
- [ ] **[Hospital Domain + Orchestration]** Run the versioned, **deterministic** warning-indicator screen as the first workflow step; a positive or unresolved warning creates a handoff and returns approved fallback wording without proceeding to booking.
- [ ] **[Hospital Domain]** Implement stepwise procedure guidance that resumes on the pinned procedure version; build navigation from configured locations and links, ask for a missing start point, and never invent a route when data is missing or expired.
- [ ] **[System Contract]** Implement the handoff API for scoped staff; patients cannot view another patient's case.
- [ ] **Verification milestone:** Information, procedure, navigation, and handoff flows run through the durable worker; a waiting execution resumes on its original version after a new version is published; a case remains pending when staff are offline.

## 3. Tool/MCP and reconcilable mock booking

- [ ] **[Tool/MCP]** Add a contract registry, allowlist, schema validation, server-side policy checks, timeout/error normalization, and audit; a denied invocation sends no request to MCP.
- [ ] **[Hospital Domain]** Build the mock hospital MCP service and slot, appointment, and effect-record schemas; keep `list_slots` read-only, and make `create_appointment` lock the slot and atomically store the booking and operation result, with strongly consistent lookup by `(tenant_id, operation_id)`.
- [ ] **[Runtime + Tool/MCP]** Assign one stable `operation_id` per logical action; durably record `tool_invocations.PREPARED` and the payload hash before calling the effecting tool.
- [ ] **[Hospital Domain + System Contract]** Require one-time confirmation, ownership checks, and policy checks before `create_appointment`; present displayed slots as availability, not reservations.
- [ ] **[Tool/MCP + Runtime]** After a timeout, crash, or lost local commit result, look up the operation ID before retrying. Record a proven effect, retry with the same ID only when absence is reliably proven, or enter `RECONCILIATION_REQUIRED` when the outcome is inconclusive.
- [ ] **Verification milestone:** One operation ID cannot create two appointments; the same ID with a different payload is rejected; competing bookings do not exceed slot capacity; a kill after remote success but before the local checkpoint is reconciled; an unavailable lookup does not trigger a second effect.

## 4. LLM Gateway + Memory + RAG

- [ ] **[LLM Gateway]** Implement the provider port, immutable prompt/model versions, timeout, structured-output validation, and at most one repair attempt; add a deterministic test stub.
- [ ] **[Memory]** Add tenant- and owner-scoped `conversation_messages`; persist a patient message before enqueuing a dependent step, append an assistant message after validated output is committed, and prevent duplicate visible replies.
- [ ] **[RAG]** Add pgvector, `knowledge_documents`, and `knowledge_chunks`; ingest only approved synthetic documents and retain version, effective dates, source, and chunk offsets.
- [ ] **[RAG]** Filter retrieval by tenant, corpus version, approval, and effective dates; choose `min_similarity` and `top_k` from a labeled evaluation set. Abstain if no validated threshold exists.
- [ ] **[LLM Gateway + RAG]** Pass evidence as untrusted data; have the renderer verify that citations refer to retrieved chunks from current approved sources and that the answer is supported. Otherwise, use the fallback or handoff path.
- [ ] **[Hospital Domain]** Continue using approved structured data for procedure steps and routes; do not infer step order or routes from vector similarity.
- [ ] **Verification milestone:** The stub is reproducible; invalid structured output and fabricated citations are rejected; an FAQ without sufficient evidence triggers abstention; clearing or summarizing chat does not change the execution checkpoint; patient A cannot read patient B's conversation.

## 5. MVP v1.0 completion gate — integration and operations

- [ ] **[Platform Operations]** Complete migration, seed, and restart procedures; worker readiness based on leadership; trace IDs across API → job → tool; and audit/redaction. Do not log raw patient text, secrets, or unredacted MCP payloads.
- [ ] **[Evaluation]** Prepare approved synthetic fixtures, staff-routing/fallback wording, qualified review of the versioned warning-indicator suite, and a retrieval evaluation set with a validated similarity threshold.
- [ ] **[Evaluation]** Run the fault matrix: lost HTTP response after commit, crash after claim, restart before retry due time, CAS race, duplicate input/approval, remote success before checkpoint, inconclusive lookup, denied access, and stale/missing RAG sources.
- [ ] **[Evaluation]** Demonstrate **zero missed handoffs within the fixed warning-indicator suite** and **zero unauthorized effects** in the test set; record fixture and agent versions, environment, sample size, and limitations.
- [ ] **[Release]** Demonstrate four MVP flows: information with citations, procedure/navigation guidance, safe handoff, and confirmed mock booking with reconciliation. Mark MVP complete only when the milestones above have evidence.

