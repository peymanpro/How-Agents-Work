# How Agents Work

A small, deterministic C# project for understanding what an agent actually does.

This repository does **not** call an LLM or an external API. Instead, it makes the agent loop explicit:

```text
Task
  ↓
Observe current state
  ↓
Choose the next action
  ↓
Use a tool
  ↓
Store the observation
  ↓
Re-evaluate the state
  ↓
Repeat until the task is complete
```

The point is to make the moving parts visible before adding a language model.

## What this project demonstrates

The demo agent works on a simple support scenario:

> Check a customer's order and decide whether a delayed shipment should be escalated.

The agent has:

- **Task** — the goal it is trying to complete.
- **Planner** — selects the next action from the current state.
- **Tools** — provide information or perform small operations.
- **Memory** — stores observations gathered during the run.
- **State** — combines the task, observations, and completed tool calls.
- **Trace** — records what happened so the run can be inspected.
- **Stop condition** — the agent finishes when it has enough evidence to produce an outcome, or fails safely when the evidence is insufficient.

The data is intentionally fixed and local. That keeps the example reproducible and makes the agent mechanics easier to study.

## A useful distinction

A normal function might look like this:

```text
get order → get shipping policy → calculate delay → decide
```

An agent loop looks more like:

```text
look at state
    ├─ missing order information → call GetOrder
    ├─ order found, policy missing → call GetShippingPolicy
    ├─ both available → calculate delay
    └─ evidence is sufficient → finish
```

The important part is the repeated **observe → decide → act** cycle.

In this project, the planner is rule-based on purpose. A production system could replace that planner with an LLM, while keeping the surrounding ideas—tools, memory, state, validation, and stopping rules.

## Project structure

```text
HowAgentsWork/
├── src/
│   └── HowAgentsWork/
│       ├── Agent/
│       ├── Data/
│       ├── Models/
│       ├── Planning/
│       ├── Tools/
│       └── Program.cs
└── tests/
    └── HowAgentsWork.Tests/
```

## Running the demo

Requirements:

- .NET 8 SDK

Run:

```bash
dotnet run --project src/HowAgentsWork
```

Run tests:

```bash
dotnet test
```

The console output shows the agent's trace rather than hiding everything behind a single final answer.

## Why the example is intentionally small

The repository is an educational model, not an attempt to reproduce a commercial agent framework.

It avoids:

- external model APIs,
- hidden prompts,
- vector databases,
- web search,
- background workers,
- framework-specific abstractions.

That leaves the core mechanism visible enough to read in one sitting.

## Where the model can go next

Once the deterministic version is understood, the same architecture can be extended with:

1. an LLM-backed planner,
2. richer tool schemas,
3. persistent memory,
4. retrieval,
5. tool-result validation,
6. retries and timeouts,
7. human approval for sensitive actions,
8. evaluation datasets.

Those additions are easier to reason about when the basic agent loop is already explicit.

## Design goal

The project is written as a learning artifact:

> **Understand the loop first. Add intelligence second.**

