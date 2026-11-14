# Platform v2.0 Implementation Checklist — Hospital Agent Platform

Start after the [Reliability v1.1 release gate](implementation-checklist-v1.1.md) passes. The [requirements](../requirement.md) define v2.0 outcomes, but the current [LLD](../low-level-design.md) details v1.0 and v1.1 only. Treat the design tasks below as prerequisites: settle and review each contract before implementing its feature. Check an item only with implementation and verification evidence. Preserve the safety, authorization, durability, and tenant-isolation guarantees from earlier releases.

## 1. Design and portability gate

- [ ] Define v2.0 module contracts and ADRs for multi-agent handoff, scheduling fairness, model routing, advanced retrieval, long-term memory, saga/compensation, sandboxing, and tenant lifecycle changes.
- [ ] Define migration, compatibility, and rollback plans for new persisted state and published config versions; verify that in-flight v1.0/v1.1 executions retain their pinned contracts.
- [ ] Add a second domain agent without changing platform runtime core; demonstrate its workflow, policy, tools, and tests through the existing extension points.

## 2. Workflow and platform scale

- [ ] **[Runtime + Orchestration]** Add multi-agent supervisor/handoff contracts that preserve trace IDs, tenant scope, authorization, and explicitly shared context.
- [ ] **[Orchestration]** Add priority and fair scheduling; expedite designated handoffs without starving ordinary work.
- [ ] **[Orchestration + Tool/MCP]** Model multi-step external actions with saga/compensation rules; record non-compensable steps and route unresolved outcomes to human review.
- [ ] **[Platform Operations]** Add tenant lifecycle extensions and load-aware capacity planning tied to measured queue age, latency, and quotas.
- [ ] **Verification milestone:** Multi-agent and scheduling scenarios preserve isolation and progress; partial external failure compensates only when safe or creates an inspectable escalation.

## 3. AI, retrieval, and memory

- [ ] **[RAG]** Compare hybrid retrieval/reranking with the v1.1 baseline using versioned recall@k, MRR, citation-validity, and answer-support results before selecting a configuration.
- [ ] **[LLM Gateway]** Add provider routing/fallback with explicit data-policy, tenant, timeout, and budget constraints; a fallback cannot bypass policy or change pinned execution semantics.
- [ ] **[Memory]** Add long-term memory with scoped access, provenance, TTL, and verifiable deletion; keep it separate from execution checkpoints and authoritative hospital facts.
- [ ] **[Orchestration + Tool/MCP]** If optional ReAct/planning is enabled, enforce bounded steps, tool calls, and budgets; run the same policy checks on every proposed action.
- [ ] **[Evaluation]** Compare prompt/model versions on quality, latency, cost, and failure rates; test malicious retrieved content and confirm tool policy still holds.

## 4. Security, deployment, and observability

- [ ] **[Tool/MCP]** Sandbox untrusted tool operations with enforced resource, time, and network limits.
- [ ] **[Platform Operations]** Enforce and test configured retention, deletion, and access-audit rules; document configurable external egress and private/on-prem deployment constraints.
- [ ] **[Platform Operations]** Define a service SLO from a stable measured baseline and tie alert thresholds to error and latency budgets.
- [ ] **Verification milestone:** Sandboxed operations cannot exceed declared permissions; deletion is verifiable; private-deployment dependencies and measured SLO assumptions are documented.

## 5. Optional hospital experience and release gate

- [ ] **[Hospital Domain]** Add voice input with confirmation of uncertain transcripts before effects; preserve the text path.
- [ ] **[Hospital Domain]** Add interactive floor maps and multilingual/spoken responses that match approved location and content versions and preserve safety behavior.
- [ ] **[Hospital Domain + Tool/MCP]** Validate a sandbox scheduling connector using synthetic records, including authorization, stable operation IDs, reconciliation, and data-policy checks; perform no real patient transaction.
- [ ] **[Release]** Demonstrate the second agent without runtime-core changes, safe multi-agent handoff, fairness, enhanced retrieval/model governance, and applicable saga, sandbox, and deployment constraints. Re-run v1.0/v1.1 safety and isolation gates.
