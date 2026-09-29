from __future__ import annotations

from .models import AgentState, Decision


class SupportPlanner:
    """A deterministic planner that makes the agent loop easy to inspect."""

    def decide(self, state: AgentState) -> Decision:
        order = state.latest("get_order")

        if order is None:
            return Decision(
                "tool",
                "get_order",
                {
                    "order_id": state.task.order_id,
                    "customer_id": state.task.customer_id,
                },
            )

        if not order.success:
            return Decision(
                "fail",
                message=f"the order could not be verified: {order.error}",
            )

        policy = state.latest("get_shipping_policy")

        if policy is None:
            return Decision(
                "tool",
                "get_shipping_policy",
                {"shipping_method": order.values["shipping_method"]},
            )

        if not policy.success:
            return Decision(
                "fail",
                message=f"the shipping policy could not be verified: {policy.error}",
            )

        delay = state.latest("calculate_delay")

        if delay is None:
            return Decision(
                "tool",
                "calculate_delay",
                {
                    "actual_days": order.values["actual_days"],
                    "allowed_days": policy.values["allowed_days"],
                },
            )

        if not delay.success:
            return Decision(
                "fail",
                message=f"the delay could not be calculated: {delay.error}",
            )

        difference = int(delay.values["difference_days"])
        allowed = policy.values["allowed_days"]

        if difference > 0:
            return Decision(
                "finish",
                message=(
                    f"escalate the shipment: it is {difference} day(s) "
                    f"beyond the {allowed}-day policy"
                ),
            )

        return Decision(
            "finish",
            message="no escalation is needed: the shipment is within the allowed delivery time",
        )
