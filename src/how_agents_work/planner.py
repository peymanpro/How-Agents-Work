from __future__ import annotations

from .models import AgentState, Decision


class SupportPlanner:
    """Choose the next action from the evidence gathered so far."""

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
                reason="I need verified order data before I can investigate the shipment.",
            )

        if not order.success:
            return Decision(
                "fail",
                reason="The order lookup did not produce trustworthy evidence.",
                message=f"the order could not be verified: {order.error}",
            )

        tracking = state.latest("get_tracking")
        if tracking is None:
            return Decision(
                "tool",
                "get_tracking",
                {"tracking_id": order.values["tracking_id"]},
                reason="The order tells me which shipment to inspect next.",
            )

        if not tracking.success:
            return Decision(
                "fail",
                reason="Carrier information is unavailable, so escalation would be guesswork.",
                message=f"tracking could not be verified: {tracking.error}",
            )

        policy = state.latest("get_shipping_policy")
        if policy is None:
            return Decision(
                "tool",
                "get_shipping_policy",
                {"shipping_method": order.values["shipping_method"]},
                reason="I need the delivery policy to interpret the observed delay.",
            )

        if not policy.success:
            return Decision(
                "fail",
                reason="There is no verified policy against which to compare the shipment.",
                message=f"shipping policy could not be verified: {policy.error}",
            )

        actual = int(order.values["actual_days"])
        allowed = int(policy.values["allowed_days"])
        delay = actual - allowed

        if delay <= 0:
            return Decision(
                "finish",
                reason="The available evidence shows the delivery is within policy.",
                message="no escalation is needed: the shipment is within the allowed delivery time",
            )

        history = state.latest("get_customer_history")
        if history is None:
            return Decision(
                "tool",
                "get_customer_history",
                {"customer_id": state.task.customer_id},
                reason="The shipment is late; I should check recent history before creating a side effect.",
            )

        if not history.success:
            return Decision(
                "fail",
                reason="I cannot safely decide whether a new escalation would duplicate recent support activity.",
                message=f"customer history could not be verified: {history.error}",
            )

        recent_escalations = int(history.values["recent_escalations"])
        threshold = int(policy.values["escalation_threshold"])
        tracking_status = tracking.values["latest_status"]

        escalation = state.latest("create_escalation")
        if escalation is not None:
            if escalation.success:
                return Decision(
                    "finish",
                    reason="The requested side effect succeeded, so the agent can stop.",
                    message=f"escalation created: {escalation.values['escalation_id']}",
                )
            return Decision(
                "fail",
                reason="The escalation tool reported a failure.",
                message=f"escalation could not be created: {escalation.error}",
            )

        if recent_escalations > 0:
            return Decision(
                "finish",
                reason="A recent escalation exists, so creating another one would risk duplication.",
                message="manual review is required: a recent escalation already exists for this customer",
            )

        if delay < threshold:
            return Decision(
                "finish",
                reason="The shipment is late, but the delay is below the policy escalation threshold.",
                message=f"no escalation yet: the shipment is {delay} day(s) late, below the {threshold}-day escalation threshold",
            )

        reason = f"{delay} day(s) late; tracking status is {tracking_status}"
        return Decision(
            "tool",
            "create_escalation",
            {"order_id": order.values["order_id"], "reason": reason},
            reason="The evidence crosses the escalation threshold and no recent escalation exists.",
        )
