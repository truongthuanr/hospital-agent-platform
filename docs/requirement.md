# Hospital Agent Platform — System Requirements Specification

**Document:** `requirement.md`  
**Specification version:** 1.0 (complete target-system overview)  
**Implementation releases:** MVP v1.0 → Reliability v1.1 → Platform v2.0  
**Status:** Proposed baseline; targets must be validated by tests  
**Reference application:** Hospital Front Desk Agent  
**Primary language:** Vietnamese; technical contracts in English

> This is a complete requirements inventory, **not** a claim that all features must be delivered in the first sprint. Each requirement is assigned a target release and priority. A feature is complete only when its acceptance criteria are demonstrated.

## 1. Vision and boundaries

Build a reusable, reliable, governed AI agent execution platform. Hospital Front Desk is the first reference application, not a dependency of platform core. The platform must support deterministic workflows, optional LLM-driven decisions, controlled tool invocation, durable execution, human interaction, evaluation, and operational visibility.

The Hospital Front Desk reference application provides general guidance only; it does not provide medical advice or make clinical decisions.

### 1.1 Goals

- Register and version agents with declared workflow, prompts, tools, model settings and policies.
- Execute workflows asynchronously with durable state, retries, scheduling, cancellation, pause/resume and crash recovery.
- Provide LLM gateway, MCP integration, RAG, memory and structured outputs.
- Prevent unauthorized or unsafe actions with policy checks and human approval.
- Demonstrate concurrency correctness, idempotent effects, overload protection, observability and reproducible evaluation.
- Make it possible to add a second domain agent without changing runtime core.

### 1.2 Personas

| Role | Capabilities |
|---|---|
| Patient (simulated) | Ask about hospital services, follow registration and location guidance, request and confirm mock bookings; use the mock service queue and request cancellation from v1.1 |
| Reception staff (simulated) | Handle administrative handoffs and approvals; manage cases and queue issues from v1.1 |
| Medical staff (simulated) | Review medically sensitive handoffs; retain responsibility for clinical decisions |
| Hospital administrator (v1.1) | Manage tenant members and hospital-specific configuration |
| Agent developer | Register/version agents, workflows, tools, policies |
| Platform operator | Inspect traces, queue, failures, replay/recover, audit |
| Evaluator | Run datasets and inspect quality/safety/reliability results |

## 2. Releases and priorities

- **MVP v1.0 / P0:** Single-instance end-to-end platform and one synthetic hospital. Hospital information, procedure guidance, static navigation, mock appointment booking and minimal staff handoff run on PostgreSQL-backed durable work admission/outbox, version-pinned execution and idempotent mock effects. Restart recovery is required; hospital service queue, multiple hospitals and live multi-replica recovery are v1.1 scope.
- **Reliability v1.1 / P1:** Mock hospital service queue and tracking, appointment changes, advanced navigation, worker leases and fencing, concurrent processing, cancellation, multi-tenant isolation and quotas, backpressure, rate limiting, operator recovery, circuit breakers, richer staff case handling and SLO measurement.
- **Platform v2.0 / P2:** Multi-agent handoffs, advanced scheduling/fairness, tenant lifecycle extensions, model routing/fallback, hybrid retrieval/reranking, governance/evaluation extensions and scale-out.
- **Priority convention:** P0 essential; P1 important production-hardening; P2 advanced. Release targets are planning goals, not promises of production readiness.

**Release dependency rule:** If a P0 acceptance test needs a capability, its minimal implementation and test belong to v1.0. Later releases may extend that capability but cannot be its first implementation.

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

Hospital Front Desk Agent = workflow + prompts + domain policy + hospital knowledge/configuration + mock appointment and service-queue tools
```

**Boundary rule:** Platform core must not contain patient, symptom, doctor, appointment, procedure, location or hospital service-queue domain models. The hospital app owns these concepts. State store, conversation memory, knowledge store and immutable audit/event history are logically separate.

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
| PLT-009 | Version pinning per execution | v1.0 P0 | Registered workflow, prompt, model and policy versions are immutable; an in-flight run uses its recorded versions after config update/restart |
| PLT-010 | Safe operator retry/reconciliation workflow | v1.1 P1 | Operator action logged; cannot blindly replay uncertain side effects |
| PLT-011 | Persisted delayed retry | v1.0 P0 | Retry runs no earlier than persisted due time and survives restart |
| PLT-012 | Multi-agent supervisor, handoff and shared context contracts | v2.0 P2 | Handoff preserves trace and scoped context |
| PLT-013 | General workflow scheduling | v1.1 P1 | Scheduled start survives restart and executes no earlier than due time |

### 4.1 Execution state model

- `PENDING` → `RUNNING` → `COMPLETED` / `FAILED`; `CANCELLED` and cancellation transitions are introduced in v1.1.
- `RUNNING` may enter `WAITING_INPUT`, `WAITING_APPROVAL`, `RETRY_SCHEDULED`, `RECONCILIATION_REQUIRED`; valid events resume into `RUNNING`.
- `FAILED` and `COMPLETED` are terminal in v1.0; `CANCELLED` is also terminal in v1.1. Explicit operator re-run in v1.1 creates a new execution linked to the original.
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
| TOOL-010 | Mock hospital service-queue tool contract | v1.1 P1 | Registration and status reads enforce patient ownership, scoped uniqueness, stable operation IDs and uncertain-outcome reconciliation |

## 7. Distributed systems, reliability and concurrency contracts

| ID | Requirement | Release | Acceptance criteria |
|---|---|---|---|
| REL-001 | Durable execution creation and checkpoint commits | v1.0 P0 | No acknowledged execution disappears after restart |
| REL-002 | API and side-effect idempotency | v1.0 P0 | Same scoped key + same payload yields same logical result; changed payload conflicts |
| REL-003 | At-least-once safe step execution | v1.0 P0 | Duplicate deliveries do not duplicate committed state or supported external effects |
| REL-004 | Optimistic locking for execution state | v1.0 P0 | Two concurrent transitions: only one wins version CAS |
| REL-005 | Exponential backoff + jitter + retry budget | v1.0 P0 | Bounded retry; permanent validation errors not retried |
| REL-006 | Ambiguous external outcome reconciliation | v1.0 P0 | Crash after remote success resolves by operation key or enters RECONCILIATION_REQUIRED |
| REL-007 | PostgreSQL-backed durable work queue and transactional outbox | v1.0 P0 | Execution/checkpoint and work intent commit atomically; crash before dispatch causes no lost accepted work after restart |
| REL-008 | Worker lease, heartbeat, expiry and reclaim | v1.1 P1 | Killed worker job is reclaimed after lease expiry |
| REL-009 | Fencing/ownership checks for stale workers | v1.1 P1 | Expired worker cannot commit stale state |
| REL-010 | Concurrent execution isolation | v1.1 P1 | 50 simulated users do not cross-contaminate state |
| REL-011 | Worker pool concurrency caps | v1.1 P1 | At most 20 active executions in configured demo environment |
| REL-012 | Rate limit per user/tenant and global API | v1.1 P1 | 30 create requests/min/user plus configurable tenant/global limits; excess 429 with Retry-After when possible |
| REL-013 | Provider RPM/TPM budget and concurrency guard | v1.1 P1 | Provider quota not exceeded by scheduler under controlled test |
| REL-014 | Bounded queue, backpressure and load shedding | v1.1 P1 | At queue >100 pending jobs, reject new admissions with 429/503 as appropriate |
| REL-015 | Graceful shutdown and restart | v1.1 P1 | Stop intake; drain or safely relinquish jobs; resume after restart |
| REL-016 | Circuit breaker closed/open/half-open | v1.1 P1 | Dependency failure trips breaker; controlled probes restore service |
| REL-017 | Dead-letter/reconciliation handling | v1.1 P1 | Exhausted/poison jobs inspectable, not silently lost |
| REL-018 | Fair scheduling and priorities | v2.0 P2 | High priority handoffs expedited without starvation |
| REL-019 | Saga/compensation for multi-step external actions | v2.0 P2 | Compensation and non-compensable steps explicitly modeled |
| REL-020 | Distributed rate limiting and multi-tenant quotas | v1.1 P1 | Tenant admission, worker and provider quotas hold across two API/worker replicas; one tenant cannot consume another tenant's reserved quota |
| REL-021 | Load-aware autoscaling and capacity planning | v2.0 P2 | Scale policy tied to queue age, latency and quotas |

### 7.1 Idempotency specification

- Scope: `(tenant_id, operation_type, idempotency_key)`; MVP may use a single fixed tenant but retain the field.
- Persist canonical request hash, status, result reference and timestamps under a unique database constraint.
- Same key and same payload: return prior result or `IN_PROGRESS`/equivalent; same key and different payload: `409 Conflict`.
- Side-effecting external service must accept idempotency key or expose a reliable query-by-operation-ID reconciliation path. If neither exists, mark outcome uncertain and require human reconciliation; **never assert exactly-once**.
- Retention window must exceed maximum retry/replay window; define and test expiration policy before production use. Suggested demo retention: 7 days.
- Client retries must reuse the original key for the same logical action; a genuinely new action gets a new key.

### 7.2 Durable workflow and queue specification

- In v1.0, a single service deployment with local worker concurrency uses PostgreSQL for durable work admission and restart recovery. Duplicate dispatch is safe. Live multi-replica worker reclamation and fencing are v1.1 scope.
- PostgreSQL is source of truth for executions, transitions, checkpoints, idempotency records, delayed retry due times and outbox.
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
- Persist every attempt and recovery decision; from v1.1, ensure cancellation is checked before starting a new step.

### 7.4 Overload policy

- From v1.1, per-user limits guard abusive request volume; global/tenant quotas protect shared resources.
- From v1.1, the admission controller checks queue depth and estimated resource budget **before** accepting work.
- From v1.1, queue full returns 429 for quota pressure or 503 for service saturation; no release may acknowledge a job that was not durably accepted.
- From v1.1, worker concurrency and per-provider concurrency are independent controls.
- Use timeout budgets from v1.0 and circuit breakers from v1.1 to prevent cascading failures.
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
| SEC-007 | Input/output validation and baseline prompt-injection resilience | v1.0 P0 | Retrieved malicious instructions cannot bypass tool policy in the fixed negative suite |
| SEC-008 | Audit logs with sensitive-data redaction | v1.0 P0 | Tool and approval events traceable without raw private content |
| SEC-009 | Data retention, deletion and access audit | v2.0 P2 | Configured retention enforced and testable |
| SEC-010 | Multi-tenant isolation | v1.1 P1 | Cross-tenant reads, writes, retrieval and tool calls are denied; tests cover API and worker paths |
| SEC-011 | Deployment options for private/on-prem environment | v2.0 P2 | External egress dependencies documented and configurable |
| SEC-012 | Synthetic patient execution ownership | v1.0 P0 | A patient session cannot read or submit input for another session's execution |

**Medical safety boundary:** No diagnosis, prescription, treatment advice or autonomous emergency disposition. Use vetted red-flag rules to flag potential urgency and route to a human or explicit emergency-care guidance; avoid presenting classifier confidence as medical certainty. The app is an educational simulator.

### 8.1 Multi-tenant functional requirements (v1.1)

v1.0 uses one fixed synthetic tenant in execution and idempotency records. v1.1 supports at least two independent synthetic hospital organizations in one deployment and one shared PostgreSQL database. Tenant deletion, self-service billing, custom identity providers and dedicated per-tenant infrastructure are outside v1.1.

| ID | Requirement | Release | Acceptance criteria |
|---|---|---|---|
| TEN-001 | Tenant creation and listing | v1.1 P1 | Platform operator creates a tenant with unique ID/name and initial tenant admin; duplicate ID is rejected; ordinary members see only their tenant metadata |
| TEN-002 | Membership and tenant roles | v1.1 P1 | Tenant admin can add, change and revoke members within their tenant; roles include tenant_admin, agent_developer, staff and evaluator; revocation blocks the next request; last tenant admin cannot be removed |
| TEN-003 | Trusted active tenant context | v1.1 P1 | Every tenant-scoped request resolves exactly one active tenant from validated identity/session and membership; a client-supplied tenant ID alone cannot grant access |
| TEN-004 | Tenant-scoped agent registry | v1.1 P1 | Agent IDs/versions/configs and policy/tool allowlists belong to one tenant; same agent ID may exist in two tenants without cross-selection |
| TEN-005 | Tenant-scoped execution and events | v1.1 P1 | Create, list/read, input, approval, cancel and retry use the active tenant; guessed foreign execution IDs reveal no state and cause no mutation |
| TEN-006 | Tenant-scoped knowledge and memory | v1.1 P1 | Retrieval filters by tenant before returning chunks/citations; conversation memory and any enabled memory store cannot include another tenant's content |
| TEN-007 | Tenant-scoped tool effects and idempotency | v1.1 P1 | Tool calls carry server-derived tenant identity; mock appointments/handoffs and operation lookup are scoped by tenant; same idempotency key in two tenants is independent |
| TEN-008 | Tenant-scoped worker and outbox processing | v1.1 P1 | Jobs/outbox messages retain tenant identity; worker reloads and verifies tenant-owned config/state before tools or commits; wrong-tenant job is rejected and audited |
| TEN-009 | Tenant quotas and admission isolation | v1.1 P1 | Configurable tenant request, queued-job, active-worker and provider budgets hold across two replicas; excess is rejected without consuming another tenant's reserved capacity |
| TEN-010 | Tenant audit and operator access | v1.1 P1 | Tenant-owned audit records include tenant ID and actor; tenant admin sees only own audit; platform operator sees tenant metadata by default; content access requires tenant membership and is audited |
| TEN-011 | Cross-tenant negative test suite | v1.1 P1 | Two-tenant tests cover API, membership revoke, agent config, RAG, memory, tool effects, idempotency, workers, audit and quotas with zero cross-tenant leaks/effects |

**Role permissions:** Platform operator creates tenants, lists tenant metadata and configures quotas. Tenant admin manages members and reads tenant audit. Agent developer manages that tenant's agents, policies and knowledge documents. Staff handles that tenant's approvals and handoffs. Evaluator runs and reads that tenant's evaluations. A synthetic patient session accesses only its own execution within its bound tenant. Adding a role in one tenant grants no permission in another tenant.

**Tenant boundary contract:** All tenant-owned tables and domain fixtures carry `tenant_id`; uniqueness, foreign keys and queries use tenant scope. The server derives tenant context from authenticated membership (or a tenant-bound synthetic patient session). A user belonging to multiple tenants explicitly selects one permitted active tenant before making a scoped request; a synthetic patient session is bound to one tenant and cannot switch. Foreign resource IDs return `404` without revealing existence; a known tenant with insufficient role returns `403`. Global platform configuration remains separate from tenant-owned content. Platform operators cannot bypass tenant membership for content access.

## 9. Hospital Front Desk reference application

The reference application uses synthetic hospital and patient data. Its answers provide general administrative guidance, not medical advice or clinical decisions. The hospital service queue below is distinct from the platform work queue in sections 3 and 7. v1.0 serves one configured synthetic hospital; v1.1 adds independently managed hospitals through the tenant controls in section 8.1.

| ID | Requirement | Release | Acceptance criteria |
|---|---|---|---|
| HOS-001 | Vietnamese text conversation and multi-turn context | v1.0 P0 | Patient can ask follow-up questions, switch supported intents and resume a waiting workflow without losing its persisted state |
| HOS-002 | Route information, procedure, navigation, booking, symptoms and support intents | v1.0 P0 | Versioned intent dataset records confusion matrix; ambiguous requests trigger clarification |
| HOS-003 | Hospital FAQ RAG with citations and abstention | v1.0 P0 | Answers cite approved source IDs; missing or irrelevant evidence produces uncertainty or handoff, never a fabricated answer |
| HOS-004 | Rule-governed warning-indicator escalation | v1.0 P0 | Configured warning indicators stop autonomous booking, create a persisted staff-visible handoff and show approved fallback guidance; no diagnosis is produced |
| HOS-005 | Read mock specialty, doctor and appointment-slot availability | v1.0 P0 | Availability comes from a deterministic scheduling fixture, not an LLM-generated slot |
| HOS-006 | Pause for explicit patient booking confirmation | v1.0 P0 | No booking side effect occurs before confirmation; waiting state survives restart |
| HOS-007 | Create mock appointment idempotently | v1.0 P0 | Duplicate confirmation or retry creates at most one booking per logical request; expired or contested slots are rejected |
| HOS-008 | Minimal human handoff | v1.0 P0 | Staff can identify and inspect a persisted handoff; if no staff is available, approved fallback guidance is shown and the case remains pending |
| HOS-009 | SSE streaming and reconnect semantics | v1.1 P1 | Client reconnect does not duplicate a business action |
| HOS-010 | Speech-to-text voice input | v2.0 P2 | Uncertain transcript is confirmed before a side effect; text path remains available |
| HOS-011 | Additional agent application as portability proof | v2.0 P2 | Second agent is added without modifying platform runtime |
| HOS-012 | Staff case resolution workflow | v1.1 P1 | Authorized staff assign, update, close or reopen a support case with audit history |
| HOS-013 | Answer approved hospital information inquiries | v1.0 P0 | Hours, departments, services, registration requirements, BHYT procedures and published fee information are answered from configured sources; unavailable facts are disclosed |
| HOS-014 | Guide examination registration and arrival procedures | v1.0 P0 | First-time and pre-booked patient scenarios show the correct ordered steps and required documents from configured procedures |
| HOS-015 | Locate departments, rooms and service counters | v1.0 P0 | Agent asks for a starting location when needed and gives a verified building, floor and room/counter route; unknown or outdated locations are not invented |
| HOS-016 | Track progress through multi-step guidance | v1.0 P0 | Patient can continue the current step after a follow-up question or process restart; the persisted step matches the approved procedure version |
| HOS-017 | Configure hospital information and procedures | v1.0 P0 | One synthetic hospital has versioned, approved fixtures for hours, departments, locations, procedures, knowledge, staff routing and booking rules |
| HOS-018 | Identify stale or unavailable operational information | v1.0 P0 | Time-sensitive hours, fees, availability and locations expose an effective date or last-updated value where configured; stale or missing information triggers disclosure or handoff |
| HOS-019 | Register a patient in a mock hospital service queue | v1.1 P1 | After collecting required information and confirmation, an open service issues one number; concurrent allocations are unique within hospital, service, date and configured queue scope |
| HOS-020 | Read hospital service queue status | v1.1 P1 | Patient sees their authorized number, status and assigned counter from the queue service; currently serving number is read from backend state |
| HOS-021 | Recover and reconcile queue registration | v1.1 P1 | Duplicate requests or worker recovery create at most one registration per logical request; uncertain outcomes are checked before retry |
| HOS-022 | Handle unavailable queue services | v1.1 P1 | Closed or failed service does not issue a number and is never reported as successful |
| HOS-023 | Manage existing mock appointments | v1.1 P1 | Authorized patient can retrieve, reschedule or cancel a booking within configured rules; each change is confirmed, idempotent and audited |
| HOS-024 | Provide advanced navigation and accessibility routes | v1.1 P1 | Multi-building routes and accessible routes are returned only when configured and current |
| HOS-025 | Provide queue notifications and estimates | v1.1 P1 | Optional approaching-turn notice and wait estimate use backend data and label estimates as approximate |
| HOS-026 | Configure separate hospital tenants and staff policies | v1.1 P1 | Two synthetic hospitals independently configure knowledge, locations, queues, schedules and staff routing; tenant isolation tests pass |
| HOS-027 | Show interactive floor maps | v2.0 P2 | Map location and route agree with approved hospital configuration |
| HOS-028 | Add multilingual and spoken responses | v2.0 P2 | Responses preserve approved content and safety behavior across supported languages and voice output |
| HOS-029 | Validate a sandbox hospital scheduling connector | v2.0 P2 | Connector respects authorization, operation reconciliation and data policy using synthetic records; no real patient transaction occurs |

### 9.1 Reference workflows

1. **Inquiry:** classify intent, retrieve approved hospital knowledge within the active hospital, cite the source and disclose when facts are missing or stale.
2. **Procedure guidance:** load the approved procedure version, give the next step, persist progress and allow clarification without losing the workflow.
3. **Navigation:** identify the requested destination and starting point, read configured location data and provide a verified route or hand off when the route is unknown.
4. **Appointment:** collect required fields, read mock availability, present options, persist `WAITING_INPUT`, obtain explicit confirmation and invoke the policy-checked booking tool with a stable idempotency key. Reconcile ambiguous outcomes before retry.
5. **Hospital service queue (v1.1):** identify an open service, collect required fields, obtain confirmation, allocate atomically with a stable operation ID and read status from the queue backend.
6. **Safety or support:** screen for configured warning indicators before routine actions; stop autonomous side effects when triggered, persist a staff-visible handoff and show approved fallback guidance.
7. All paths emit trace, redacted audit events and an accurate waiting, completed or failed status.

### 9.2 Hospital business rules

- Hospital information, procedures, locations, hours and fees come from approved versioned sources. The agent must disclose uncertainty and must not invent prices, insurance coverage, availability, rooms or routes.
- General information inquiries do not require patient identification. Booking, queue registration and access to an existing record require only the identity and fields needed for that action; patient sessions can access only their own records.
- Availability and queue status come from their mock backend services. A displayed appointment slot is not reserved until booking succeeds; concurrent bookings cannot exceed slot capacity.
- Every side-effecting appointment or queue operation has a stable operation identity. A timeout is not proof of failure; reconcile an uncertain outcome before retry or reporting success.
- Symptom signals support administrative handoff only. No diagnosis, treatment, prescription or autonomous emergency disposition is permitted. Warning indicators and patient-facing fallback guidance require qualified review before use; classifier confidence is not a clinical probability.
- In v1.0, hospital-specific fixtures belong to one fixed synthetic tenant. From v1.1, hospital business records, knowledge retrieval, policies, staff actions and service effects are scoped to the validated active tenant.
- Hospital service queue numbers are unique within their configured scope; status is read from backend state. Closed services and failed operations never yield a success message.

## 10. API contracts (initial)

| Method | Endpoint | Behavior | Release |
|---|---|---|---|
| `GET` | `/agents` | List authorized registered agents and versions; scoped to active tenant from v1.1 | v1.0 |
| `POST` | `/agents/{agent_id}/executions` | Start execution; requires `Idempotency-Key`; returns `202` and execution ID | v1.0 |
| `GET` | `/executions/{execution_id}` | Status, current step, version, timestamps | v1.0 |
| `GET` | `/executions` | List executions visible in the active tenant and permitted role | v1.1 |
| `GET` | `/executions/{execution_id}/events` | Paginated event history, authorized/redacted | v1.0 |
| `POST` | `/executions/{execution_id}/input` | Submit user input with input event ID/version guard | v1.0 |
| `POST` | `/executions/{execution_id}/approval` | Authorized staff approve/reject with decision ID | v1.0 |
| `GET` | `/hospital/handoffs` | Staff list of pending hospital handoffs | v1.0 |
| `GET` | `/hospital/handoffs/{handoff_id}` | Staff inspect a hospital handoff | v1.0 |
| `POST` | `/hospital/handoffs/{handoff_id}/resolution` | Staff record resolution with decision ID and audit | v1.1 |
| `POST` | `/executions/{execution_id}/cancel` | Request cancellation, idempotent | v1.1 |
| `GET` | `/health/live` | Liveness | v1.0 |
| `GET` | `/health/ready` | Readiness/dependency checks | v1.0 |
| `GET` | `/metrics` | Protected telemetry endpoint | v1.1 |
| `POST` | `/tenants` | Platform operator creates a tenant | v1.1 |
| `GET` | `/tenants` | List tenant metadata authorized for the caller | v1.1 |
| `POST` | `/session/active-tenant` | Select a tenant after verifying membership; returns tenant-bound session/context | v1.1 |
| `GET` | `/tenants/{tenant_id}/memberships` | Tenant admin lists members | v1.1 |
| `POST` | `/tenants/{tenant_id}/memberships` | Tenant admin adds a member and role | v1.1 |
| `PATCH` | `/tenants/{tenant_id}/memberships/{user_id}` | Tenant admin changes a role | v1.1 |
| `DELETE` | `/tenants/{tenant_id}/memberships/{user_id}` | Tenant admin revokes membership | v1.1 |
| `GET` | `/tenants/{tenant_id}/quotas` | Tenant admin/operator reads quota configuration and usage | v1.1 |
| `PATCH` | `/tenants/{tenant_id}/quotas` | Platform operator changes tenant quotas with audit | v1.1 |
| `GET` | `/tenants/{tenant_id}/audit` | Tenant admin reads paginated, redacted tenant audit | v1.1 |

- Standard error body: `error_code`, `message`, `trace_id`, optional `retry_after` and `details` (safe/redacted).
- Document `400`, `401`, `403`, `404`, `409`, `422`, `429`, `500`, `503` semantics.
- All mutation endpoints must specify idempotency, concurrency and authorization rules. Hospital appointment and service-queue actions are invoked through authorized domain tools in the agent workflow; their schemas, operation IDs, ownership checks and reconciliation endpoints must be documented separately. The service queue is not the platform work queue.
- In v1.0, a synthetic patient session may read and submit input only for its own execution; staff-only approval and handoff access require staff identity. A mismatched session or role is denied before state changes.
- From v1.1, tenant-scoped endpoints derive the active tenant from the validated session. If the path contains `tenant_id`, it must match the active tenant and the caller's role. Revocation invalidates access on the next request; a cached tenant context must not bypass the membership check.

## 11. Data model (logical)

- `tenants(id, name, created_at)` and `tenant_memberships(tenant_id, user_id, role, status, updated_at)` (v1.1)
- `tenant_quota_configs(tenant_id, request_limit, queue_limit, worker_limit, provider_budget)` (v1.1)
- `agents(tenant_id, id, version, config, created_at)`
- `executions(id, tenant_id, agent_id, agent_version, status, current_step, state_json, version, trace_id, created_at, updated_at)`
- `execution_events(tenant_id, id, execution_id, sequence, type, payload_redacted, timestamp)`
- `step_attempts(tenant_id, id, execution_id, step_id, attempt, status, error_class, started_at, ended_at)`
- `checkpoints(tenant_id, id, execution_id, version, state_json, created_at)`
- `idempotency_records(tenant_id, operation_type, key, request_hash, status, result_ref, expires_at)`
- `outbox_events(tenant_id, id, aggregate_id, type, payload, published_at)`
- `worker_leases(tenant_id, execution_id, owner_id, fencing_token, expires_at)`
- `approvals(tenant_id, id, execution_id, action, actor_id, decision, decided_at)`
- `tool_invocations(tenant_id, id, execution_id, operation_id, tool_name, status, result_ref, timestamp)`
- `conversation_messages(tenant_id, id, conversation_id, role, content_redacted, created_at)`
- `knowledge_documents(tenant_id, id, version, source, metadata)` and `knowledge_chunks(tenant_id, id, document_id, embedding, text, metadata)`
- `audit_records(tenant_id, id, actor, action, resource, outcome, trace_id, timestamp)` (`tenant_id` nullable only for global platform administration)
- `evaluation_runs(tenant_id, id, dataset_version, agent_version, metrics, created_at)`
- Hospital application schema: `hospital_profiles`, `hospital_departments`, `hospital_locations`, `hospital_procedures` and their approved versions (v1.0 synthetic fixtures)
- Hospital application schema: `appointment_slots`, `appointments` and `handoff_cases`, with patient-session ownership, operation IDs and tenant IDs (v1.0 mock services)
- Hospital application schema: `queue_services`, `queue_registrations` and `queue_status_events`, with scoped unique numbers and operation IDs (v1.1 mock service)

For v1.1, define tenant-scoped unique constraints and composite foreign keys so a child row cannot reference another tenant's parent. Index tenant-leading access paths, including retrieval filters and outbox/queue claims. Define retention and migration strategy during detailed design. Keep hospital-domain tables (appointments, slots, service queues, procedures, locations and handoff cases) in the hospital application schema with `tenant_id`. v1.0 uses one fixed synthetic tenant; v1.1 enforces isolation across independently managed tenants. Queue number allocation and appointment capacity require database constraints and atomic transactions in their mock services.

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
| NFR-010 | Observability | 100% accepted executions have a trace/correlation ID and a persisted current state; after processing or a declared wait, each reaches a terminal or waiting state within the documented test timeout | v1.0 P0 |
| NFR-011 | Security | 100% denied tool/approval requests blocked before side effects in negative suite | v1.0 P0 |
| NFR-012 | Load reporting | Report throughput, p50/p95/p99 latency, error rate, queue depth/age | v1.1 P1 |
| NFR-013 | Shutdown | No acknowledged job lost across graceful stop/restart | v1.1 P1 |
| NFR-014 | Cost | Per-execution token count and estimated model cost visible | v1.1 P1 |
| NFR-015 | Availability | Define measured service SLO after stable benchmark baseline; do not invent uptime claim | v2.0 P2 |
| NFR-016 | Tenant isolation | 0 cross-tenant data leaks or effects in the two-tenant negative suite; every accepted tenant-owned record has a valid tenant ID | v1.1 P1 |

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
| EVAL-004 | MVP safety release gate | v1.0 P0 | Fixed versioned critical red-flag suite has zero missed handoffs and zero unauthorized tool effects; manual reviewer signs off on test cases and results; no clinical sensitivity claim |
| EVAL-005 | Regression and model/prompt version comparison | v2.0 P2 | Compare quality, latency, cost and failure rates |
| EVAL-006 | Adversarial/prompt injection testing | v2.0 P2 | Tool policy holds under malicious retrieved content |
| EVAL-007 | Expanded safety evaluation | v1.1 P1 | Red-flag miss rate and unsafe action rate reported with sample size, manual review and documented limitations |
| EVAL-008 | Hospital information and guidance evaluation | v1.0 P0 | Versioned cases cover hours, BHYT, procedures, stale facts, location lookup, missing evidence and multi-turn continuation |
| EVAL-009 | Hospital service-queue evaluation | v1.1 P1 | Concurrent allocation, duplicate retry, status ownership, closed service and crash reconciliation cases pass |

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
| FT-008 | LLM timeout, 429 and 5xx | Correct bounded retry/backoff and final outcome | v1.0 |
| FT-009 | Kill worker with active lease | Reclaim after expiry; stale worker fenced | v1.1 |
| FT-010 | Crash between DB commit and queue publish | Outbox eventually delivers accepted work after restart | v1.0 |
| FT-011 | Queue delivers same job twice | One valid state progression | v1.0 |
| FT-012 | 50 simultaneous users | No cross-run data leaks; record latency/error metrics | v1.1 |
| FT-013 | Exceed per-user rate limit | 429; no job accepted beyond quota | v1.1 |
| FT-014 | Queue exceeds capacity | Bounded queue, 429/503, no silent drop | v1.1 |
| FT-015 | MCP server outage | Circuit opens/degrades; retries bounded | v1.1 |
| FT-016 | Graceful worker shutdown | No new intake; existing work completed or safely reclaimed | v1.1 |
| FT-017 | Cancellation during side-effect uncertainty | Reconciliation before final cancellation claim | v1.1 |
| FT-018 | Poison job exhausts retries | Inspectable DLQ or reconciliation record | v1.1 |
| FT-019 | Multi-tenant cross-access attempt | Denied; tenant-scoped state, RAG, tools and audit | v1.1 |
| FT-020 | Multi-step saga partial failure | Compensate when safe or escalate non-compensable step | v2.0 |
| FT-021 | Update agent config during a waiting execution | Resume uses pinned workflow, prompt, model and policy versions | v1.0 |
| FT-022 | Red-flag handoff with no staff online | Case persists for staff; patient gets approved fallback; no autonomous booking | v1.0 |
| FT-023 | Tenant B requests execution/event/approval/input of tenant A by guessed ID | No data or mutation; foreign resource returns 404 and audit records denied access | v1.1 |
| FT-024 | Two tenants use same agent ID and idempotency key | Config, execution and mock booking remain independent; no cross-tenant conflict | v1.1 |
| FT-025 | Tenant A document appears similar to tenant B query | Tenant B receives no A chunk, citation or conversation content | v1.1 |
| FT-026 | Revoke member while tenant session is active; inject wrong-tenant worker job | Next request denied; worker rejects job before tool/effect/commit | v1.1 |
| FT-027 | Tenant A saturates request, queue and provider quota across two replicas | A is limited; B retains its configured capacity and can progress | v1.1 |
| FT-028 | Tenant admin B edits A membership/quotas or removes B's last admin | Cross-tenant edits denied; last-admin removal denied; no role escalation | v1.1 |
| FT-029 | Ask about hours, BHYT, fees and procedures with current, stale and absent sources | Current answers cite approved sources; stale or absent facts are disclosed; no invented detail | v1.0 |
| FT-030 | Ask for a department route without a starting point or with an unknown room | Starting point is requested; route uses verified location data or reports that it is unavailable | v1.0 |
| FT-031 | Interrupt multi-step registration guidance and resume after restart | Correct approved procedure version and step are restored | v1.0 |
| FT-032 | Two patients book the last available mock slot | At most the configured slot capacity is committed; unsuccessful patient receives no false confirmation | v1.0 |
| FT-033 | Concurrent hospital service-queue requests, duplicate retry and worker crash | Unique scoped queue numbers; at most one registration per logical request; uncertain outcome reconciled | v1.1 |
| FT-034 | Queue service closed or unavailable; patient requests status of another session | No number or false success; unauthorized status access denied | v1.1 |

## 15. Definition of Done by release

### MVP v1.0

- [ ] Hospital workflow completes approved information inquiry, procedure guidance, static navigation, mock booking and minimal handoff paths end-to-end.
- [ ] Agent config, state machine, checkpoint and resume implemented.
- [ ] Config versions are immutable and pinned per execution; PostgreSQL work queue/outbox and delayed retries survive restart.
- [ ] MCP tool invocation is schema-validated and policy-checked.
- [ ] LLM gateway and RAG citations function with abstention behavior.
- [ ] Appointment side effects use persistent idempotency and ambiguous-outcome reconciliation.
- [ ] Crash/restart, duplicate confirm, concurrent CAS and authorization tests pass.
- [ ] Minimal staff-visible handoff and patient fallback work; critical red-flag safety suite passes with manual review.
- [ ] FT-001 through FT-008, FT-010, FT-011, FT-021, FT-022 and FT-029 through FT-032 pass reproducibly.
- [ ] Synthetic data, safe demo policies, structured logs and documented run instructions exist.

### Reliability v1.1

- [ ] Worker lease, heartbeat, live-worker reclaim and stale-owner protection extend the v1.0 durable queue/outbox.
- [ ] Rate limits, tenant quotas, concurrency caps, queue bounds, backpressure and load shedding tested.
- [ ] Two synthetic hospitals can be created and managed; membership, active tenant context, agents, executions, RAG, hospital configuration, service effects, audit and worker paths enforce tenant isolation.
- [ ] Mock hospital service-queue registration/tracking, appointment changes, advanced navigation, cancellation, general scheduling, operator recovery and staff case resolution implemented.
- [ ] Circuit breaker, graceful shutdown and DLQ/reconciliation implemented; v1.0 bounded retry remains enforced.
- [ ] OpenTelemetry traces, metrics, cost tracking and load benchmark report available.
- [ ] v1.0 failure tests remain green; FT-009, FT-012 through FT-019, FT-023 through FT-028 and FT-033 through FT-034 run reproducibly.

### Platform v2.0

- [ ] Second domain agent uses same runtime without core changes.
- [ ] Multi-agent handoff, advanced scheduling/fairness and tenant lifecycle extensions demonstrated.
- [ ] Enhanced RAG, evaluation, security and model routing validated.
- [ ] Saga/compensation, sandboxing and private deployment constraints documented and tested where applicable.

## 16. Implementation approach and suggested stack

- **Backend:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Runtime:** custom deterministic state machine first; optional LangGraph adapter later. Document decision and trade-offs.
- **Database:** PostgreSQL; pgvector for RAG.
- **Queue:** PostgreSQL-backed queue/outbox and persisted due times in v1.0; worker leases/fencing and optional Redis transport in v1.1, with PostgreSQL as durable source of truth.
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
2. **First vertical slice:** hospital intent, approved FAQ/procedure/location fixtures, guided answers, mock appointment MCP, patient confirmation and minimal staff handoff.
3. **MVP correctness:** immutable version pinning, PostgreSQL-backed queue/outbox and delayed retry, transactional state changes, idempotency keys, external reconciliation and crash tests.
4. **MVP governance:** policy engine, approval, patient/staff access rules, audit and critical safety release gate.
5. **Reliability v1.1:** mock hospital service queue, appointment changes, advanced navigation, leases/fencing, cancellation, tenant management/isolation/quotas, operator/staff workflows, overload controls and circuit breaker.
6. **Observability:** traces, metrics, token/cost, dashboards and reproducible load tests.
7. **Extensibility:** second agent, multi-agent handoff, advanced retrieval and tenant lifecycle extensions.

## 19. Demonstration scenarios

1. **Happy path:** Vietnamese inquiry → cited hospital answer; procedure and location guidance → verified steps/route; appointment search → patient confirmation → one mock booking.
2. **Crash window:** stop the v1.0 service after remote booking success but before checkpoint → restart → reconcile by operation ID → no duplicate.
3. **Concurrency race:** duplicate confirmation and two workers → version conflict + idempotency; one logical effect.
4. **Overload:** 50 users, 20 worker slots, bounded queue and rate limit → controlled 429/503, measurable queue depth/latency.
5. **Governance:** malicious/unauthorized tool request → blocked and audited; suspicious symptoms → human escalation.
6. **Evaluation:** run versioned golden dataset, show retrieval, safety, latency and cost trade-offs.
7. **Hospital operations v1.1:** register and track a mock service-queue number; duplicate and concurrent requests preserve uniqueness and idempotency.
8. **Multi-tenant v1.1:** two synthetic hospitals use the same agent ID and request key; cross-tenant API/RAG/tool attempts are denied, while one tenant's quota saturation does not block the other.

---

**Baseline acceptance:** This specification defines the intended *whole system*. Release tags separate what to build first from what to build later. Before implementation, create an HLD and ADRs for the state/queue/idempotency boundaries, and keep requirement IDs traceable to automated tests.
