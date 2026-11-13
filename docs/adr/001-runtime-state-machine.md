# ADR-001: Use a deterministic workflow state machine

- **Status:** Accepted (architecture baseline)
- **Decision date:** 2026-11-13
- **Decision authority:** Project requester
- **Target release:** MVP v1.0
- **Sources:** [HLD §§1, 4, 11, 13](../architecture.md); PLT-002/004/005/006/009/011, REL-001/004

## Context

The platform must resume acknowledged executions after restart, pause for patient input or staff approval without holding a worker, and keep one immutable set of workflow, prompt, model, policy, and tool-contract versions throughout a run. Concurrent workers or repeated input may race to change the same execution. Hospital workflows need explicit policy boundaries, so runtime progression cannot depend on an LLM-generated next state.

## Decision

Implement a small platform-owned state machine with declared step types and allowed transitions. Persist each checkpoint, event, step attempt, and next work intent in the same PostgreSQL transaction as a version-checked execution transition. Return a waiting state only after its checkpoint and input or approval token are committed. A worker releases its slot while waiting. On a CAS conflict, reload state and discard the stale decision; a tool effect is handled under [ADR-003](003-idempotent-side-effects.md). A LangGraph adapter may be added later without becoming the authoritative state store.

## Alternatives considered

- **LangGraph as the runtime:** Offers orchestration features, but its state and retry semantics would need to be reconciled with this platform's transaction, version pinning, and policy contracts.
- **In-memory workflow state:** Simple for a demo, but cannot satisfy durable acknowledgment and restart recovery.

## Consequences and verification

The platform owns transition validation, checkpoint migrations, and more fault tests. Invalid transitions must fail; restart while waiting must resume the same step and pinned versions; two competing transitions must yield one committed version. The full transition table and checkpoint schema are low-level design work.
