# LLM gateway

- **Status:** detailed design baseline
- **Scope:** MVP v1.0 provider adapter and stub; usage and budgets in v1.1
- **ADRs:** [001](../adr/001-runtime-state-machine.md), [005](../adr/005-hospital-knowledge.md)

## Boundary

The gateway owns model-provider adapters, prompt assembly input contract, output schema validation, timeout/error normalization, and a deterministic test stub. It does not choose workflow state, authorize tools, retrieve cross-tenant documents, or persist execution checkpoints. Only an orchestration step declared `LLM` may call it. The caller supplies a pinned model/prompt version and already-scoped context.

## Internal contract

`generate(tenant_id, trace_id, execution_id, step_id, model_version, prompt_version, messages, output_schema, timeout_budget) -> LLMResult`. `LLMResult` contains schema-validated structured output, provider/model version, latency, usage if available, and a normalized error class. The gateway rejects unpinned or unsupported versions. It never interprets generated text as a policy decision, citation proof, tool authorization, or clinical certainty.

The gateway builds the request from immutable prompt version plus bounded conversation context supplied by [Memory](memory.md) and evidence supplied by [RAG](rag.md). Retrieved content is labeled as untrusted evidence. It is never placed in a system-policy position. The gateway strips secrets and unnecessary patient text from telemetry. The same prompt/model versions are used through an execution even if registry defaults change.

## Processing

1. Validate prompt, model, input messages, and output schema against pinned contracts.
2. Apply the 20 s MVP demo timeout from [Orchestration](workflow-orchestration.md). A provider timeout becomes a transient step error; a malformed output is not a tool command.
3. Parse the model response as structured output and validate it. Allow at most one bounded repair attempt. If still invalid, return a schema error; do not guess missing fields.
4. Return the typed result to orchestration. A deterministic rule validates allowed next steps and citations before runtime commits anything.

The deterministic stub accepts the same request and returns fixture outputs keyed by scenario. Infrastructure and fault tests use the stub so latency and correctness results are reproducible. A real-provider demo is configured separately and reports model/version, latency, tokens, and limitations.

## v1.1 and later

v1.1 records per-run token/cost estimates, context window budgets, and provider concurrency/RPM/TPM admission independently of worker capacity. A provider failure cannot block all worker slots indefinitely. Provider routing/fallback is v2.0 and must preserve data and policy constraints; it is not an MVP hidden fallback.

## Verification

Swap pinned model config without changing workflow code, reject malformed structured output after one repair, verify timeout classification, prevent LLM output from bypassing policy, and confirm the stub produces reproducible results. Trace data must omit raw patient content and credentials.
