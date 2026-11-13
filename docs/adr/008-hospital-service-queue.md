# ADR-008: Keep patient service numbers in a separate hospital domain queue

- **Status:** Accepted (architecture baseline)
- **Decision date:** 2026-11-13
- **Decision authority:** Project requester
- **Target release:** Reliability v1.1
- **Sources:** [HLD §§5.3, 6, 11, 13](../architecture.md); TOOL-010, HOS-019–022/025

## Context

The platform work queue schedules worker jobs; a hospital service queue issues patient-facing numbers. They have different state, uniqueness, ownership, and access rules. Concurrent registrations can race for the same next number, and a timeout can hide a successful registration.

## Decision

Keep the hospital service queue in its own domain service/schema. Accept registration only for an open service after required fields and explicit confirmation. Allocate a number in one atomic transaction within `(tenant_id, service_id, business_date, queue_scope)`, with a uniqueness constraint and transactional counter or lock. Deduplicate registration by `(tenant_id, operation_id)` and provide lookup by operation ID for reconciliation. Patient status reads require ownership and return backend status, serving number, and assigned counter; estimated waits are labeled approximate. Closed or failing services produce no number and no success message.

## Alternatives considered

- **Reuse the platform work queue:** Worker-job ordering and patient service numbering have unrelated contracts and permissions.
- **Generate numbers in the agent or LLM:** Cannot guarantee uniqueness or match backend state under concurrency.
- **Retry registration without lookup:** May issue a second number after an uncertain outcome.

## Consequences and verification

The domain service owns allocation contention and status history. Test simultaneous registrations, repeated operation IDs, crash after allocation, closed service, and cross-patient reads. Queue scope, business-date boundary, statuses, counter locking, and optional notice policy belong in low-level design.
