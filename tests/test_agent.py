import pytest

from how_agents_work.agent import Agent
from how_agents_work.main import build_agent
from how_agents_work.models import AgentTask, Decision
from how_agents_work.tools import GetOrder, ToolRegistry
from how_agents_work.data import build_demo_system


def test_delayed_order_reaches_a_side_effecting_tool() -> None:
    result = build_agent().run(AgentTask("C-02", "O-1002"))

    assert result.success
    assert "escalation created" in result.message
    assert any(
        entry.kind == "action" and "create_escalation" in entry.detail
        for entry in result.trace
    )


def test_on_time_order_finishes_without_escalation() -> None:
    result = build_agent().run(AgentTask("C-03", "O-1003"))

    assert result.success
    assert "no escalation" in result.message
    assert all(
        "create_escalation" not in entry.detail
        for entry in result.trace
    )


def test_recent_history_changes_the_plan() -> None:
    result = build_agent().run(AgentTask("C-04", "O-1004"))

    assert result.success
    assert "manual review" in result.message
    assert all(
        "create_escalation" not in entry.detail
        for entry in result.trace
    )


def test_side_effects_can_be_blocked() -> None:
    result = build_agent(allow_side_effects=False).run(
        AgentTask("C-02", "O-1002")
    )

    assert not result.success
    assert "side effects are disabled" in result.message


def test_repeated_tool_calls_are_guarded() -> None:
    class RepeatingPlanner:
        def decide(self, state):
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


def test_invalid_limits_are_rejected() -> None:
    with pytest.raises(ValueError):
        Agent(object(), ToolRegistry([]), max_steps=0)

    with pytest.raises(ValueError):
        Agent(object(), ToolRegistry([]), max_tool_calls=0)
