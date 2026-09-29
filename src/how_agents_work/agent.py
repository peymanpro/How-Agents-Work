from __future__ import annotations

from collections.abc import Mapping

from .models import AgentResult, AgentState, AgentTask, TraceEntry
from .tools import ToolRegistry


class Agent:
    def __init__(
        self,
        planner,
        tools: ToolRegistry,
        max_steps: int = 10,
        allow_side_effects: bool = True,
        max_tool_calls: int = 8,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        if max_tool_calls < 1:
            raise ValueError("max_tool_calls must be at least 1")

        self._planner = planner
        self._tools = tools
        self._max_steps = max_steps
        self._allow_side_effects = allow_side_effects
        self._max_tool_calls = max_tool_calls

    def run(self, task: AgentTask) -> AgentResult:
        state = AgentState(task)
        trace: list[TraceEntry] = []

        for step in range(1, self._max_steps + 1):
            decision = self._planner.decide(state)
            trace.append(TraceEntry(step, "decision", decision.reason))

            if decision.action == "finish":
                message = decision.message or "done"
                trace.append(TraceEntry(step, "finish", message))
                return self._result(True, message, state, trace)

            if decision.action == "fail":
                message = decision.message or "failed"
                trace.append(TraceEntry(step, "fail", message))
                return self._result(False, message, state, trace)

            if decision.action != "tool":
                raise ValueError(f"unknown planner action: {decision.action!r}")

            tool = self._tools.get(decision.tool_name or "")
            if tool is None:
                message = f"tool {decision.tool_name!r} is not registered"
                trace.append(TraceEntry(step, "fail", message))
                return self._result(False, message, state, trace)

            if not self._allow_side_effects and not tool.read_only:
                message = f"side effects are disabled; refusing to call {tool.name!r}"
                trace.append(TraceEntry(step, "guardrail", message))
                return self._result(False, message, state, trace)

            if len(state.tool_calls) >= self._max_tool_calls:
                message = f"tool-call budget of {self._max_tool_calls} was exhausted"
                trace.append(TraceEntry(step, "fail", message))
                return self._result(False, message, state, trace)

            if state.has_called(tool.name, decision.arguments):
                message = f"repeated tool call detected: {tool.name!r}"
                trace.append(TraceEntry(step, "fail", message))
                return self._result(False, message, state, trace)

            arguments = self._format_arguments(decision.arguments)
            trace.append(TraceEntry(step, "action", f"{tool.name}({arguments})"))
            state.remember_call(tool.name, decision.arguments)

            observation = self._tools.run(tool.name, decision.arguments)
            state.add_observation(observation)
            trace.append(
                TraceEntry(step, "observation", self._format_observation(observation))
            )

        message = f"stopped after {self._max_steps} steps to prevent an infinite loop"
        trace.append(TraceEntry(self._max_steps, "fail", message))
        return self._result(False, message, state, trace)

    @staticmethod
    def _result(
        success: bool,
        message: str,
        state: AgentState,
        trace: list[TraceEntry],
    ) -> AgentResult:
        return AgentResult(
            success,
            message,
            tuple(trace),
            state.memory.snapshot(),
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
