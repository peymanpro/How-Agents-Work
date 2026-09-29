from how_agents_work.evaluation import EvaluationCase, evaluate
from how_agents_work.models import AgentResult, AgentTask


def test_evaluation_counts_expected_outcomes() -> None:
    case = EvaluationCase(
        "demo",
        AgentTask("C-01", "O-1001"),
        "done",
    )
    result = AgentResult(True, "done here", (), {}, ())

    assert evaluate([(case, result)]) == (1, 1)
