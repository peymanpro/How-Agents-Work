from how_agents_work.data import build_demo_system
from how_agents_work.models import AgentState, AgentTask, Observation
from how_agents_work.planner import SupportPlanner
from how_agents_work.tools import GetOrder


def test_planner_starts_with_information_gathering() -> None:
    state = AgentState(AgentTask("C-02", "O-1002"))

    decision = SupportPlanner().decide(state)

    assert decision.action == "tool"
    assert decision.tool_name == "get_order"


def test_planner_reacts_to_a_failed_lookup() -> None:
    state = AgentState(AgentTask("C-02", "O-1002"))
    state.add_observation(
        Observation("get_order", False, error="missing order")
    )

    decision = SupportPlanner().decide(state)

    assert decision.action == "fail"


def test_planner_builds_its_next_step_from_observed_state() -> None:
    state = AgentState(AgentTask("C-02", "O-1002"))
    state.add_observation(
        GetOrder(build_demo_system()).run(
            {"order_id": "O-1002", "customer_id": "C-02"}
        )
    )

    decision = SupportPlanner().decide(state)

    assert decision.tool_name == "get_tracking"
