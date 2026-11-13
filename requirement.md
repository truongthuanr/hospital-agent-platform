# Hostpital Agent Platform — System Requirements Specification

**Document:** `requirement.md`  
**Specification version:** 1.0 (complete target-system overview)  
**Implementation releases:** MVP v1.0 → Reliability v1.1 → Platform v2.0  
**Status:** Proposed baseline; targets must be validated by tests  
**Reference application:** Hospital Front Desk Agent  
**Primary language:** Vietnamese; technical contracts in English

> This is a complete requirements inventory, **not** a claim that all features must be delivered in the first sprint. Each requirement is assigned a target release and priority. A feature is complete only when its acceptance criteria are demonstrated.

## 1. Vision and boundaries

Build a reusable, reliable, governed AI agent execution platform. Hospital Front Desk is the first reference application, not a dependency of platform core. The platform must support deterministic workflows, optional LLM-driven decisions, controlled tool invocation, durable execution, human interaction, evaluation, and operational visibility.

### 1.1 Goals

- Register and version agents with declared workflow, prompts, tools, model settings and policies.
- Execute workflows asynchronously with durable state, retries, scheduling, cancellation, pause/resume and crash recovery.
- Provide LLM gateway, MCP integration, RAG, memory and structured outputs.
- Prevent unauthorized or unsafe actions with policy checks and human approval.
- Demonstrate concurrency correctness, idempotent effects, overload protection, observability and reproducible evaluation.
- Make it possible to add a second domain agent without changing runtime core.

### 1.2 Non-goals for initial MVP

- Production hospital deployment or clinical decision support; diagnosis, prescriptions and autonomous emergency triage are excluded.
- Exactly-once execution across distributed services; guarantee at-least-once delivery plus bounded idempotent effects where supported.
- Visual no-code workflow builder, model training, full enterprise IAM, multi-region active-active, autonomous agent marketplace.
- Real patient records, real hospital integrations, or real-world appointment transactions.

### 1.3 Personas

| Role | Capabilities |
|---|---|
| Patient (simulated) | Ask questions, submit booking request, confirm/cancel |
| Hospital staff (simulated) | Handle escalation and approvals |
| Agent developer | Register/version agents, workflows, tools, policies |
| Platform operator | Inspect traces, queue, failures, replay/recover, audit |
| Evaluator | Run datasets and inspect quality/safety/reliability results |

## 2. Releases and priorities

- **MVP v1.0 / P0:** Minimal end-to-end platform, domain demo, persistent execution, idempotency, safe tool invocation, human pause/resume, basic observability and tests.
- **Reliability v1.1 / P1:** Durable queue/worker leases, concurrent processing, backpressure, rate limiting, advanced recovery, fault injection, circuit breakers and SLO measurement.
- **Platform v2.0 / P2:** Multi-agent handoffs, advanced scheduling/fairness, multi-tenancy, model routing/fallback, hybrid retrieval/reranking, governance/evaluation extensions and scale-out.
- **Priority convention:** P0 essential; P1 important production-hardening; P2 advanced. Release targets are planning goals, not promises of production readiness.

## 3. Logical architecture

```text
Patient Web/CLI, Staff Console, Operator CLI/Dashboard
                  |
       FastAPI Gateway (auth, quotas, API idempotency)
                  |
        Agent Registry + Execution API
                  |
        Durable Workflow Runtime / Scheduler
           |          |           |
    State/Events   Policy/HITL   Queue/Workers
           |          |           |
           +---- Tool Execution Manager ---- MCP Client -> MCP Servers
           |                 |
           +---- LLM Gateway  +---- Retrieval/RAG
           |                          |
     PostgreSQL (state, events, outbox)  pgvector/docs
           |
      Redis (optional queue, cache, rate limiter)
           |
    OpenTelemetry / logs / metrics / evaluation / audit

Hospital Front Desk Agent = workflow + prompts + domain policy + domain tools
```

**Boundary rule:** Platform core must not contain patient, symptom, doctor or appointment domain models. The hospital app owns these concepts. State store, conversation memory, knowledge store and immutable audit/event history are logically separate.

## 4. Functional requirements — Platform lifecycle

| ID | Requirement | Release | Acceptance criteria |
|---|---|---|---|
| PLT-001 | Register agents with stable IDs and versioned config | v1.0 P0 | Register and load one hospital agent; invalid config rejected |
| PLT-002 | Define workflow steps, transitions, input/output schema | v1.0 P0 | Deterministic path and invalid transition tests pass |
| PLT-003 | Start execution and return unique execution ID | v1.0 P0 | Duplicate client submission with same key does not create two executions |
| PLT-004 | Persist execution state, step results, version and timestamps | v1.0 P0 | Restart does not lose acknowledged transitions |
| PLT-005 | Pause for user input or human approval | v1.0 P0 | Execution enters waiting state without holding worker indefinitely |
| PLT-006 | Resume from persisted checkpoint | v1.0 P0 | Resume at correct step after process restart |
| PLT-007 | Timeout, retry and terminal failure states | v1.0 P0 | Configurable retry budget and no unbounded loop |
| PLT-008 | Cancel queued, waiting and running execution | v1.1 P1 | Cancellation is durable; running side effects treated explicitly |
| PLT-009 | Version pinning per execution | v1.1 P1 | In-flight run uses original workflow/prompt version |
| PLT-010 | Safe operator retry/reconciliation workflow | v1.1 P1 | Operator action logged; cannot blindly replay uncertain side effects |
| PLT-011 | Workflow scheduling and delayed retry | v1.1 P1 | Retry runs no earlier than due time; survives restart |
| PLT-012 | Multi-agent supervisor, handoff and shared context contracts | v2.0 P2 | Handoff preserves trace and scoped context |

### 4.1 Execution state model

- `PENDING` → `RUNNING` → `COMPLETED` / `FAILED` / `CANCELLED`.
- `RUNNING` may enter `WAITING_INPUT`, `WAITING_APPROVAL`, `RETRY_SCHEDULED`, `RECONCILIATION_REQUIRED`; valid events resume into `RUNNING`.
- `FAILED`, `COMPLETED`, `CANCELLED` are terminal for the execution; explicit operator re-run creates a new execution linked to original.
- State transitions require compare-and-swap/version checks. `execution_id`, `step_id`, `attempt_id`, `trace_id` and `operation_id` have distinct meanings.
- Persist checkpoint before acknowledging a pause; do not hold a worker slot while waiting for external input.

## 5. Agent reasoning, memory, LLM and RAG

| ID | Requirement | Release | Acceptance criteria |
|---|---|---|---|
| AI-001 | LLM gateway with provider adapter and timeouts | v1.0 P0 | Swap model config without changing workflow code |
| AI-002 | Validate structured LLM outputs against schema | v1.0 P0 | Malformed output rejected or safely repaired within budget |
| AI-003 | Explicit deterministic vs LLM-driven step types | v1.0 P0 | Trace identifies reasoning and deterministic steps |
| AI-004 | Separate short-term conversation memory from execution state | v1.0 P0 | Clearing chat context cannot corrupt execution progress |
| AI-005 | RAG with indexed hospital SOP/FAQ documents | v1.0 P0 | Responses reference source document IDs and excerpts |
| AI-006 | Grounded answers and abstention when retrieval is insufficient | v1.0 P0 | Unsupported FAQ test triggers abstain/handoff |
| AI-007 | Context window and token budget management | v1.1 P1 | Truncation/summarization strategy documented and tested |
| AI-008 | Record tokens, cost estimate, model version and latency | v1.1 P1 | Per-run usage report available |
| AI-009 | Hybrid retrieval, reranking, retrieval evaluation | v2.0 P2 | Compare baseline recall@k / MRR with hybrid approach |
| AI-010 | Provider routing, fallback and circuit breaker | v2.0 P2 | Fallback does not violate data/policy constraints |
| AI-011 | Long-term memory with provenance, TTL and deletion | v2.0 P2 | Memory access scoped; delete request verifiable |
| AI-012 | Optional ReAct/planning with bounded tool/step budget | v2.0 P2 | Agent cannot exceed step budget; all actions policy-checked |

**Hallucination safeguards:** grounded citations, source validation, structured output checks, abstention thresholds, curated evaluation datasets and human review. No claim of 100% hallucination detection.

## 6. MCP and external tool contracts

| ID | Requirement | Release | Acceptance criteria |
|---|---|---|---|
| TOOL-001 | MCP client discovery and invocation of allowlisted tools | v1.0 P0 | Mock appointment and FAQ tools callable via MCP |
| TOOL-002 | Tool input/output schema validation | v1.0 P0 | Invalid args rejected before external call |
| TOOL-003 | Per-agent tool allowlist and policy gate | v1.0 P0 | Unauthorized tool call never reaches MCP server |
| TOOL-004 | Distinguish read-only vs side-effecting tools | v1.0 P0 | Side-effecting calls require stable operation identity |
| TOOL-005 | Tool timeout, retry classification and error normalization | v1.0 P0 | Transient vs permanent error tests pass |
| TOOL-006 | Tool invocation audit with redaction | v1.0 P0 | Actor, policy result, tool, outcome and IDs recorded |
| TOOL-007 | Tool registry versioning and capability metadata | v1.1 P1 | Incompatible schema changes detected |
| TOOL-008 | Per-tool concurrency, quota and circuit breaker | v1.1 P1 | Dependency overload does not exhaust all workers |
| TOOL-009 | Sandboxed tool execution for untrusted operations | v2.0 P2 | Resource/time/network permissions enforced |

## 7. Distributed systems, reliability and concurrency contracts

| ID | Requirement | Release | Acceptance criteria |
|---|---|---|---|
| REL-001 | Durable execution creation and checkpoint commits | v1.0 P0 | No acknowledged execution disappears after restart |
| REL-002 | API and side-effect idempotency | v1.0 P0 | Same scoped key + same payload yields same logical result; changed payload conflicts |
| REL-003 | At-least-once safe step execution | v1.0 P0 | Duplicate deliveries do not duplicate committed state or supported external effects |
| REL-004 | Optimistic locking for execution state | v1.0 P0 | Two concurrent transitions: only one wins version CAS |
| REL-005 | Exponential backoff + jitter + retry budget | v1.0 P0 | Bounded retry; permanent validation errors not retried |
| REL-006 | Ambiguous external outcome reconciliation | v1.0 P0 | Crash after remote success resolves by operation key or enters RECONCILIATION_REQUIRED |
| REL-007 | Durable job queue and transactional outbox | v1.1 P1 | DB commit and enqueue crash window causes no lost accepted work |
| REL-008 | Worker lease, heartbeat, expiry and reclaim | v1.1 P1 | Killed worker job is reclaimed after lease expiry |
| REL-009 | Fencing/ownership checks for stale workers | v1.1 P1 | Expired worker cannot commit stale state |
| REL-010 | Concurrent execution isolation | v1.1 P1 | 50 simulated users do not cross-contaminate state |
| REL-011 | Worker pool concurrency caps | v1.1 P1 | At most 20 active executions in configured demo environment |
| REL-012 | Rate limit per user/tenant and global API | v1.1 P1 | 30 create requests/min/user; excess 429 with Retry-After when possible |
| REL-013 | Provider RPM/TPM budget and concurrency guard | v1.1 P1 | Provider quota not exceeded by scheduler under controlled test |
| REL-014 | Bounded queue, backpressure and load shedding | v1.1 P1 | At queue >100 pending jobs, reject new admissions with 429/503 as appropriate |
| REL-015 | Graceful shutdown and restart | v1.1 P1 | Stop intake; drain or safely relinquish jobs; resume after restart |
| REL-016 | Circuit breaker closed/open/half-open | v1.1 P1 | Dependency failure trips breaker; controlled probes restore service |
| REL-017 | Dead-letter/reconciliation handling | v1.1 P1 | Exhausted/poison jobs inspectable, not silently lost |
| REL-018 | Fair scheduling and priorities | v2.0 P2 | High priority handoffs expedited without starvation |
| REL-019 | Saga/compensation for multi-step external actions | v2.0 P2 | Compensation and non-compensable steps explicitly modeled |
| REL-020 | Distributed rate limiting and multi-tenant quotas | v2.0 P2 | Limits hold across multiple API replicas |
| REL-021 | Load-aware autoscaling and capacity planning | v2.0 P2 | Scale policy tied to queue age, latency and quotas |

### 7.1 Idempotency specification

- Scope: `(tenant_id, operation_type, idempotency_key)`; MVP may use a single fixed tenant but retain the field.
- Persist canonical request hash, status, result reference and timestamps under a unique database constraint.
- Same key and same payload: return prior result or `IN_PROGRESS`/equivalent; same key and different payload: `409 Conflict`.
- Side-effecting external service must accept idempotency key or expose a reliable query-by-operation-ID reconciliation path. If neither exists, mark outcome uncertain and require human reconciliation; **never assert exactly-once**.
- Retention window must exceed maximum retry/replay window; define and test expiration policy before production use. Suggested demo retention: 7 days.
- Client retries must reuse the original key for the same logical action; a genuinely new action gets a new key.

### 7.2 Durable workflow and queue specification

- PostgreSQL is source of truth for executions, transitions, checkpoints, idempotency records and outbox.
- State transition and outbox insert must be in the same transaction when producing work.
- Outbox dispatcher can publish more than once; consumers must deduplicate and verify current state/version.
- Redis may be queue/cache/rate limiter but must not be the sole durable record of acknowledged executions.
- Workers are stateless relative to durable workflow state; resume must rehydrate from DB.
- Never replay a non-idempotent external side effect solely because the worker did not persist the response.

### 7.3 Retry and recovery policy

- Retry only transient categories: timeouts, transport failures, rate limits, selected 5xx; use bounded exponential backoff + jitter and respect provider `Retry-After`.
- Never automatically retry malformed input, policy denial, invalid permissions or clinically unsafe decisions.
- After budget exhaustion, enter `FAILED`, `WAITING_APPROVAL` or `RECONCILIATION_REQUIRED` according to outcome certainty and risk.
- Distinguish failure before call, during call with unknown outcome, and after successful remote effect but before local checkpoint.
- Persist every attempt and recovery decision; ensure cancellation is checked before starting a new step.

### 7.4 Overload policy

- Per-user limit guards abusive request volume; global/tenant quotas protect shared resources.
- Admission controller checks queue depth and estimated resource budget **before** accepting work.
- Queue full: return 429 for quota pressure, 503 for service saturation; do not acknowledge a job that was not durably accepted.
- Worker concurrency and per-provider concurrency are independent controls.
- Use timeout budgets and circuit breakers to prevent cascading failures.
- Priority lanes and fairness become v2.0 scope; safety-critical escalation must have a safe human fallback in v1.x.

## 8. Security, governance and privacy

| ID | Requirement | Release | Acceptance criteria |
|---|---|---|---|
| SEC-001 | Authentication for operator/staff APIs | v1.0 P0 | Unauthenticated privileged call denied |
| SEC-002 | Role-based authorization for approval and tools | v1.0 P0 | Patient cannot approve staff-only action |
| SEC-003 | Policy engine outside LLM prompts | v1.0 P0 | Disallowed tool call blocked regardless of model output |
| SEC-004 | Human-in-the-loop for sensitive actions | v1.0 P0 | Approval persisted with actor/time/decision before tool call |
| SEC-005 | Synthetic patient data only | v1.0 P0 | Demo fixtures contain no real patient PII |
| SEC-006 | Secrets via environment/secret store, not repo | v1.0 P0 | Secret scan passes; credentials absent from logs |
| SEC-007 | Input/output validation and prompt-injection resilience | v1.1 P1 | Retrieved malicious instructions cannot bypass tool policy |
| SEC-008 | Audit logs with sensitive-data redaction | v1.1 P1 | Tool and approval events traceable without raw private content |
| SEC-009 | Data retention, deletion and access audit | v2.0 P2 | Configured retention enforced and testable |
| SEC-010 | Multi-tenant isolation | v2.0 P2 | Cross-tenant data/tool access rejected |
| SEC-011 | Deployment options for private/on-prem environment | v2.0 P2 | External egress dependencies documented and configurable |

**Medical safety boundary:** No diagnosis, prescription, treatment advice or autonomous emergency disposition. Use vetted red-flag rules to flag potential urgency and route to a human or explicit emergency-care guidance; avoid presenting classifier confidence as medical certainty. The app is an educational simulator.

## 9. Hospital Front Desk reference application

| ID | Requirement | Release | Acceptance criteria |
|---|---|---|---|
| HOS-001 | Vietnamese text conversation | v1.0 P0 | Multi-turn intent/slot flow works with synthetic fixtures |
| HOS-002 | Route FAQ / booking / symptoms / support intents | v1.0 P0 | Curated test set records intent confusion matrix |
| HOS-003 | Hospital FAQ RAG with citations | v1.0 P0 | Answers grounded; unknown questions abstain |
| HOS-004 | Rule-governed symptom red-flag escalation | v1.0 P0 | Red-flag cases trigger handoff, not diagnosis |
| HOS-005 | Read mock specialty/doctor/slot availability | v1.0 P0 | Tool returns deterministic test fixtures |
| HOS-006 | Pause for patient confirmation | v1.0 P0 | No booking side effect before explicit confirmation |
| HOS-007 | Create mock appointment idempotently | v1.0 P0 | Duplicate confirm/retry creates max one booking |
| HOS-008 | Human handoff/support ticket | v1.1 P1 | Staff can inspect case and record resolution |
| HOS-009 | SSE streaming and reconnect semantics | v1.1 P1 | Client reconnect does not duplicate business action |
| HOS-010 | Whisper STT voice input | v2.0 P2 | Audio transcribed; uncertain transcript asks confirmation |
| HOS-011 | Additional agent application as portability proof | v2.0 P2 | Second agent added without modifying platform runtime |

### 9.1 Reference workflow

1. Patient asks a question or requests an appointment.
2. Intent routing and deterministic safety screening.
3. If red flags or uncertainty: stop autonomous path, open staff handoff.
4. If FAQ: retrieve evidence and answer with citations or abstain.
5. If booking: collect required fields, query mock availability, present options.
6. Persist `WAITING_INPUT` checkpoint while awaiting patient confirmation.
7. On confirmation, invoke policy-checked MCP booking tool with stable idempotency key.
8. Commit result; on ambiguous timeout reconcile remote operation before retry.
9. Emit trace, audit events and metrics; report terminal status.

## 10. API contracts (initial)

| Method | Endpoint | Behavior |
|---|---|---|
| `GET` | `/agents` | List authorized registered agents and versions |
| `POST` | `/agents/{agent_id}/executions` | Start execution; accepts `Idempotency-Key`; returns `202` and execution ID |
| `GET` | `/executions/{execution_id}` | Status, current step, version, timestamps |
| `GET` | `/executions/{execution_id}/events` | Paginated event history, authorized/redacted |
| `POST` | `/executions/{execution_id}/input` | Submit user input with input event ID/version guard |
| `POST` | `/executions/{execution_id}/approval` | Authorized staff approve/reject with decision ID |
| `POST` | `/executions/{execution_id}/cancel` | Request cancellation, idempotent |
| `GET` | `/health/live` | Liveness |
| `GET` | `/health/ready` | Readiness/dependency checks |
| `GET` | `/metrics` | Protected telemetry endpoint |

- Standard error body: `error_code`, `message`, `trace_id`, optional `retry_after` and `details` (safe/redacted).
- Document `400`, `401`, `403`, `404`, `409`, `422`, `429`, `500`, `503` semantics.
- All mutation endpoints must specify idempotency, concurrency and authorization rules.

## 11. Data model (logical)

- `agents(id, version, config, created_at)`
- `executions(id, tenant_id, agent_id, agent_version, status, current_step, state_json, version, trace_id, created_at, updated_at)`
- `execution_events(id, execution_id, sequence, type, payload_redacted, timestamp)`
- `step_attempts(id, execution_id, step_id, attempt, status, error_class, started_at, ended_at)`
- `checkpoints(id, execution_id, version, state_json, created_at)`
- `idempotency_records(tenant_id, operation_type, key, request_hash, status, result_ref, expires_at)`
- `outbox_events(id, aggregate_id, type, payload, published_at)`
- `worker_leases(execution_id, owner_id, fencing_token, expires_at)`
- `approvals(id, execution_id, action, actor_id, decision, decided_at)`
- `tool_invocations(id, execution_id, operation_id, tool_name, status, result_ref, timestamp)`
- `conversation_messages(id, conversation_id, role, content_redacted, created_at)`
- `knowledge_documents(id, version, source, metadata)` and `knowledge_chunks(id, document_id, embedding, text, metadata)`
- `audit_records(id, actor, action, resource, outcome, trace_id, timestamp)`
- `evaluation_runs(id, dataset_version, agent_version, metrics, created_at)`

Define uniqueness constraints, foreign keys, indexes, retention and migration strategy during detailed design. Keep medical-domain tables (appointments, slots, tickets) in the hospital application schema.

## 12. Non-functional requirements and measurable targets

**Benchmark profile (proposed):** one documented local Docker Compose deployment, mock MCP and deterministic/fixed-latency LLM stub for infrastructure load tests. Separately measure real LLM latency/cost. Results must record hardware, test duration, data size and configuration.

| ID | Dimension | Target | Release |
|---|---|---|---|
| NFR-001 | API response | p95 execution creation <500 ms excluding LLM, under target load | v1.1 P1 |
| NFR-002 | Concurrency | 50 simulated concurrent users; no cross-run state leakage | v1.1 P1 |
| NFR-003 | Worker cap | At most 20 active execution slots (configurable) | v1.1 P1 |
| NFR-004 | Queue capacity | 100 pending jobs; explicit reject beyond bound | v1.1 P1 |
| NFR-005 | User rate limit | 30 execution-creation requests/min/user (configurable) | v1.1 P1 |
| NFR-006 | State durability | 0 lost acknowledged executions in crash/restart suite | v1.0 P0 |
| NFR-007 | Side effects | 0 duplicate appointments in 100 concurrent same-key submissions | v1.0 P0 |
| NFR-008 | Concurrency safety | 0 invalid double-committed transitions in worker race suite | v1.0 P0 |
| NFR-009 | Recovery | Reclaim interrupted jobs after configured lease expiry; no unsafe blind replay | v1.1 P1 |
| NFR-010 | Observability | 100% accepted executions have trace/correlation ID and terminal or waiting state | v1.0 P0 |
| NFR-011 | Security | 100% denied tool/approval requests blocked before side effects in negative suite | v1.0 P0 |
| NFR-012 | Load reporting | Report throughput, p50/p95/p99 latency, error rate, queue depth/age | v1.1 P1 |
| NFR-013 | Shutdown | No acknowledged job lost across graceful stop/restart | v1.1 P1 |
| NFR-014 | Cost | Per-execution token count and estimated model cost visible | v1.1 P1 |
| NFR-015 | Availability | Define measured service SLO after stable benchmark baseline; do not invent uptime claim | v2.0 P2 |

## 13. Observability and evaluation

| ID | Requirement | Release | Acceptance criteria |
|---|---|---|---|
| OBS-001 | Structured logs and correlation IDs | v1.0 P0 | Trace execution from API to tool call |
| OBS-002 | Execution events and step attempts | v1.0 P0 | Failure root cause visible without raw sensitive payload |
| OBS-003 | Distributed tracing (OpenTelemetry) | v1.1 P1 | Trace spans API, runtime, LLM, MCP, DB |
| OBS-004 | Runtime metrics and dashboards | v1.1 P1 | Queue depth/age, worker utilization, retries, failures, latency |
| OBS-005 | Token/cost and provider metrics | v1.1 P1 | Per-agent/per-execution breakdown |
| OBS-006 | Alerts and SLO burn-rate concepts | v2.0 P2 | Alert thresholds tied to error/latency budgets |
| EVAL-001 | Versioned golden dataset for FAQ, intent, booking, red flags | v1.0 P0 | Dataset and expected outputs committed to repo |
| EVAL-002 | Deterministic workflow/tool correctness tests | v1.0 P0 | Invalid transition, duplicate side effect and policy tests pass |
| EVAL-003 | Retrieval/citation and groundedness evaluation | v1.1 P1 | Recall@k, citation validity, abstention reported |
| EVAL-004 | Safety evaluation | v1.1 P1 | Red-flag miss rate and unsafe action rate reported, with manual review |
| EVAL-005 | Regression and model/prompt version comparison | v2.0 P2 | Compare quality, latency, cost and failure rates |
| EVAL-006 | Adversarial/prompt injection testing | v2.0 P2 | Tool policy holds under malicious retrieved content |

Evaluation must distinguish deterministic checks, heuristic/LLM-as-judge scoring and human review. Report sample size and limitations; no blanket hallucination detection guarantees.

## 14. Failure injection / acceptance test matrix

| ID | Injected scenario | Required result | Release |
|---|---|---|---|
| FT-001 | 100 same-key concurrent booking requests | Max one remote booking; consistent responses or in-progress status | v1.0 |
| FT-002 | Same key, different request body | 409; no second effect | v1.0 |
| FT-003 | Two workers update same execution version | One commit, other conflict/reload | v1.0 |
| FT-004 | Restart while waiting for patient confirmation | Waiting state preserved; resume works | v1.0 |
| FT-005 | Crash after external booking succeeds before local checkpoint | Query/reconcile result; no duplicate | v1.0 |
| FT-006 | Unauthorized tool/approval request | Denied before side effect; audit event | v1.0 |
| FT-007 | Missing/irrelevant RAG evidence | Abstain or handoff, no fabricated citation | v1.0 |
| FT-008 | LLM timeout, 429 and 5xx | Correct bounded retry/backoff and final outcome | v1.1 |
| FT-009 | Kill worker with active lease | Reclaim after expiry; stale worker fenced | v1.1 |
| FT-010 | Crash between DB commit and queue publish | Outbox eventually delivers accepted work | v1.1 |
| FT-011 | Queue delivers same job twice | One valid state progression | v1.1 |
| FT-012 | 50 simultaneous users | No cross-run data leaks; record latency/error metrics | v1.1 |
| FT-013 | Exceed per-user rate limit | 429; no job accepted beyond quota | v1.1 |
| FT-014 | Queue exceeds capacity | Bounded queue, 429/503, no silent drop | v1.1 |
| FT-015 | MCP server outage | Circuit opens/degrades; retries bounded | v1.1 |
| FT-016 | Graceful worker shutdown | No new intake; existing work completed or safely reclaimed | v1.1 |
| FT-017 | Cancellation during side-effect uncertainty | Reconciliation before final cancellation claim | v1.1 |
| FT-018 | Poison job exhausts retries | Inspectable DLQ or reconciliation record | v1.1 |
| FT-019 | Multi-tenant cross-access attempt | Denied; tenant-scoped state and tools | v2.0 |
| FT-020 | Multi-step saga partial failure | Compensate when safe or escalate non-compensable step | v2.0 |

## 15. Definition of Done by release

### MVP v1.0

- [ ] Hospital workflow completes FAQ and mock booking paths end-to-end.
- [ ] Agent config, state machine, checkpoint and resume implemented.
- [ ] MCP tool invocation is schema-validated and policy-checked.
- [ ] LLM gateway and RAG citations function with abstention behavior.
- [ ] Appointment side effects use persistent idempotency and ambiguous-outcome reconciliation.
- [ ] Crash/restart, duplicate confirm, concurrent CAS and authorization tests pass.
- [ ] Synthetic data, safe demo policies, structured logs and documented run instructions exist.

### Reliability v1.1

- [ ] Durable queue/outbox, worker lease and stale-owner protection implemented.
- [ ] Rate limits, concurrency caps, queue bounds, backpressure and load shedding tested.
- [ ] Circuit breaker, bounded retries, graceful shutdown and DLQ/reconciliation implemented.
- [ ] OpenTelemetry traces, metrics, cost tracking and load benchmark report available.
- [ ] Failure injection suite FT-001 through FT-018 runs reproducibly.

### Platform v2.0

- [ ] Second domain agent uses same runtime without core changes.
- [ ] Multi-agent handoff, advanced scheduling/fairness and multi-tenant isolation demonstrated.
- [ ] Enhanced RAG, evaluation, security and model routing validated.
- [ ] Saga/compensation, sandboxing and private deployment constraints documented and tested where applicable.

## 16. Implementation approach and suggested stack

- **Backend:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Runtime:** custom deterministic state machine first; optional LangGraph adapter later. Document decision and trade-offs.
- **Database:** PostgreSQL; pgvector for RAG.
- **Queue:** DB-backed/outbox baseline; Redis-backed workers with durable DB source of truth in v1.1.
- **MCP:** official Python MCP SDK with mock hospital services.
- **LLM:** provider adapter with deterministic stub for tests; external LLM optional for interactive demo.
- **Telemetry:** OpenTelemetry, structured logging; optional Langfuse/Grafana.
- **Testing:** pytest, integration tests, fault injection, Locust/k6 for load; Docker Compose for reproducibility.

### Suggested repository layout

```text
agentos-lite/
  requirement.md
  docs/{architecture.md,adr/,api.md,runbook.md,test-plan.md}
  platform/{api,runtime,registry,llm_gateway,mcp,retrieval,memory,policy,queue,telemetry,evaluation}/
  agents/hospital_frontdesk/{workflow,config,prompts,policies,tools,fixtures}/
  infrastructure/{db,migrations,compose}/
  tests/{unit,integration,concurrency,fault_injection,evaluation,load}/
  docker-compose.yml
```

## 17. Risks and architecture decisions to resolve

| Decision | Initial recommendation | Trade-off |
|---|---|---|
| Custom runtime vs LangGraph | Custom small deterministic core | More learning, more engineering/testing burden |
| Queue source of truth | PostgreSQL + outbox | More DB work; clear durability boundary |
| Redis use | Optional transport/cache/limiter | Must not be sole checkpoint source |
| MCP transport | Local/HTTP mock servers | Keep contracts stable, avoid unnecessary complexity |
| Idempotency remote support | Build mock service with operation-key lookup | Demonstrates realistic uncertain-outcome recovery |
| Multi-agent | Defer to v2.0 | Avoid premature orchestration complexity |
| LLM autonomy | Bound step count, tools and budgets | Less autonomy, more safety and predictability |
| Safety scope | Administrative workflows + escalation only | No real clinical decision support |
| Benchmark targets | Proposed demo targets, not production SLO | Must measure before claiming performance |

## 18. Proposed execution plan

1. **Foundation:** repository, architecture ADR, FastAPI, PostgreSQL schema, execution state machine and API.
2. **First vertical slice:** hospital intent, FAQ RAG, mock appointment MCP, user confirmation.
3. **Correctness:** transactional state changes, idempotency keys, external reconciliation, crash tests.
4. **Reliability:** outbox, queue/worker, leases, rate limiting, overload controls, retry/circuit breaker.
5. **Governance:** policy engine, approval, auth, audit and safety evaluation.
6. **Observability:** traces, metrics, token/cost, dashboards and reproducible load tests.
7. **Extensibility:** second agent, multi-agent handoff, advanced retrieval and multi-tenant features.

## 19. Interview demonstration scenarios

1. **Happy path:** Vietnamese FAQ → cited answer; appointment search → patient confirmation → one mock booking.
2. **Crash window:** kill worker after remote booking success but before checkpoint → restart → reconcile by operation ID → no duplicate.
3. **Concurrency race:** duplicate confirmation and two workers → version conflict + idempotency; one logical effect.
4. **Overload:** 50 users, 20 worker slots, bounded queue and rate limit → controlled 429/503, measurable queue depth/latency.
5. **Governance:** malicious/unauthorized tool request → blocked and audited; suspicious symptoms → human escalation.
6. **Evaluation:** run versioned golden dataset, show retrieval, safety, latency and cost trade-offs.

---

**Baseline acceptance:** This specification defines the intended *whole system*. Release tags separate what to build first from what to build later. Before implementation, create an HLD and ADRs for the state/queue/idempotency boundaries, and keep requirement IDs traceable to automated tests.
