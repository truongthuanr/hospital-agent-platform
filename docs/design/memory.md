# Conversation memory

- **Status:** detailed design baseline
- **Scope:** short-term conversation context in MVP; long-term memory deferred to v2.0
- **ADRs:** [001](../adr/001-runtime-state-machine.md), [004](../adr/004-identity-authorization-tenancy.md)

## Boundary

Memory owns tenant-scoped conversation messages and the context window passed to an LLM step. It does not own workflow progress, checkpoints, events, audit, hospital knowledge, or authorization policy. Deleting or summarizing chat context cannot change an execution's step or pending input state.

## Data contract

`conversation_messages` has UUID PK, tenant ID, conversation ID, owner session ID, role, content or protected synthetic-fixture reference, created time, and optional summary version. Reads filter tenant and owner/staff scope before returning any text. Messages are ordered by creation time plus ID tie-break. Raw text is not copied into logs, events, or checkpoints. A checkpoint may hold a conversation reference, never the entire history.

`get_context(actor, tenant_id, conversation_id, max_tokens, pinned_summary_version?) -> ordered messages + provenance`. The caller supplies a budget; Memory returns bounded context and a truncation/summary marker. The LLM gateway receives this as untrusted user conversation content. A summary is a derived, replaceable cache with its own version and provenance; it is not an authoritative business fact or execution state.

## Write and lifecycle

Append a patient message only after session ownership is checked. The execution creation/input transaction records the message reference needed by the workflow; memory failure must not silently change a committed execution decision. For MVP, persist the message before enqueuing the dependent step or fail the request transaction. An assistant message is appended after its validated output is committed; duplicate step deliveries use a stable message/event reference to avoid duplicate visible replies.

v1.0 keeps short-term context only. v1.1 adds explicit context budget management and tenant isolation tests across independent hospitals. Long-term memory, TTL and deletion policy are v2.0. Before production data use, define per-data-type retention and deletion; demo fixtures contain synthetic data only.

## Verification

Clear or summarize conversation history and verify the execution checkpoint and procedure step are unchanged. Test duplicate worker delivery does not append two assistant replies, patient A cannot read patient B's conversation, and v1.1 tenant A never receives tenant B's text.
