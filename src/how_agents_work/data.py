from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: str
    shipping_method: str
    actual_days: int
    status: str


ORDERS = {
    "O-1001": Order("O-1001", "C-01", "standard", 3, "delivered on time"),
    "O-1002": Order("O-1002", "C-02", "express", 4, "delayed"),
    "O-1003": Order("O-1003", "C-03", "standard", 2, "delivered early"),
}

SHIPPING_POLICIES = {
    "standard": 3,
    "express": 2,
}
