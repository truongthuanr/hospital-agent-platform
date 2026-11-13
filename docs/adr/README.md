# Architecture decision records

These records form the architecture baseline derived from the [HLD](../architecture.md) and the [requirements](../requirement.md). The project requester authorized finalizing the recommendations on 2026-11-13. `Accepted` records establish design direction; implementation still requires the low-level design, tests, and release gates. Detailed schemas, queries, timeouts, thresholds, and operational values belong in the low-level design and runbook.

| Record | Scope | Target release | Status |
|---|---|---|---|
| [ADR-001](001-runtime-state-machine.md) | Runtime state machine | v1.0 | Accepted |
| [ADR-002](002-postgresql-work-delivery.md) | Durable work delivery | v1.0 | Accepted: direct PostgreSQL claims |
| [ADR-003](003-idempotent-side-effects.md) | Idempotent side effects and reconciliation | v1.0 | Accepted |
| [ADR-004](004-identity-authorization-tenancy.md) | Identity, authorization, tenancy | v1.0; v1.1 expansion | Accepted |
| [ADR-005](005-hospital-knowledge.md) | Approved hospital knowledge | v1.0 | Accepted |
| [ADR-006](006-safety-escalation.md) | Warning indicators and handoff | v1.0 | Accepted |
| [ADR-007](007-appointment-tool.md) | Appointment effects | v1.0; v1.1 changes | Accepted |
| [ADR-008](008-hospital-service-queue.md) | Hospital service queue | v1.1 | Accepted |
