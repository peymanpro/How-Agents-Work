from .agent import Agent
from .data import build_demo_system
from .evaluation import EvaluationCase, evaluate
from .model import MockLLM, MockLLMPlanner, OpenEndedMockLLM
from .models import AgentTask
from .planner import SupportPlanner
from .tools import (
    CreateEscalation,
    GetCustomerHistory,
    GetOrder,
    GetShippingPolicy,
    GetTracking,
    ToolRegistry,
)


def build_agent(*, allow_side_effects: bool = True, planner=None) -> Agent:
    system = build_demo_system()
    registry = ToolRegistry(
        [
            GetOrder(system),
            GetTracking(system),
            GetShippingPolicy(system),
            GetCustomerHistory(system),
            CreateEscalation(system),
        ]
    )

    if planner is None:
        reference_policy = SupportPlanner()
        planner = MockLLMPlanner(MockLLM(reference_policy.decide))

    return Agent(
        planner,
        registry,
        allow_side_effects=allow_side_effects,
    )


def demo_cases() -> list[EvaluationCase]:
    return [
        EvaluationCase(
            "late express shipment",
            AgentTask("C-02", "O-1002"),
            "escalation",
        ),
        EvaluationCase(
            "on-time shipment",
            AgentTask("C-03", "O-1003"),
            "no escalation",
        ),
        EvaluationCase(
            "late shipment with recent escalation",
            AgentTask("C-04", "O-1004"),
            "manual review",
        ),
        EvaluationCase(
            "late shipment below escalation threshold",
            AgentTask("C-05", "O-1005"),
            "no escalation yet",
        ),
    ]


def main() -> None:
    agent = build_agent()
    cases = demo_cases()
    results = []

    print("How Agents Work")
    print("================")
    print(
        "A deterministic agent runtime with a simulated LLM response boundary."
    )
    print()

    for case in cases:
        result = agent.run(case.task)
        results.append((case, result))

        print(f"Task: {case.name}")
        print(f"  {case.task.description}")
        for entry in result.trace:
            print(f"  [{entry.step}] {entry.kind:<15} {entry.detail}")
        print(f"  Result: {'completed' if result.success else 'failed'}")
        print(f"  Decision: {result.message}")
        print("-" * 80)

    passed, total = evaluate(results)
    print(f"Evaluation: {passed}/{total} scenarios matched their expected outcome.")
    print()
    print("Open-ended model simulation")
    print("===========================")
    print(
        "The next decisions are sampled from tool relevance rather than a "
        "shipment-specific planner."
    )

    task = AgentTask(
        "C-02",
        "O-1002",
        request="Investigate this shipment and gather the most relevant evidence before deciding what to do.",
    )
    for seed in (1, 7):
        open_model = OpenEndedMockLLM(seed=seed, temperature=0.9)
        open_agent = build_agent(
            allow_side_effects=False,
            planner=MockLLMPlanner(open_model),
        )
        open_result = open_agent.run(task)
        first_model = next(
            entry for entry in open_result.trace if entry.kind == "model_output"
        )
        print(f"  seed={seed}: {first_model.detail}")


if __name__ == "__main__":
    main()
