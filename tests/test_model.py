import json

from how_agents_work.model import MockLLM, MockLLMPlanner, ModelOutputParser
from how_agents_work.models import AgentState, Decision, AgentTask


def build_context():
    state = AgentState(AgentTask("C-02", "O-1002"))
    return state.build_context(
        step=1,
        available_tools=(),
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
