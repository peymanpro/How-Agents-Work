from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .memory import WorkingMemory


@dataclass(frozen=True)
class AgentTask:
    customer_id: str
    order_id: str
    request: str = "Investigate the shipment and decide whether it needs escalation."

    @property
    def description(self) -> str:
        return f"{self.request} (customer={self.customer_id}, order={self.order_id})"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    read_only: bool
    arguments: tuple[str, ...] = ()


@dataclass(frozen=True)
class Observation:
    source: str
    success: bool
    values: Mapping[str, str] = field(default_factory=dict)
    error: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class Decision:
    action: str
    tool_name: str | None = None
    arguments: Mapping[str, str] = field(default_factory=dict)
    reason: str = ""
    message: str | None = None


@dataclass(frozen=True)
class ModelContext:
    """The structured context a model/planner receives for one decision."""

    task: AgentTask
    step: int
    memory: Mapping[str, str]
    observations: tuple[Observation, ...]
    available_tools: tuple[ToolSpec, ...]
    constraints: Mapping[str, str]

    def latest(self, source: str) -> Observation | None:
        for observation in reversed(self.observations):
            if observation.source == source:
                return observation
        return None

    def has_tool(self, name: str) -> bool:
        return any(tool.name == name for tool in self.available_tools)


@dataclass(frozen=True)
class TraceEntry:
    step: int
    kind: str
    detail: str


@dataclass
class AgentState:
    task: AgentTask
    memory: WorkingMemory = field(default_factory=WorkingMemory)
    observations: list[Observation] = field(default_factory=list)
    tool_calls: list[tuple[str, tuple[tuple[str, str], ...]]] = field(default_factory=list)

    def add_observation(self, observation: Observation) -> None:
        self.observations.append(observation)
        if observation.success:
            self.memory.remember(observation.values)

    def latest(self, source: str) -> Observation | None:
        for observation in reversed(self.observations):
            if observation.source == source:
                return observation
        return None

    def has_called(self, tool_name: str, arguments: Mapping[str, str]) -> bool:
        normalized = tuple(sorted(arguments.items()))
        return (tool_name, normalized) in self.tool_calls

    def remember_call(self, tool_name: str, arguments: Mapping[str, str]) -> None:
        self.tool_calls.append((tool_name, tuple(sorted(arguments.items()))))

    def build_context(
        self,
        *,
        step: int,
        available_tools: tuple[ToolSpec, ...],
        constraints: Mapping[str, str],
    ) -> ModelContext:
        return ModelContext(
            task=self.task,
            step=step,
            memory=self.memory.snapshot(),
            observations=tuple(self.observations),
            available_tools=available_tools,
            constraints=dict(constraints),
        )


@dataclass(frozen=True)
class AgentResult:
    success: bool
    message: str
    trace: tuple[TraceEntry, ...]
    memory: Mapping[str, str]
    observations: tuple[Observation, ...]
