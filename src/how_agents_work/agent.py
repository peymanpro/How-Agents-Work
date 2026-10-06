from __future__ import annotations

from collections.abc import Mapping

from .models import AgentResult, AgentState, AgentTask, Decision, TraceEntry
from .tools import ToolRegistry


class Agent:
    """Small, inspectable agent runtime.

    The planner acts like the model boundary. It receives a structured context,
    proposes a decision, and never executes tools directly. The runtime validates
    that proposal, executes the selected capability, records the observation, and
    builds a fresh context for the next decision.
    """

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
            context = state.build_context(
                step=step,
                available_tools=tuple(self._tools.specs()),
                constraints={
                    "side_effects": (
                        "allowed" if self._allow_side_effects else "blocked"
                    ),
                    "remaining_tool_calls": str(
                        max(0, self._max_tool_calls - len(state.tool_calls))
                    ),
                },
            )
            trace.append(
                TraceEntry(
                    step,
                    "context",
                    self._format_context(context),
                )
            )

            decision = self._planner.decide(context)
            if decision.raw_model_output is not None:
                trace.append(
                    TraceEntry(
                        step,
                        "model_response",
                        decision.raw_model_output,
                    )
                )

            trace.append(
                TraceEntry(
                    step,
                    "model_output",
                    self._format_decision(decision),
                )
            )

            if decision.action == "finish":
                message = decision.message or "done"
                trace.append(TraceEntry(step, "finish", message))
                return self._result(True, message, state, trace)

            if decision.action == "fail":
                message = decision.message or "failed"
                trace.append(TraceEntry(step, "fail", message))
                return self._result(False, message, state, trace)

            if decision.action != "tool":
                message = f"unknown planner action: {decision.action!r}"
                trace.append(TraceEntry(step, "validation", message))
                return self._result(False, message, state, trace)

            tool = self._tools.get(decision.tool_name or "")
            if tool is None:
                message = f"tool {decision.tool_name!r} is not registered"
                trace.append(TraceEntry(step, "validation", message))
                return self._result(False, message, state, trace)

            missing = sorted(set(tool.arguments) - set(decision.arguments))
            unexpected = sorted(set(decision.arguments) - set(tool.arguments))
            if missing or unexpected:
                message = (
                    f"invalid arguments for {tool.name!r}; "
                    f"missing={missing or []}, unexpected={unexpected or []}"
                )
                trace.append(TraceEntry(step, "validation", message))
                return self._result(False, message, state, trace)

            if not self._allow_side_effects and not tool.read_only:
                message = f"side effects are disabled; refusing to call {tool.name!r}"
                trace.append(TraceEntry(step, "guardrail", message))
                return self._result(False, message, state, trace)

            if len(state.tool_calls) >= self._max_tool_calls:
                message = f"tool-call budget of {self._max_tool_calls} was exhausted"
                trace.append(TraceEntry(step, "guardrail", message))
                return self._result(False, message, state, trace)

            if state.has_called(tool.name, decision.arguments):
                message = f"repeated tool call detected: {tool.name!r}"
                trace.append(TraceEntry(step, "guardrail", message))
                return self._result(False, message, state, trace)

            arguments = self._format_arguments(decision.arguments)
            trace.append(
                TraceEntry(
                    step,
                    "tool_call",
                    f"{tool.name}({arguments})",
                )
            )
            state.remember_call(tool.name, decision.arguments)

            observation = self._tools.run(tool.name, decision.arguments)
            state.add_observation(observation)
            trace.append(
                TraceEntry(
                    step,
                    "observation",
                    self._format_observation(observation),
                )
            )

        message = f"stopped after {self._max_steps} steps to prevent an infinite loop"
        trace.append(TraceEntry(self._max_steps, "guardrail", message))
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

    @staticmethod
    def _format_decision(decision: Decision) -> str:
        confidence = (
            f", confidence={decision.confidence:.2f}"
            if decision.confidence is not None
            else ""
        )
        if decision.action != "tool":
            return f"{decision.action}: {decision.message or decision.reason}{confidence}"
        return (
            f"tool_call={decision.tool_name}("
            f"{Agent._format_arguments(decision.arguments)}){confidence}"
        )

    @staticmethod
    def _format_context(context) -> str:
        tools = ", ".join(tool.name for tool in context.available_tools)
        memory = ", ".join(
            f"{key}={value}" for key, value in context.memory.items()
        ) or "empty"
        observations = ", ".join(
            f"{item.source}:{'ok' if item.success else 'error'}"
            for item in context.observations
        ) or "none"
        return (
            f"goal={context.task.description}; "
            f"memory={memory}; "
            f"observations={observations}; "
            f"tools=[{tools}]; "
            f"constraints={dict(context.constraints)}"
        )
