from how_agents_work.main import build_agent
from how_agents_work.models import AgentTask


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
