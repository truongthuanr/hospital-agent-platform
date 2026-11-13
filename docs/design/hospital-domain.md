# Hospital domain

- **Status:** detailed design baseline
- **Scope:** synthetic Hospital Front Desk MVP; service queue and appointment changes in v1.1
- **ADRs:** [005](../adr/005-hospital-knowledge.md), [006](../adr/006-safety-escalation.md), [007](../adr/007-appointment-tool.md), [008](../adr/008-hospital-service-queue.md)

## Bounded context and interfaces

Hospital Domain owns profiles, procedures, locations, appointment slots/bookings, handoff cases, service queues, and the hospital-specific workflow/policy configuration. Platform core stores opaque workflow state and invokes hospital domain tools through [Tool/MCP](tool-mcp.md); it does not contain patient, doctor, symptom, appointment, room, or service-number models. The domain publishes approved source/version references to [RAG](rag.md).

| Interface | Input | Result |
|---|---|---|
| `get_hospital_information` | Tenant, source/version, as-of time | Approved facts with provenance or unavailable/stale result |
| `get_procedure` / `get_route` | Tenant, pinned version, current step or start/destination | Ordered steps or configured route; never a guessed step/room |
| `list_slots` | Tenant, specialty/date filters | Backend availability, explicitly unreserved |
| `create_appointment` | Tenant, owner session, confirmed slot, operation ID, payload hash | One booking or known rejection; lookup by operation ID |
| `create_handoff` | Tenant, execution, kind, routing target, redacted summary | Persisted case ID and status |
| `register_queue` (v1.1) | Tenant, owner, service, fields, confirmation, operation ID | One scoped number or known rejection |

## Owned data

`hospital_profiles`, `hospital_departments`, `hospital_locations`, and `hospital_procedures` are tenant-owned versioned records with approval state, approver, source, effective-from/until, and publication time. Published versions are immutable. `appointment_slots` has capacity, booked count, schedule version, active flag and a database check `0 <= booked_count <= capacity`. `appointments` has tenant, owner session, slot, status, operation ID, timestamps, and unique `(tenant_id, operation_id)`. `handoff_cases` has tenant, execution, kind, routing target, status, redacted summary and timestamps. All records use synthetic data.

### Guidance and navigation

Information answers cite approved effective source versions; unavailable fees, hours, insurance benefits, or departments are disclosed rather than inferred. A procedure is a versioned ordered set of steps and conditions. The execution checkpoint holds `procedure_version`, `current_step`, and minimal collected fields; a follow-up question may interrupt and resume the same version. Navigation resolves start and destination IDs against current approved building/floor/room/counter data and traverses only configured valid links/waypoints. Missing start asks for clarification; unknown/expired route yields handoff or uncertainty, never an invented route. Advanced accessible/multi-building routes are v1.1 only when configured.

### Safety escalation and handoff

The first hospital workflow step applies a fixed, versioned deterministic warning-indicator screen before routine actions. A positive indicator or unresolved warning-related uncertainty stops autonomous booking, persists a staff-visible handoff plus checkpoint, and returns approved fallback text. The case remains pending if staff are offline. Only authorized scoped staff inspect or resolve it. Medical staff retain clinical decisions; the agent provides administrative escalation only. The rule owner and qualified reviewer approve the fixed warning suite and fallback before release. MVP gate: zero missed handoffs within that suite and zero unauthorized effects. This is not a clinical sensitivity claim.

### Appointment transaction (MVP)

Read specialties, doctors and slots from the mock scheduling service. Displayed availability is not a reservation. Persist `WAITING_INPUT` and a one-time confirmation before any booking effect. After confirmation, policy and ownership checks precede Tool/MCP invocation. In the service transaction, first return the stored result for the same `(tenant_id, operation_id)` and payload; a changed payload conflicts. Lock the slot, verify active status and remaining capacity, insert appointment, increment booked count, and commit the operation result atomically. A contested/expired slot produces no success. After timeout or crash, lookup by operation ID before retry. Display appointment ID only after a known result.

### Appointment changes (v1.1)

Each reschedule or cancel requires owner/scoped-staff authorization, hospital-configured change rule, separate explicit confirmation and new operation ID. Reschedule locks appointment and both slots in stable key order, validates destination capacity, updates counts/state and stores the result in one service transaction. Cancel locks appointment/current slot, marks cancellation, decrements capacity once, and stores its result. Replays return the stored result; uncertain outcomes reconcile by operation ID. Every change is audited.

### Patient service queue (v1.1)

The hospital service queue is separate from the platform work queue. `queue_services` stores tenant, service, business timezone, queue scope, required fields, open/closed state and counter rules. `queue_counters` has one row per `(tenant_id, service_id, business_date, queue_scope)`; `queue_registrations` stores owner, operation ID, number and status; `queue_status_events` is append-only. Unique `(tenant_id, service_id, business_date, queue_scope, number)` and `(tenant_id, operation_id)` constraints enforce numbering and effect deduplication. Initial status is `WAITING`; authorized staff may move through `CALLED`, `SERVING`, `COMPLETED`, or `CANCELLED`. Cancelled numbers are not reused.

After collecting required fields and explicit confirmation, the service computes business date in its configured timezone using transaction time. In one transaction it returns an existing same-operation result, locks open service and counter, allocates the next number, inserts registration and status event, increments counter, and commits. A closed/failing service issues no number. Lookup by operation ID precedes retry after timeout. Patient reads require ownership; serving number, assigned counter and status come from backend state. Optional wait estimates are labeled approximate.

## Verification

Test current/stale/missing content, procedure resume after publication of a new version, unknown routes, warning suite and staff-offline fallback, booking slot contention, duplicate operation IDs, crash after remote success, queue concurrent allocation, closed service and cross-patient reads. All test fixtures are synthetic and versioned.
