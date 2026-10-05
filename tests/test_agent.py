import pytest

from how_agents_work.agent import Agent
from how_agents_work.data import build_demo_system
from how_agents_work.main import build_agent
from how_agents_work.models import AgentTask, Decision
from how_agents_work.tools import GetOrder, GetTracking, ToolRegistry


def test_delayed_order_reaches_a_side_effecting_tool() -> None:
    result = build_agent().run(AgentTask("C-02", "O-1002"))

    assert result.success
    assert "escalation created" in result.message
    assert any(
        entry.kind == "tool_call" and "create_escalation" in entry.detail
        for entry in result.trace
    )


def test_on_time_order_finishes_without_escalation() -> None:
    result = build_agent().run(AgentTask("C-03", "O-1003"))

    assert result.success
    assert "no escalation" in result.message
    assert all("create_escalation" not in entry.detail for entry in result.trace)


def test_recent_history_changes_the_plan() -> None:
    result = build_agent().run(AgentTask("C-04", "O-1004"))

    assert result.success
    assert "manual review" in result.message
    assert all("create_escalation" not in entry.detail for entry in result.trace)


def test_small_delay_does_not_cross_the_escalation_threshold() -> None:
    result = build_agent().run(AgentTask("C-05", "O-1005"))

    assert result.success
    assert "no escalation yet" in result.message
    assert all("create_escalation" not in entry.detail for entry in result.trace)


def test_failed_tool_observation_stops_the_run_safely() -> None:
    system = build_demo_system()
    del system.tracking["T-7002"]

    registry = ToolRegistry(
        [
            GetOrder(system),
            GetTracking(system),
        ]
    )
    result = Agent(
        build_agent()._planner,
        registry,
    ).run(AgentTask("C-02", "O-1002"))

    assert not result.success
    assert "tracking could not be verified" in result.message


def test_side_effects_can_be_blocked() -> None:
    result = build_agent(allow_side_effects=False).run(
        AgentTask("C-02", "O-1002")
    )

    assert not result.success
    assert "side effects are disabled" in result.message


def test_repeated_tool_calls_are_guarded() -> None:
    class RepeatingPlanner:
        def decide(self, context):
            return Decision(
                "tool",
                "get_order",
                {"order_id": "O-1002", "customer_id": "C-02"},
            )

    result = Agent(
        RepeatingPlanner(),
        ToolRegistry([GetOrder(build_demo_system())]),
        max_steps=3,
    ).run(AgentTask("C-02", "O-1002"))

    assert not result.success
    assert "repeated tool call" in result.message


def test_tool_call_budget_is_enforced() -> None:
    class ChangingPlanner:
        def __init__(self) -> None:
            self._customer = 0

        def decide(self, state):
            self._customer += 1
            return Decision(
                "tool",
                "get_order",
                {
                    "order_id": f"O-100{self._customer}",
                    "customer_id": f"C-0{self._customer}",
                },
            )

    result = Agent(
        ChangingPlanner(),
        ToolRegistry([GetOrder(build_demo_system())]),
        max_steps=5,
        max_tool_calls=2,
    ).run(AgentTask("C-01", "O-1001"))

    assert not result.success
    assert "tool-call budget of 2 was exhausted" in result.message


def test_invalid_limits_are_rejected() -> None:
    with pytest.raises(ValueError):
        Agent(object(), ToolRegistry([]), max_steps=0)

    with pytest.raises(ValueError):
        Agent(object(), ToolRegistry([]), max_tool_calls=0)


def test_trace_exposes_model_context_and_tool_boundary() -> None:
    result = build_agent().run(AgentTask("C-02", "O-1002"))

    assert any(entry.kind == "context" for entry in result.trace)
    assert any(entry.kind == "model_output" for entry in result.trace)
    assert any(entry.kind == "tool_call" for entry in result.trace)
    assert any("tools=[" in entry.detail for entry in result.trace if entry.kind == "context")


def test_invalid_tool_arguments_are_rejected_by_runtime() -> None:
    class BadPlanner:
        def decide(self, context):
            return Decision(
                "tool",
                "get_order",
                {"order_id": "O-1002", "unexpected": "value"},
            )

    result = Agent(
        BadPlanner(),
        ToolRegistry([GetOrder(build_demo_system())]),
    ).run(AgentTask("C-02", "O-1002"))

    assert not result.success
    assert "invalid arguments" in result.message
