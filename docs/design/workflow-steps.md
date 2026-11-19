# Workflow step types

- **Status:** design contract; Stage 0 registry supports `RULE` and `FINAL`, while the other types are planned
- **Scope:** meaning and declared contracts of published workflow steps
- **Related:** [Workflow Orchestration](workflow-orchestration.md), [Agent Runtime](agent-runtime.md), [System Contract](system-contract.md)

## Step, attempt, and execution state

A **step** is a node in an immutable, published workflow graph. Its stable `step_id` identifies the node, and its type says what the node does. An **attempt** is one try to execute that step; a retry gets a new attempt ID and number. An **execution** is one run of the published graph. Its state (`PENDING`, `RUNNING`, `WAITING_INPUT`, and so on) describes the run's progress, not a kind of step. The authoritative state transitions are in [Agent Runtime](agent-runtime.md#state-machine).

For example, a `WAIT_INPUT` step creates a question while the execution is `RUNNING`. After the waiting request is committed, the execution is `WAITING_INPUT` and no worker remains occupied. A valid answer moves the execution back to `RUNNING` and selects the step's declared successor. A single `RUNNING` state can likewise cover several consecutive steps. A retry can move an execution through `RUNNING → RETRY_SCHEDULED → RUNNING` while still targeting the same step.

## Common published contract

Each published step declares a stable `step_id`, type, input and output schema versions, allowed successors, timeout, and attempt budget. Types with additional choices declare named branches and the schema for the choice. Tool and policy requirements are declared where applicable. Publication validates referenced steps, branch completeness, compatible contracts, and bounded paths. A run pins the exact published snapshot; editing a workflow requires a new agent version.

The published definition describes **allowed behavior**. A handler returns a typed `StepDecision` selecting a state and, when appropriate, a declared successor. Runtime checks that decision against the pinned graph and current execution state before committing it. A handler cannot create a new graph edge at runtime. The Stage 0 registry currently stores only schema-version labels; concrete input/decision schemas and their compatibility checks are Stage 1 work for waiting steps.

| Type | Purpose and input | Result and allowed continuation | Delivery stage |
|---|---|---|---|
| `RULE` | Evaluate a deterministic rule over validated, referenced input. | Select one declared successor. Demo handlers have no external effect. | Registered in Stage 0; durable handler in Stage 1 |
| `WAIT_INPUT` | Ask the execution owner for an answer matching a declared answer schema. | Commit a pending request and `WAITING_INPUT`; on a valid, authorized answer, resume through a declared successor. Invalid answers do not advance the execution. | Stage 1 |
| `WAIT_APPROVAL` | Request an authorized staff decision with a declared action/scope and decision schema. | Commit a pending request and `WAITING_APPROVAL`; approval and rejection each follow their declared branch. | Stage 1 |
| `FINAL` | Produce a validated final result from available references. | Commit `COMPLETED`; no successor. A failure follows the runtime failure contract, not a hidden graph edge. | Registered in Stage 0; durable handler in Stage 1 |
| `LLM` | Generate structured output using pinned model and prompt versions. | Validate the output and select a declared successor; model output cannot authorize an action. | Later MVP stage |
| `RAG` | Retrieve approved, versioned evidence for a request. | Return evidence references or a declared no-evidence outcome, then follow an allowed successor. | Later MVP stage |
| `TOOL` | Invoke a declared, policy-authorized tool contract. | Return a validated result or follow the effect/reconciliation protocol before a declared successor. | Later MVP stage |

These rows define the meaning of each type, not a claim that every type is implemented. See the [Stage 1 checklist](../implementation/checklist/v1.0-1-durable-execution.md) for the waiting-step implementation and [Tool/MCP](tool-mcp.md) for external effects.

## Waiting branches: concrete example

An administrative guidance workflow might publish these edges:

```text
start (RULE) → ask_department (WAIT_INPUT) → give_directions (FINAL)
start (RULE) → request_review (WAIT_APPROVAL)
request_review --approved→ approved_result (FINAL)
request_review --rejected→ rejected_result (FINAL)
```

The `WAIT_INPUT` step declares what an acceptable department answer looks like; the API rejects an invalid answer without moving the execution. The `WAIT_APPROVAL` step declares both decision values and both successors at publication. Its rejection branch is part of the pinned graph, so a later publication cannot change where an already waiting execution goes. This is an illustrative workflow, not a claim that the demo handlers or endpoints already exist.

Publication must reject a missing successor, an incomplete decision branch, an incompatible input/output contract, an unreachable step, or an unbounded loop. For the Stage 1 demo, rejecting graph cycles entirely is sufficient. Retries are bounded execution attempts and are not graph edges.
