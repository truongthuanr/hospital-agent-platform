from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StepType(StrEnum):
    RULE = "RULE"
    FINAL = "FINAL"


class StepDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str = Field(min_length=1, max_length=100)
    type: StepType
    input_schema_version: str = "1"
    output_schema_version: str = "1"
    successors: tuple[str, ...] = ()
    timeout_seconds: int = Field(default=20, ge=1, le=300)
    max_attempts: int = Field(default=3, ge=1, le=10)


class VersionReferences(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow: str
    policy: str = "foundation-v1"
    prompt: str | None = None
    model: str | None = None
    tool_contract: str | None = None
    hospital_config: str | None = None


class PublishedAgent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1"
    agent_id: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=64)
    start_step: str
    steps: tuple[StepDefinition, ...]
    refs: VersionReferences

    @model_validator(mode="after")
    def valid_graph(self) -> "PublishedAgent":
        if self.schema_version != "1":
            raise ValueError("Unsupported agent schema version")
        if self.refs.workflow != self.version or self.refs.policy != "foundation-v1":
            raise ValueError("Invalid version references")
        by_id = {step.step_id: step for step in self.steps}
        if len(by_id) != len(self.steps) or self.start_step not in by_id:
            raise ValueError("Duplicate step IDs or missing start step")
        for step in self.steps:
            if step.type == StepType.FINAL and step.successors:
                raise ValueError("FINAL cannot have successors")
            if step.type == StepType.RULE and not step.successors:
                raise ValueError("RULE requires a successor")
            if any(next_id not in by_id for next_id in step.successors):
                raise ValueError("Missing successor")
        visited: set[str] = set()
        active: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in active:
                raise ValueError("Unbounded workflow loop")
            if step_id in visited:
                return
            active.add(step_id)
            for successor in by_id[step_id].successors:
                visit(successor)
            active.remove(step_id)
            visited.add(step_id)

        visit(self.start_step)
        if len(visited) != len(by_id) or not any(by_id[x].type == StepType.FINAL for x in visited):
            raise ValueError("Unreachable steps or no FINAL step")
        return self

