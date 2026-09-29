# How Agents Work

A small, deterministic Python project for understanding what an AI agent actually does.

The project deliberately avoids an LLM, external APIs, frameworks, databases, and hidden prompts. The goal is to make the **agent loop** visible first.

## The idea

An agent is useful when the next step depends on what happened in the previous step.

A normal program can be written as a fixed pipeline:

~~~text
get order
  ↓
get policy
  ↓
calculate delay
  ↓
make a decision
~~~

An agent loop is different:

~~~text
goal
  ↓
observe state
  ↓
decide next action
  ↓
use a tool
  ↓
observe the result
  ↓
update state
  ↓
decide again
  ↓
finish or stop
~~~

In this repository the planner is rule-based rather than LLM-based, so the decisions are predictable. The surrounding architecture is still the same architecture we would need when a model becomes the planner.

## The example

The demo agent handles a tiny customer-support problem:

> Check a customer's order and decide whether a delayed shipment should be escalated.

The input data is fixed:

| Order | Customer | Method | Actual days | Allowed days | Outcome |
| --- | --- | --- | ---: | ---: | --- |
| O-1001 | C-01 | standard | 3 | 3 | no escalation |
| O-1002 | C-02 | express | 4 | 2 | escalate |
| O-1003 | C-03 | standard | 2 | 3 | no escalation |

The fixed data is intentional. Reproducible input makes the agent's behavior easy to inspect and test.

## What makes it an agent?

The interesting part is not the business rule. It is the loop around the rule.

For order O-1002, the agent starts with almost no knowledge:

~~~text
Task:
  customer = C-02
  order = O-1002

Memory:
  empty
~~~

The planner sees that it does not yet know the order, so it chooses:

~~~text
get_order(order_id=O-1002, customer_id=C-02)
~~~

The tool returns an observation. That observation becomes part of the state.

Now the planner can see the shipping method, but it still does not know the policy. It therefore chooses:

~~~text
get_shipping_policy(shipping_method=express)
~~~

The same pattern happens again for the delay calculation.

Only after the required evidence exists does the planner finish:

~~~text
4 actual days - 2 allowed days = 2 days late
→ escalate
~~~

So the agent is repeatedly answering:

> **Given everything I know right now, what should I do next?**

## The pieces

### Task

The goal and the initial input.

### State

The current working state. Here it contains the original task plus all observations collected during the run.

### Planner

Chooses the next action from the current state.

In this demo the planner is deterministic:

~~~python
if order is missing:
    get the order
elif policy is missing:
    get the policy
elif delay is missing:
    calculate the delay
else:
    finish
~~~

A model-backed agent would put an LLM in roughly this position.

### Tool

A small capability that can inspect data or perform an operation.

The example has three tools:

- **get_order**
- **get_shipping_policy**
- **calculate_delay**

Tools return structured observations rather than directly changing the planner's mind.

### Memory

Here, the agent's short-term memory is the list of observations in AgentState.

That is enough to demonstrate the idea. Persistent memory, semantic memory, or retrieval can be added later without changing the basic loop.

### Trace

Every action and observation is recorded.

This is important because an agent that only returns a final answer hides the most useful part of its behavior: **how it got there**.

### Stop condition

The agent can finish normally, fail because required evidence is unavailable, or stop after a maximum number of steps.

The step limit protects the loop from running forever.

## A run, step by step

A delayed shipment produces a trace like this:

~~~text
[1] action       get_order(order_id=O-1002, customer_id=C-02)
[1] observation  get_order: order_id=O-1002, customer_id=C-02, shipping_method=express, actual_days=4, status=delayed

[2] action       get_shipping_policy(shipping_method=express)
[2] observation  get_shipping_policy: shipping_method=express, allowed_days=2

[3] action       calculate_delay(actual_days=4, allowed_days=2)
[3] observation  calculate_delay: actual_days=4, allowed_days=2, difference_days=2, is_late=True

[4] finish       escalate the shipment: it is 2 day(s) beyond the 2-day policy
~~~

Notice that there is no giant function containing every step. The agent reaches the next step from the state that the previous step created.

## Project structure

~~~text
HowAgentsWork/
├── README.md
├── pyproject.toml
├── src/
│   └── how_agents_work/
│       ├── __init__.py
│       ├── __main__.py
│       ├── agent.py
│       ├── data.py
│       ├── main.py
│       ├── models.py
│       ├── planner.py
│       └── tools.py
└── tests/
    ├── test_agent.py
    ├── test_planner.py
    └── test_tools.py
~~~

## Running it

Python 3.11 or newer is required.

Create a virtual environment and install the development dependency:

~~~bash
python -m venv .venv
~~~

Activate it, then:

~~~bash
python -m pip install -e ".[dev]"
python -m how_agents_work
pytest
~~~

The first command installs the package in editable mode. That is why the example can be run as a normal Python module instead of relying on a manually configured PYTHONPATH.

## What this project is not

This is not a production agent framework and it does not claim to be one.

It intentionally leaves out:

- LLM calls
- prompt management
- vector databases
- web search
- asynchronous workers
- retries with external services
- persistent memory
- multi-agent coordination

Those features are useful, but adding them too early can make the basic idea harder to see.

## From this demo to a real LLM agent

A practical next step would be to replace SupportPlanner with an LLM-backed planner.

The overall shape could remain:

~~~text
Agent
 ├── State / Memory
 ├── Planner  ← LLM
 ├── Tool registry
 ├── Validation
 └── Trace / evaluation
~~~

The model would receive a description of the current state and the tools it is allowed to call. It would choose a tool or return a final response. The tool result would then be added to the state and the model would be called again.

That distinction matters:

> The LLM is one component of an agent. It is not the whole agent.

## Why start without an LLM?

A deterministic implementation gives us three useful properties:

1. **The mechanics are visible.** We can read the loop without first understanding prompting.
2. **The behavior is reproducible.** The same task produces the same trace.
3. **The design is testable.** We can test tools, planning decisions, failure handling, and the complete loop separately.

Once those pieces are clear, adding an LLM becomes an architectural change rather than a leap into a black box.

## Design goal

The repository is intentionally small enough to read in one sitting.

> **Understand the loop first. Add intelligence second.**
