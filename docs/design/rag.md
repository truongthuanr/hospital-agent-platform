# Retrieval and grounded answers (RAG)

- **Status:** detailed design baseline
- **Scope:** approved hospital information in MVP; tenant filtering and measurement in v1.1
- **ADR:** [005](../adr/005-hospital-knowledge.md)

## Boundary

RAG owns document ingestion, approval/version metadata, chunking/embedding, retrieval, and citation validation. It supplies evidence to the LLM gateway and answer renderer. It does not authorize tools, modify execution state, or treat retrieved text as instructions. Hospital domain owns the meaning and approval of operational facts; RAG owns their retrieval representation.

## Data contract

`knowledge_documents` has `(tenant_id, document_id, version)` identity, source ID, approval state and approver, effective-from/until, last-updated time, content hash, and publication time. Published versions are immutable. `knowledge_chunks` references that exact document version and stores chunk ID, text, embedding, source offsets, and metadata. A citation is `(document_id, version, chunk_id, source_id, effective_at)`; the renderer checks this tuple against an approved current document and verifies the cited chunk was in the retrieved evidence set.

`retrieve(tenant_id, query, pinned_corpus_version, as_of_time, top_k) -> evidence[]` filters tenant, approval, pinned corpus, and effective date **before** returning chunks. PostgreSQL/pgvector is the store. `min_similarity` and `top_k` are versioned configuration chosen from a labeled evaluation set. If the threshold is absent/unvalidated, the retrieval workflow abstains; an LLM score is not a substitute. A missing, stale, irrelevant, or conflicting source produces uncertainty disclosure or handoff, not a fabricated answer.

## Ingestion and answer flow

1. Hospital content owner supplies synthetic source, version, effective dates, and approval. Ingestion validates metadata and chunks/embeds the exact published version.
2. Retrieval applies server-derived tenant and pinned corpus filters. It returns evidence with provenance and similarity metadata, never arbitrary tool permissions.
3. The LLM gateway receives evidence marked as untrusted data and produces structured answer plus citation candidates.
4. The answer renderer checks each citation against retrieved approved chunks and ensures requested facts are supported. It rejects fabricated IDs, stale versions, and unsupported fees, insurance benefits, rooms, routes, hours, or availability.
5. If validation fails, return an approved abstention/fallback and optionally create a hospital handoff.

Procedures and navigation use structured approved hospital records rather than free-form vector similarity for step ordering or route construction. Their versions are pinned in the execution. v1.1 adds two-tenant negative tests and retrieval metrics; v2.0 may add hybrid retrieval/reranking after measured comparison.

## Verification

Use versioned current/stale/missing/conflicting fixtures, fabricated citation attempts, malicious retrieved instructions, and two-tenant retrieval tests. Report recall and answer-support metrics with dataset/agent versions, sample size, and limitations. Passing the fixed demo set is not a claim of clinical reliability.
