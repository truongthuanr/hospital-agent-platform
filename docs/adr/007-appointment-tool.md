# ADR-007: Perform appointment effects through an authorized domain tool

- **Status:** Accepted (architecture baseline)
- **Decision date:** 2026-11-13
- **Decision authority:** Project requester
- **Target release:** MVP v1.0; appointment changes in v1.1
- **Sources:** [HLD §§4.2, 5.2, 7.1, 11, 13](../architecture.md); HOS-005/006/007/023, TOOL-001–006

## Context

A displayed slot is only availability. It may expire or be taken before the patient confirms. Duplicate confirmations, retries, and worker crashes may repeat a booking request. The platform core should not own appointment domain state.

## Decision

Keep slot and appointment state in the mock hospital scheduling service. After the execution durably enters `WAITING_INPUT`, require explicit patient confirmation. The Tool Manager checks tenant, ownership, allowlist, policy, approval if required, and argument schema before calling the domain tool. The mock service enforces slot capacity atomically and deduplicates by `(tenant_id, operation_id)`; it supports lookup by operation ID under [ADR-003](003-idempotent-side-effects.md). A contested or expired slot returns a failure without a booking success message.

In v1.1, each reschedule or cancellation is a separate confirmed, audited action with its own operation ID and hospital-configured change rules.

## Alternatives considered

- **Put appointment tables in platform core:** Couples the reusable runtime to hospital-specific models.
- **Treat availability as a reservation:** Misstates the backend guarantee and risks false success.
- **Book directly from model output:** Bypasses patient confirmation and server-side policy.

## Consequences and verification

The mock service must provide atomic capacity checks and operation lookup. Test slot contention, duplicate confirmation, policy denial, and crash after remote success. Exact tool schemas, capacity transaction, ownership lookup, and change rules belong in low-level design.
