from __future__ import annotations

from collections.abc import Mapping


class WorkingMemory:
    """A tiny short-term memory used by a single agent run."""

    def __init__(self) -> None:
        self._facts: dict[str, str] = {}

    def remember(self, facts: Mapping[str, str]) -> None:
        self._facts.update(facts)

    def get(self, key: str) -> str | None:
        return self._facts.get(key)

    def has(self, key: str) -> bool:
        return key in self._facts

    def snapshot(self) -> dict[str, str]:
        return dict(self._facts)
