from how_agents_work.tools import CalculateDelay, GetOrder


def test_get_order_checks_customer_ownership() -> None:
    tool = GetOrder()

    observation = tool.run({"order_id": "O-1002", "customer_id": "C-03"})

    assert not observation.success
    assert "does not belong" in (observation.error or "")


def test_calculate_delay_reports_lateness() -> None:
    tool = CalculateDelay()

    observation = tool.run({"actual_days": "4", "allowed_days": "2"})

    assert observation.success
    assert observation.values["difference_days"] == "2"
    assert observation.values["is_late"] == "True"
