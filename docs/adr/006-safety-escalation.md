# ADR-006: Escalate warning indicators before routine hospital actions

- **Status:** Accepted (architecture baseline)
- **Decision date:** 2026-11-13
- **Decision authority:** Project requester
- **Target release:** MVP v1.0
- **Sources:** [HLD §§1, 5, 8, 11, 13](../architecture.md); HOS-004/008, SEC-003/004/007

## Context

The reference agent provides administrative guidance with synthetic data. A patient request may contain a configured warning indicator or ambiguous symptom description. Continuing a routine booking flow in that case would exceed the application's intended scope. A model classification alone is not a reliable authorization or clinical decision.

## Decision

Run a fixed, versioned warning-indicator screen before routine hospital actions. A positive result or unresolved warning-related uncertainty stops autonomous booking, persists a staff-visible handoff routed by configured policy, and presents approved fallback guidance. If staff are unavailable, the case remains pending and the fallback is shown. Medical staff retain all clinical decisions; the agent neither diagnoses nor performs autonomous emergency triage. Policy checks remain server-side and independent of model prompts.

## Alternatives considered

- **Let the LLM decide whether to escalate:** Hard to reproduce and cannot serve as the safety gate.
- **Continue routine booking while notifying staff:** Allows a side effect before the warning is reviewed.
- **Attempt automated triage:** Outside the administrative and synthetic-data scope.

## Consequences and verification

The warning suite and fallback need a qualified reviewer and versioned signoff. The MVP gate requires zero missed handoffs within that fixed suite and zero unauthorized effects; this does not establish clinical sensitivity. Test warning, ambiguous, staff-offline, and prompt-injection cases. Rule ownership, routing matrix, and signoff process belong in low-level design and the runbook.
