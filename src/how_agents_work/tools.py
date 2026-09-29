from __future__ import annotations

from collections.abc import Mapping

from .data import ORDERS, SHIPPING_POLICIES
from .models import Observation


class Tool:
    name: str

    def run(self, arguments: Mapping[str, str]) -> Observation:
        raise NotImplementedError


class GetOrder(Tool):
    name = "get_order"

    def run(self, arguments: Mapping[str, str]) -> Observation:
        order_id = arguments.get("order_id")
        customer_id = arguments.get("customer_id")

        if not order_id or not customer_id:
            return Observation(
                self.name, False, error="order_id and customer_id are required"
            )

        order = ORDERS.get(order_id)
        if order is None:
            return Observation(
                self.name, False, error=f"order {order_id!r} was not found"
            )

        if order.customer_id != customer_id:
            return Observation(
                self.name,
                False,
                error=f"order {order_id!r} does not belong to customer {customer_id!r}",
            )

        return Observation(
            self.name,
            True,
            values={
                "order_id": order.order_id,
                "customer_id": order.customer_id,
                "shipping_method": order.shipping_method,
                "actual_days": str(order.actual_days),
                "status": order.status,
            },
        )


class GetShippingPolicy(Tool):
    name = "get_shipping_policy"

    def run(self, arguments: Mapping[str, str]) -> Observation:
        method = arguments.get("shipping_method")
        if not method:
            return Observation(
                self.name, False, error="shipping_method is required"
            )

        allowed_days = SHIPPING_POLICIES.get(method)
        if allowed_days is None:
            return Observation(
                self.name,
                False,
                error=f"no policy exists for shipping method {method!r}",
            )

        return Observation(
            self.name,
            True,
            values={
                "shipping_method": method,
                "allowed_days": str(allowed_days),
            },
        )


class CalculateDelay(Tool):
    name = "calculate_delay"

    def run(self, arguments: Mapping[str, str]) -> Observation:
        try:
            actual_days = int(arguments["actual_days"])
            allowed_days = int(arguments["allowed_days"])
        except (KeyError, ValueError):
            return Observation(
                self.name,
                False,
                error="actual_days and allowed_days must be integers",
            )

        difference = actual_days - allowed_days

        return Observation(
            self.name,
            True,
            values={
                "actual_days": str(actual_days),
                "allowed_days": str(allowed_days),
                "difference_days": str(difference),
                "is_late": str(difference > 0),
            },
        )


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def run(self, name: str, arguments: Mapping[str, str]) -> Observation:
        tool = self._tools.get(name)
        if tool is None:
            return Observation(
                name, False, error=f"tool {name!r} is not registered"
            )
        return tool.run(arguments)
