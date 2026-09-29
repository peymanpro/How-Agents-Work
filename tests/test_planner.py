from how_agents_work.models import AgentState, AgentTask
from how_agents_work.planner import SupportPlanner
from how_agents_work.tools import GetOrder


def test_planner_starts_by_getting_the_order() -> None:
    state = AgentState(AgentTask("C-02", "O-1002"))

    decision = SupportPlanner().decide(state)

    assert decision.action == "tool"
    assert decision.tool_name == "get_order"


def test_planner_fails_when_order_lookup_failed() -> None:
    state = AgentState(AgentTask("C-02", "O-1002"))
    state.add(GetOrder().run({"order_id": "missing", "customer_id": "C-02"}))

    decision = SupportPlanner().decide(state)

    assert decision.action == "fail"
