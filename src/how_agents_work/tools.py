from __future__ import annotations

from collections.abc import Mapping

from .data import DemoSystem
from .models import Observation, ToolSpec


class Tool:
    name: str
    description: str
    read_only: bool = True
    arguments: tuple[str, ...] = ()

    def spec(self):
        return ToolSpec(
            name=self.name,
            description=self.description,
            read_only=self.read_only,
            arguments=self.arguments,
        )

    def run(self, arguments: Mapping[str, str]) -> Observation:
        raise NotImplementedError


class GetOrder(Tool):
    name = "get_order"
    description = "Look up an order after verifying customer ownership."
    arguments = ("order_id", "customer_id")

    def __init__(self, system: DemoSystem) -> None:
        self._system = system

    def run(self, arguments: Mapping[str, str]) -> Observation:
        order_id = arguments.get("order_id")
        customer_id = arguments.get("customer_id")

        if not order_id or not customer_id:
            return Observation(
                self.name, False, error="order_id and customer_id are required"
            )

        order = self._system.orders.get(order_id)
        if order is None:
            return Observation(self.name, False, error=f"order {order_id!r} was not found")

        if order.customer_id != customer_id:
            return Observation(
                self.name,
                False,
                error=f"order {order_id!r} does not belong to customer {customer_id!r}",
            )

        return Observation(
            self.name,
            True,
            {
                "order_id": order.order_id,
                "customer_id": order.customer_id,
                "shipping_method": order.shipping_method,
                "tracking_id": order.tracking_id,
                "actual_days": str(order.actual_days),
                "order_status": order.status,
            },
        )


class GetTracking(Tool):
    name = "get_tracking"
    description = "Read the latest carrier status for an order."
    arguments = ("tracking_id",)

    def __init__(self, system: DemoSystem) -> None:
        self._system = system

    def run(self, arguments: Mapping[str, str]) -> Observation:
        tracking_id = arguments.get("tracking_id")
        if not tracking_id:
            return Observation(self.name, False, error="tracking_id is required")

        tracking = self._system.tracking.get(tracking_id)
        if tracking is None:
            return Observation(
                self.name, False, error=f"tracking {tracking_id!r} was not found"
            )

        values = {
            "tracking_id": tracking.tracking_id,
            "latest_status": tracking.latest_status,
        }
        if tracking.exception:
            values["exception"] = tracking.exception

        return Observation(self.name, True, values)


class GetShippingPolicy(Tool):
    name = "get_shipping_policy"
    description = "Read delivery limits and escalation thresholds for a shipping method."
    arguments = ("shipping_method",)

    def __init__(self, system: DemoSystem) -> None:
        self._system = system

    def run(self, arguments: Mapping[str, str]) -> Observation:
        method = arguments.get("shipping_method")
        if not method:
            return Observation(self.name, False, error="shipping_method is required")

        allowed_days = self._system.policies.get(method)
        threshold = self._system.escalation_thresholds.get(method)
        if allowed_days is None or threshold is None:
            return Observation(
                self.name, False, error=f"no policy exists for {method!r}"
            )

        return Observation(
            self.name,
            True,
            {
                "shipping_method": method,
                "allowed_days": str(allowed_days),
                "escalation_threshold": str(threshold),
            },
        )


class GetCustomerHistory(Tool):
    name = "get_customer_history"
    description = "Check recent escalation history before creating another escalation."
    arguments = ("customer_id",)

    def __init__(self, system: DemoSystem) -> None:
        self._system = system

    def run(self, arguments: Mapping[str, str]) -> Observation:
        customer_id = arguments.get("customer_id")
        if not customer_id:
            return Observation(
                self.name, False, error="customer_id is required"
            )

        history = self._system.history.get(customer_id)
        if history is None:
            return Observation(
                self.name, False, error=f"customer {customer_id!r} was not found"
            )

        return Observation(
            self.name,
            True,
            {
                "customer_id": history.customer_id,
                "recent_escalations": str(history.recent_escalations),
            },
        )


class CreateEscalation(Tool):
    name = "create_escalation"
    description = "Create one escalation for an order. This is a side-effecting tool."
    read_only = False
    arguments = ("order_id", "reason")

    def __init__(self, system: DemoSystem) -> None:
        self._system = system

    def run(self, arguments: Mapping[str, str]) -> Observation:
        order_id = arguments.get("order_id")
        reason = arguments.get("reason")

        if not order_id or not reason:
            return Observation(
                self.name, False, error="order_id and reason are required"
            )

        if order_id not in self._system.orders:
            return Observation(
                self.name, False, error=f"order {order_id!r} was not found"
            )

        escalation_id = self._system.create_escalation(order_id, reason)
        return Observation(
            self.name,
            True,
            {
                "escalation_id": escalation_id,
                "order_id": order_id,
            },
        )


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def run(self, name: str, arguments: Mapping[str, str]) -> Observation:
        tool = self.get(name)
        if tool is None:
            return Observation(name, False, error=f"tool {name!r} is not registered")
        return tool.run(arguments)

    def specs(self):
        return [tool.spec() for tool in self._tools.values()]

    def describe(self) -> list[str]:
        return [f"{tool.name}: {tool.description}" for tool in self._tools.values()]
