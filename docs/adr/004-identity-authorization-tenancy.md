# ADR-004: Derive tenant identity and enforce RBAC plus ABAC centrally

- **Status:** Accepted (architecture baseline)
- **Decision date:** 2026-11-13
- **Decision authority:** Project requester
- **Target release:** MVP v1.0; full tenant boundary in v1.1
- **Sources:** [HLD §§6–7.1, 11, 13](../architecture.md); SEC-001/002/003/004, TEN-003/005/007/008

## Context

Patients, staff, operators, agents, and workers access different resources. A role alone does not prove ownership, tenant membership, approval scope, or a valid execution state. Client fields, queue payloads, and LLM output cannot grant authority. MVP uses one fixed synthetic tenant; v1.1 adds multiple tenants and revocable membership.

## Decision

Use a centralized default-deny policy decision function. Authenticate the actor and derive active tenant context on the server. RBAC limits which actions a role may attempt; ABAC then checks tenant, ownership or staff assignment, resource state, action, pinned policy/tool versions, and required approvals. Enforce the decision at API, worker, and Tool Manager boundaries, and audit decisions with redacted context. A foreign resource ID returns `404`; a known same-tenant resource with insufficient privilege returns `403`.

For MVP, bind each synthetic patient session to its executions and keep staff/operator authentication separate. In v1.1, recheck current membership on every request and reload execution and agent configuration before worker effects or commits. Tenant IDs in a path or job never establish authority by themselves.

## Alternatives considered

- **RBAC alone:** Cannot distinguish another patient's record or an invalid approval state.
- **Prompt-based or LLM authorization:** Model output is untrusted and cannot enforce a security boundary.
- **External general-purpose policy service for MVP:** Adds deployment complexity without a requirement for policy distribution at this scale.

## Consequences and verification

Policy rules and enforcement points must stay consistent across interfaces. Test patient ownership, staff-only decisions, foreign IDs, revoked membership, wrong-tenant jobs, and denied tool calls. Role definitions, attribute matrix, session binding, and v1.1 tenant indexes and foreign keys belong in low-level design.
