from __future__ import annotations

from collections.abc import Mapping

from .models import AgentResult, AgentState, AgentTask, TraceEntry
from .planner import SupportPlanner
from .tools import ToolRegistry


class Agent:
    def __init__(
        self,
        planner: SupportPlanner,
        tools: ToolRegistry,
        max_steps: int = 8,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")

        self._planner = planner
        self._tools = tools
        self._max_steps = max_steps

    def run(self, task: AgentTask) -> AgentResult:
        state = AgentState(task)
        trace: list[TraceEntry] = []

        for step in range(1, self._max_steps + 1):
            decision = self._planner.decide(state)

            if decision.action == "tool":
                arguments = decision.arguments
                trace.append(
                    TraceEntry(
                        step,
                        "action",
                        f"{decision.tool_name}({self._format_arguments(arguments)})",
                    )
                )

                observation = self._tools.run(decision.tool_name or "", arguments)
                state.add(observation)

                trace.append(
                    TraceEntry(step, "observation", self._format_observation(observation))
                )
                continue

            if decision.action == "finish":
                trace.append(TraceEntry(step, "finish", decision.message or "done"))
                return AgentResult(
                    True,
                    decision.message or "done",
                    tuple(trace),
                    tuple(state.observations),
                )

            if decision.action == "fail":
                trace.append(TraceEntry(step, "fail", decision.message or "failed"))
                return AgentResult(
                    False,
                    decision.message or "failed",
                    tuple(trace),
                    tuple(state.observations),
                )

            raise ValueError(f"unknown planner action: {decision.action!r}")

        message = f"stopped after {self._max_steps} steps to prevent an infinite loop"
        trace.append(TraceEntry(self._max_steps, "fail", message))

        return AgentResult(
            False,
            message,
            tuple(trace),
            tuple(state.observations),
        )

    @staticmethod
    def _format_arguments(arguments: Mapping[str, str]) -> str:
        return ", ".join(f"{key}={value}" for key, value in arguments.items())

    @staticmethod
    def _format_observation(observation) -> str:
        if not observation.success:
            return f"{observation.source}: error={observation.error}"

        values = ", ".join(
            f"{key}={value}" for key, value in observation.values.items()
        )
        return f"{observation.source}: {values}"
