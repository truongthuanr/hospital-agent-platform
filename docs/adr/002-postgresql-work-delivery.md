# ADR-002: Keep PostgreSQL authoritative for work delivery

- **Status:** Accepted (architecture baseline)
- **Decision date:** 2026-11-13
- **Decision authority:** Project requester
- **Target release:** MVP v1.0; leases and fencing in v1.1
- **Sources:** [HLD §§3, 4.1, 9, 11, 13](../architecture.md); REL-001/003/007/008/009, PLT-011

## Context

An API response of `202 Accepted` promises that the execution and its work intent survive a process restart. Delayed retries must not run before their persisted due time. Dispatch and worker processing can be repeated, so a transport acknowledgment cannot be the source of truth for execution progress.

## Decision

Commit execution state, checkpoint, event, and durable work intent together in PostgreSQL. For MVP, workers claim due work-intent rows directly from PostgreSQL; no separate broker or dispatcher is required for internal jobs. PostgreSQL owns due times and pending work. A claimed job is complete only after its execution transition and successor work intent are committed. Claims and transitions remain at least once: consumers verify job identity, execution state/version, attempt, and tenant before work. In v1.1, multiple workers add leases, heartbeats, and fencing tokens before committing transitions.

For MVP, the durable job row serves as the transactionally committed outbox work intent; a separate publication record is unnecessary. If a separate transport is introduced later, its dispatcher publishes from a durable outbox record and marks publication independently; PostgreSQL remains authoritative. The transport change requires a new ADR or amendment to this one.

## Alternatives considered

- **Redis or another broker as the sole queue:** Reduces database polling, but cannot alone make execution state and work admission atomic.
- **Dispatcher plus broker:** Allows separate delivery scaling, but adds publish/mark races and another operational dependency for the MVP.
- **Direct PostgreSQL claim (chosen):** Fewer components while retaining durable admission; requires careful locking and polling under load.

## Consequences and verification

Duplicate processing remains possible after a crash; state/version and job checks must make it harmless. Test crash after commit but before claim, crash after claim, duplicate claim attempts, restart with a delayed retry, and v1.1 stale-worker fencing. Job schema, claim query, polling interval, and claim/complete transaction order belong in low-level design.
