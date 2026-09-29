from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class AgentTask:
    customer_id: str
    order_id: str

    @property
    def description(self) -> str:
        return (
            f"check order {self.order_id} for customer {self.customer_id} "
            "and decide whether the shipment needs escalation"
        )


@dataclass(frozen=True)
class Observation:
    source: str
    success: bool
    values: Mapping[str, str] = field(default_factory=dict)
    error: str | None = None


@dataclass
class AgentState:
    task: AgentTask
    observations: list[Observation] = field(default_factory=list)

    def add(self, observation: Observation) -> None:
        self.observations.append(observation)

    def latest(self, source: str) -> Observation | None:
        for observation in reversed(self.observations):
            if observation.source == source:
                return observation
        return None


@dataclass(frozen=True)
class Decision:
    action: str
    tool_name: str | None = None
    arguments: Mapping[str, str] = field(default_factory=dict)
    message: str | None = None


@dataclass(frozen=True)
class TraceEntry:
    step: int
    kind: str
    detail: str


@dataclass(frozen=True)
class AgentResult:
    success: bool
    message: str
    trace: tuple[TraceEntry, ...]
    memory: tuple[Observation, ...]
