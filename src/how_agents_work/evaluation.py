from __future__ import annotations

from dataclasses import dataclass

from .models import AgentResult, AgentTask


@dataclass(frozen=True)
class EvaluationCase:
    name: str
    task: AgentTask
    expected_text: str
    expected_success: bool = True


def evaluate(results: list[tuple[EvaluationCase, AgentResult]]) -> tuple[int, int]:
    passed = sum(
        result.success == case.expected_success
        and case.expected_text in result.message
        for case, result in results
    )
    return passed, len(results)
