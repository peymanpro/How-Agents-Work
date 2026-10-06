import json

from how_agents_work.model import (
    MockLLM,
    MockLLMPlanner,
    ModelOutputParser,
    OpenEndedMockLLM,
)
from how_agents_work.models import AgentState, Decision, AgentTask, ToolSpec


def build_context():
    state = AgentState(AgentTask("C-02", "O-1002"))
    return state.build_context(
        step=1,
        available_tools=(
            ToolSpec(
                "inspect_logs",
                "Inspect recent application logs for errors.",
                True,
            ),
            ToolSpec(
                "get_metrics",
                "Read current service health metrics.",
                True,
            ),
        ),
        constraints={"side_effects": "allowed"},
    )


def test_mock_llm_emits_llm_shaped_json() -> None:
    model = MockLLM(
        lambda context: Decision(
            "tool",
            "get_order",
            {"order_id": "O-1002", "customer_id": "C-02"},
            reason="Need verified order data.",
        )
    )

    raw = model.generate(build_context())
    payload = json.loads(raw)

    assert payload["action"] == "tool"
    assert payload["tool_name"] == "get_order"
    assert payload["arguments"]["order_id"] == "O-1002"


def test_mock_llm_planner_preserves_raw_model_response() -> None:
    planner = MockLLMPlanner(
        MockLLM(
            lambda context: Decision(
                "finish",
                reason="Enough evidence is available.",
                message="done",
            )
        )
    )

    decision = planner.decide(build_context())

    assert decision.action == "finish"
    assert decision.message == "done"
    assert decision.raw_model_output is not None
    assert '"action": "finish"' in decision.raw_model_output


def test_malformed_model_output_becomes_safe_failure() -> None:
    planner = MockLLMPlanner(
        MockLLM(
            lambda context: Decision("finish"),
            response_overrides={1: "this is not json"},
        )
    )

    decision = planner.decide(build_context())

    assert decision.action == "fail"
    assert "invalid model output" in (decision.message or "")
    assert decision.raw_model_output == "this is not json"


def test_parser_rejects_non_string_tool_arguments() -> None:
    raw = json.dumps(
        {
            "action": "tool",
            "tool_name": "get_order",
            "arguments": {"order_id": 1002},
        }
    )

    try:
        ModelOutputParser.parse(raw)
    except ValueError as exc:
        assert "string key/value pairs" in str(exc)
    else:
        raise AssertionError("expected parser to reject non-string arguments")


def test_parser_preserves_model_confidence() -> None:
    raw = json.dumps(
        {
            "action": "finish",
            "reason": "uncertain",
            "confidence": 0.37,
        }
    )

    decision = ModelOutputParser.parse(raw)

    assert decision.confidence == 0.37


def test_open_ended_model_is_reproducible_with_a_seed() -> None:
    first = OpenEndedMockLLM(seed=42).generate(build_context())
    second = OpenEndedMockLLM(seed=42).generate(build_context())

    assert first == second


def test_open_ended_model_can_make_non_deterministic_choices() -> None:
    outputs = {
        OpenEndedMockLLM(seed=seed, temperature=1.5).generate(build_context())
        for seed in range(12)
    }

    assert len(outputs) > 1


def test_open_ended_model_uses_tool_descriptions_for_a_new_problem() -> None:
    state = AgentState(
        AgentTask(
            "C-01",
            "O-1001",
            request=(
                "Investigate recent application errors and determine the "
                "current service health."
            ),
        )
    )
    context = state.build_context(
        step=1,
        available_tools=(
            ToolSpec(
                "inspect_logs",
                "Inspect recent application logs for errors.",
                True,
            ),
            ToolSpec(
                "get_metrics",
                "Read current service health metrics.",
                True,
            ),
            ToolSpec(
                "restart_service",
                "Restart an application service after diagnosis.",
                False,
            ),
        ),
        constraints={"side_effects": "blocked"},
    )

    raw = OpenEndedMockLLM(seed=3, temperature=0.4).generate(context)
    decision = ModelOutputParser.parse(raw)

    assert decision.action == "tool"
    assert decision.tool_name in {"inspect_logs", "get_metrics"}
    assert decision.confidence is not None
