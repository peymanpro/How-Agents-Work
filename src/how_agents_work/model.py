from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Protocol

from .models import Decision, ModelContext


class Model(Protocol):
    """Minimal model boundary used by the planner adapter."""

    def generate(self, context: ModelContext) -> str:
        """Return a model-like text response for the supplied context."""
        ...


class MockLLM:
    """Deterministic simulator for an LLM response boundary.

    The simulator delegates decision selection to a deterministic policy so the
    demo remains reproducible, then serializes that decision as model-like JSON.
    Raw response overrides can intentionally simulate malformed model output.
    """

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

        return json.dumps(payload, sort_keys=True)


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
            raw_model_output=raw_output,
        )


class MockLLMPlanner:
    """Planner adapter that turns MockLLM text into a structured decision."""

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
