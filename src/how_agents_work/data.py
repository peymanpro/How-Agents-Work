from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: str
    shipping_method: str
    tracking_id: str
    actual_days: int
    status: str


@dataclass(frozen=True)
class Tracking:
    tracking_id: str
    latest_status: str
    exception: str | None = None


@dataclass(frozen=True)
class CustomerHistory:
    customer_id: str
    recent_escalations: int


@dataclass
class DemoSystem:
    orders: dict[str, Order]
    tracking: dict[str, Tracking]
    policies: dict[str, int]
    escalation_thresholds: dict[str, int]
    history: dict[str, CustomerHistory]
    escalations: list[dict[str, str]] = field(default_factory=list)

    def create_escalation(self, order_id: str, reason: str) -> str:
        existing = next(
            (item for item in self.escalations if item["order_id"] == order_id),
            None,
        )
        if existing:
            return existing["id"]

        escalation_id = f"ESC-{len(self.escalations) + 1:04d}"
        self.escalations.append(
            {
                "id": escalation_id,
                "order_id": order_id,
                "reason": reason,
            }
        )
        return escalation_id


def build_demo_system() -> DemoSystem:
    return DemoSystem(
        orders={
            "O-1001": Order("O-1001", "C-01", "standard", "T-7001", 3, "delivered"),
            "O-1002": Order("O-1002", "C-02", "express", "T-7002", 4, "delayed"),
            "O-1003": Order("O-1003", "C-03", "standard", "T-7003", 2, "delivered"),
            "O-1004": Order("O-1004", "C-04", "standard", "T-7004", 5, "delayed"),
            "O-1005": Order("O-1005", "C-05", "standard", "T-7005", 4, "delayed"),
        },
        tracking={
            "T-7001": Tracking("T-7001", "delivered"),
            "T-7002": Tracking("T-7002", "in_transit"),
            "T-7003": Tracking("T-7003", "delivered"),
            "T-7004": Tracking("T-7004", "exception", "carrier delay"),
            "T-7005": Tracking("T-7005", "in_transit"),
        },
        policies={"standard": 3, "express": 2},
        escalation_thresholds={"standard": 2, "express": 1},
        history={
            "C-01": CustomerHistory("C-01", 0),
            "C-02": CustomerHistory("C-02", 0),
            "C-03": CustomerHistory("C-03", 0),
            "C-04": CustomerHistory("C-04", 1),
            "C-05": CustomerHistory("C-05", 0),
        },
    )
