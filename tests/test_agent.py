import pytest

from how_agents_work.agent import Agent
from how_agents_work.main import build_agent
from how_agents_work.models import AgentTask, Decision
from how_agents_work.tools import ToolRegistry


def test_delayed_order_is_escalated() -> None:
    result = build_agent().run(AgentTask("C-02", "O-1002"))

    assert result.success
    assert "escalate" in result.message
    assert [entry.kind for entry in result.trace] == [
        "action",
        "observation",
        "action",
        "observation",
        "action",
        "observation",
        "finish",
    ]


def test_on_time_order_is_not_escalated() -> None:
    result = build_agent().run(AgentTask("C-03", "O-1003"))

    assert result.success
    assert "no escalation" in result.message


def test_wrong_customer_fails_without_guessing() -> None:
    result = build_agent().run(AgentTask("C-03", "O-1002"))

    assert not result.success
    assert "could not be verified" in result.message


def test_agent_stops_at_the_step_limit() -> None:
    class NoProgressPlanner:
        def decide(self, state):
            return Decision(action="tool", tool_name="unknown")

    result = Agent(NoProgressPlanner(), ToolRegistry([]), max_steps=2)

    assert not result.success
    assert "stopped after 2 steps" in result.message


def test_invalid_step_limit_is_rejected() -> None:
    class NoProgressPlanner:
        def decide(self, state):
            return Decision(action="tool", tool_name="unknown")

    with pytest.raises(ValueError, match="max_steps"):
        Agent(NoProgressPlanner(), ToolRegistry([]), max_steps=0)
