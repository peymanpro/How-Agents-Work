from .agent import Agent
from .models import AgentTask
from .planner import SupportPlanner
from .tools import CalculateDelay, GetOrder, GetShippingPolicy, ToolRegistry


def build_agent() -> Agent:
    registry = ToolRegistry(
        [
            GetOrder(),
            GetShippingPolicy(),
            CalculateDelay(),
        ]
    )
    return Agent(SupportPlanner(), registry)


def main() -> None:
    agent = build_agent()
    tasks = [
        AgentTask("C-02", "O-1002"),
        AgentTask("C-03", "O-1003"),
    ]

    print("How Agents Work")
    print("================")
    print()

    for task in tasks:
        result = agent.run(task)

        print(f"Task: {task.description}")
        for entry in result.trace:
            print(f"  [{entry.step}] {entry.kind:<11} {entry.detail}")

        print()
        print(f"Result: {'completed' if result.success else 'failed'}")
        print(f"Decision: {result.message}")
        print("-" * 72)


if __name__ == "__main__":
    main()
