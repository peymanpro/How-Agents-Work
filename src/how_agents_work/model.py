from __future__ import annotations

import json
import math
import random
import re
from collections.abc import Callable, Mapping
from typing import Protocol

from .models import Decision, ModelContext, ToolSpec


class Model(Protocol):
    """Minimal model boundary used by the planner adapter."""

    def generate(self, context: ModelContext) -> str:
        """Return a model-like text response for the supplied context."""
        ...


class MockLLM:
    """Deterministic simulator for an LLM response boundary."""

    def __init__(
        self,
        decision_provider: Callable[[ModelContext], Decision],
        *,
        response_overrides: Mapping[int, str] | None = None,
    ) -> None:
        self._decision_provider = decision_provider
        self._response_overrides = dict(response_overrides or {})

    def generate(self, context: ModelContext) -> str:
        override = self._response_overrides.get(context.step)
        if override is not None:
            return override

        decision = self._decision_provider(context)
        payload: dict[str, object] = {
            "action": decision.action,
            "reason": decision.reason,
        }

        if decision.action == "tool":
            payload["tool_name"] = decision.tool_name
            payload["arguments"] = dict(decision.arguments)

        if decision.message is not None:
            payload["message"] = decision.message

        if decision.confidence is not None:
            payload["confidence"] = decision.confidence

        return json.dumps(payload, sort_keys=True)


class OpenEndedMockLLM:
    """Probabilistic, domain-agnostic simulation of model-style tool selection.

    Unlike SupportPlanner, this model does not encode shipment-specific rules.
    It scores available tools from the current task, observations, memory, and
    tool descriptions, then samples a plausible action. This demonstrates open
    and uncertain decision-making while remaining fully local and inspectable.

    It is still only a simulation: lexical relevance and generic state heuristics
    are not equivalent to semantic understanding by a trained neural model.
    """

    def __init__(
        self,
        *,
        temperature: float = 0.8,
        seed: int | None = None,
        finish_bias: float = -1.2,
    ) -> None:
        if temperature <= 0:
            raise ValueError("temperature must be greater than 0")

        self._temperature = temperature
        self._rng = random.Random(seed)
        self._finish_bias = finish_bias

    def generate(self, context: ModelContext) -> str:
        candidates = self._candidate_decisions(context)

        if not candidates:
            decision = Decision(
                "finish",
                reason="No executable capability is available from the current context.",
                message="unable to identify a next action from the available context",
                confidence=0.2,
            )
        else:
            probabilities = _softmax(
                [score for score, _ in candidates],
                self._temperature,
            )
            index = self._sample(probabilities)
            selected = candidates[index][1]
            decision = Decision(
                action=selected.action,
                tool_name=selected.tool_name,
                arguments=selected.arguments,
                reason=selected.reason,
                message=selected.message,
                confidence=probabilities[index],
            )

        payload: dict[str, object] = {
            "action": decision.action,
            "reason": decision.reason,
            "confidence": decision.confidence,
        }

        if decision.action == "tool":
            payload["tool_name"] = decision.tool_name
            payload["arguments"] = dict(decision.arguments)

        if decision.message is not None:
            payload["message"] = decision.message

        return json.dumps(payload, sort_keys=True)

    def _candidate_decisions(
        self,
        context: ModelContext,
    ) -> list[tuple[float, Decision]]:
        candidates: list[tuple[float, Decision]] = []
        context_terms = _context_terms(context)
        observations_count = len(context.observations)

        for spec in context.available_tools:
            if (
                context.constraints.get("side_effects") == "blocked"
                and not spec.read_only
            ):
                continue

            arguments = {}
            for name in spec.arguments:
                value = _resolve_argument(name, context)
                if value is None:
                    break
                arguments[name] = value
            else:
                candidates.append(
                    (
                        self._tool_score(
                            spec,
                            context_terms=context_terms,
                            context=context,
                            observations_count=observations_count,
                        ),
                        Decision(
                            "tool",
                            spec.name,
                            arguments,
                            reason=(
                                "This capability appears relevant to the current "
                                "goal and available evidence."
                            ),
                        ),
                    )
                )

        if observations_count:
            candidates.append(
                (
                    self._finish_bias + min(observations_count, 3) * 0.25,
                    Decision(
                        "finish",
                        reason=(
                            "The model is uncertain whether another action is "
                            "worth the remaining execution budget."
                        ),
                        message="best-effort completion based on current evidence",
                    ),
                )
            )

        return candidates

    @staticmethod
    def _tool_score(
        spec: ToolSpec,
        *,
        context_terms: set[str],
        context: ModelContext,
        observations_count: int,
    ) -> float:
        tool_terms = _terms(
            f"{spec.name} {spec.description} {' '.join(spec.arguments)}"
        )
        overlap = len(context_terms & tool_terms)
        score = 0.35 * overlap

        if spec.read_only:
            score += 0.5
        elif observations_count < 2:
            score -= 1.0

        if any(
            observation.source == spec.name and observation.success
            for observation in context.observations[-3:]
        ):
            score -= 0.8

        if context.step > 1:
            score += 0.05 * min(observations_count, 5)

        return score

    def _sample(self, probabilities: list[float]) -> int:
        value = self._rng.random()
        cumulative = 0.0
        for index, probability in enumerate(probabilities):
            cumulative += probability
            if value <= cumulative:
                return index
        return len(probabilities) - 1


class ModelOutputParser:
    """Convert model text into the runtime's structured decision object."""

    @staticmethod
    def parse(raw_output: str) -> Decision:
        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError("response is not valid JSON") from exc

        if not isinstance(payload, dict):
            raise ValueError("response must be a JSON object")

        action = payload.get("action")
        if not isinstance(action, str) or action not in {"tool", "finish", "fail"}:
            raise ValueError("action must be one of: tool, finish, fail")

        reason = payload.get("reason", "")
        if not isinstance(reason, str):
            raise ValueError("reason must be a string")

        message = payload.get("message")
        if message is not None and not isinstance(message, str):
            raise ValueError("message must be a string")

        confidence = payload.get("confidence")
        if confidence is not None:
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                raise ValueError("confidence must be a number between 0 and 1")
            confidence = float(confidence)

        tool_name = payload.get("tool_name")
        if tool_name is not None and not isinstance(tool_name, str):
            raise ValueError("tool_name must be a string")

        arguments = payload.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be a JSON object")

        normalized_arguments: dict[str, str] = {}
        for key, value in arguments.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("tool arguments must be string key/value pairs")
            normalized_arguments[key] = value

        if action == "tool":
            if not tool_name:
                raise ValueError("tool action requires tool_name")
        elif tool_name is not None or normalized_arguments:
            raise ValueError("tool_name and arguments are only valid for tool actions")

        return Decision(
            action=action,
            tool_name=tool_name,
            arguments=normalized_arguments,
            reason=reason,
            message=message,
            confidence=confidence,
            raw_model_output=raw_output,
        )


class MockLLMPlanner:
    """Planner adapter that turns model text into a structured decision."""

    def __init__(self, model: Model) -> None:
        self._model = model

    def decide(self, context: ModelContext) -> Decision:
        raw_output = self._model.generate(context)

        try:
            return ModelOutputParser.parse(raw_output)
        except ValueError as exc:
            return Decision(
                action="fail",
                reason="The model output could not be parsed into a safe decision.",
                message=f"invalid model output: {exc}",
                raw_model_output=raw_output,
            )


def _terms(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", value.lower())
        if len(token) > 2
    }


def _context_terms(context: ModelContext) -> set[str]:
    parts = [context.task.description]
    parts.extend(context.memory.keys())
    parts.extend(context.memory.values())

    for observation in context.observations:
        parts.append(observation.source)
        parts.extend(observation.values.keys())
        parts.extend(observation.values.values())

    return _terms(" ".join(parts))


def _resolve_argument(name: str, context: ModelContext) -> str | None:
    if name in context.memory:
        return context.memory[name]

    task_value = getattr(context.task, name, None)
    if isinstance(task_value, str) and task_value:
        return task_value

    return None


def _softmax(scores: list[float], temperature: float) -> list[float]:
    scaled = [score / temperature for score in scores]
    maximum = max(scaled)
    exponentials = [math.exp(value - maximum) for value in scaled]
    total = sum(exponentials)
    return [value / total for value in exponentials]
