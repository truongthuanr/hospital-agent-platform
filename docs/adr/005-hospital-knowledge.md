# ADR-005: Ground hospital guidance in approved, versioned sources

- **Status:** Accepted (architecture baseline)
- **Decision date:** 2026-11-13
- **Decision authority:** Project requester
- **Target release:** MVP v1.0; tenant-filtered retrieval in v1.1
- **Sources:** [HLD §§5.1, 6, 11, 13](../architecture.md); AI-005/006, HOS-003/013–018

## Context

Opening hours, fees, insurance procedures, documents, rooms, and routes change over time. A plausible answer without a current approved source can misdirect a patient. A procedure may span several turns and must not change mid-execution when the hospital publishes an update.

## Decision

The hospital application owns approved, versioned information, procedure, and location data. Retrieval may supply evidence, but generated answers must cite a validated source ID and version; time-sensitive facts use effective or last-updated dates. If evidence is missing, stale, irrelevant, or cannot support the answer, disclose uncertainty or hand off. Procedure progress pins its approved version for the execution. Navigation uses configured valid links and waypoints only. PostgreSQL/pgvector is the knowledge store; v1.1 filters retrieval by the active tenant before returning chunks or citations.

## Alternatives considered

- **Let the model answer from general knowledge:** Cannot prove local operational facts or their validity dates.
- **Store all guidance in prompts:** Makes updates and provenance difficult to review and pin.
- **Use retrieval without source validation:** A retrieved passage or model citation may be stale, unapproved, or fabricated.

## Consequences and verification

Hospital content needs an approval and publication process. Test supported, stale, missing, and conflicting sources; invented citations; procedure resume after content updates; and unknown routes. Exact retrieval thresholds, stale-date rules, citation schema, and content ownership belong in low-level design.
