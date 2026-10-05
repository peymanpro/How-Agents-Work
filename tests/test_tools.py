from how_agents_work.data import build_demo_system
from how_agents_work.tools import CreateEscalation, GetOrder, ToolRegistry


def test_get_order_rejects_wrong_customer() -> None:
    observation = GetOrder(build_demo_system()).run(
        {"order_id": "O-1002", "customer_id": "C-03"}
    )

    assert not observation.success
    assert "does not belong" in (observation.error or "")


def test_create_escalation_is_idempotent() -> None:
    system = build_demo_system()
    tool = CreateEscalation(system)

    first = tool.run({"order_id": "O-1002", "reason": "late"})
    second = tool.run({"order_id": "O-1002", "reason": "late again"})

    assert first.values["escalation_id"] == "ESC-0001"
    assert second.values["escalation_id"] == "ESC-0001"
    assert len(system.escalations) == 1


def test_registry_describes_tools() -> None:
    registry = ToolRegistry([GetOrder(build_demo_system())])

    assert registry.describe() == [
        "get_order: Look up an order after verifying customer ownership."
    ]


def test_registry_exposes_structured_tool_specs() -> None:
    registry = ToolRegistry([GetOrder(build_demo_system())])

    spec = registry.specs()[0]

    assert spec.name == "get_order"
    assert spec.read_only is True
    assert spec.arguments == ("order_id", "customer_id")
