from how_agents_work.memory import WorkingMemory


def test_memory_returns_a_copy() -> None:
    memory = WorkingMemory()
    memory.remember({"order_id": "O-1002"})

    snapshot = memory.snapshot()
    snapshot["order_id"] = "changed"

    assert memory.get("order_id") == "O-1002"


def test_memory_tracks_known_facts() -> None:
    memory = WorkingMemory()

    assert not memory.has("tracking_id")

    memory.remember({"tracking_id": "T-7002"})

    assert memory.has("tracking_id")
    assert memory.get("tracking_id") == "T-7002"
