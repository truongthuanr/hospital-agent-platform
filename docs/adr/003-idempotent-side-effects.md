# ADR-003: Reconcile side effects by stable operation ID

- **Status:** Accepted (architecture baseline)
- **Decision date:** 2026-11-13
- **Decision authority:** Project requester
- **Target release:** MVP v1.0
- **Sources:** [HLD §§1, 4.1–4.2, 11, 13](../architecture.md); REL-002/003/005/006, TOOL-004/005, HOS-007

## Context

A worker may crash after a remote booking succeeds but before its result is checkpointed. At-least-once work delivery and a CAS conflict can also repeat a step. Neither a successful local commit nor a timeout proves whether the external effect happened.

## Decision

Assign one stable `operation_id` to each logical business action, distinct from execution and attempt IDs. Persist the operation ID, request identity, and invocation status before calling a side-effecting tool. The mock MCP service enforces uniqueness within `(tenant_id, operation_id)`, returns the same result on repeats, and supports lookup by operation ID. After a timeout or crash, look up the operation first. Record an existing result, retry with the same ID only when absence is proven and retry is safe, or enter `RECONCILIATION_REQUIRED` when the outcome cannot be established. A real tool without idempotency or reliable lookup must not be retried automatically after an uncertain outcome.

API request idempotency is separately scoped by `(tenant_id, operation_type, key)` and canonical payload hash: the same key and payload return the same logical result or `IN_PROGRESS`; a changed payload returns `409`.

## Alternatives considered

- **Claim exactly-once execution:** Cannot be guaranteed across PostgreSQL and an external service without a shared transaction.
- **Retry every timeout:** May duplicate a successful remote effect.
- **Never retry an uncertain effect:** Avoids duplicates, but leaves recoverable operations stuck even when the remote system can prove absence.

## Consequences and verification

Tool contracts must include idempotency and lookup capabilities; unresolved effects require an operator review path. Test duplicate API submissions, changed payload conflict, remote success followed by worker crash, and an unavailable lookup. Hash canonicalization, ID derivation, retention, and operator permissions belong in low-level design.
