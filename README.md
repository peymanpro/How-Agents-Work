# How Agents Work

A small deterministic Python project for understanding how an agent works as a **system**.

It is intentionally not an LLM demo.

There is no model API, no external service, and no framework hiding the control flow. Instead, the repository makes the runtime visible:

```text
goal
  ↓
state
  ↓
planner
  ↓
guardrails
  ↓
tool
  ↓
observation
  ↓
memory + state update
  ↓
planner again
  ↓
finish / fail / continue
```

The planner in this repository is deterministic. The architecture around it is the interesting part.

## Why this repository exists

A lot of introductory agent examples reduce the idea to:

```python
while not done:
    action = llm(...)
    tool_result = tool(action)
```

That is a useful sketch, but it leaves several engineering questions unanswered:

- What does the agent remember?
- How does the next action depend on previous observations?
- What happens when a tool fails?
- What prevents the same tool call from repeating forever?
- What prevents an agent from creating a side effect when it is not allowed?
- Where does the execution budget live?
- How do we evaluate the behavior rather than only the final answer?

This project keeps those questions in the code.

## The example problem

The agent investigates customer shipments.

Its goal is:

> Investigate a shipment and decide whether it needs escalation.

The demo environment is fixed and local so every run is reproducible.

| Order | Customer | Method | Actual days | Status | Condition |
| --- | --- | --- | ---: | --- | --- |
| O-1001 | C-01 | standard | 3 | delivered | within policy |
| O-1002 | C-02 | express | 4 | delayed | escalation threshold crossed |
| O-1003 | C-03 | standard | 2 | delivered | within policy |
| O-1004 | C-04 | standard | 5 | delayed | recent escalation exists |
| O-1005 | C-05 | standard | 4 | delayed | late, but below threshold |

Policy data is part of the same environment:

| Method | Allowed days | Escalation threshold |
| --- | ---: | ---: |
| standard | 3 | 2 |
| express | 2 | 1 |

This is deliberately small, but it is not a fixed sequence of calls. Different evidence produces different behavior.

## The important difference: the path can change

For order `O-1002`, the initial state is roughly:

```text
task = customer C-02, order O-1002

memory = empty
observations = empty
tool calls = empty
```

The planner cannot decide whether to escalate yet.

So it selects:

```text
get_order
```

The order observation adds:

```text
shipping_method = express
tracking_id = T-7002
actual_days = 4
```

That changes the state.

The planner sees the new state and chooses:

```text
get_tracking
```

The tracking observation changes the available evidence again.

Then the planner chooses:

```text
get_shipping_policy
```

Only after the policy is known can it calculate the relevant delay.

Because the order is late, it performs another information-gathering step:

```text
get_customer_history
```

The history is clean, so the planner now permits a side effect:

```text
create_escalation
```

After that tool succeeds, the next decision is to stop.

The key idea is:

> **The next action is a function of the current state, not just the task.**

That is what makes the loop agent-like.

## The runtime pieces

### Task

`AgentTask` is the goal plus the identifiers required to start the investigation.

A task is not the same thing as state.

The task stays stable while state accumulates evidence.

### State

`AgentState` represents one execution.

It stores:

- the original task,
- observations,
- working memory,
- normalized tool-call history.

Every tool result changes what the planner can know.

### Working memory

`WorkingMemory` is intentionally simple.

It stores the facts that successful observations make available:

```text
order_id = O-1002
tracking_id = T-7002
shipping_method = express
actual_days = 4
allowed_days = 2
recent_escalations = 0
```

This is short-term working memory.

It is not a vector store and it is not meant to represent long-term user memory.

The important concept is that observations are not thrown away after a tool call.

### Planner

`SupportPlanner` chooses one of:

```text
tool
finish
fail
```

The planner is deliberately deterministic.

That lets us answer:

> What does the runtime do around the planner?

without first having to answer:

> Why did the model generate this text?

A real LLM can replace the planner later.

### Tool registry

The agent does not call Python classes directly from the planner.

The planner chooses a named capability:

```text
get_order
get_tracking
get_shipping_policy
get_customer_history
create_escalation
```

The registry resolves that name to a tool implementation.

That boundary matters because it is where a real system can later add:

- schemas,
- authentication,
- permissions,
- rate limits,
- timeouts,
- telemetry,
- tool versioning.

### Observations

A tool returns an `Observation`.

An observation says:

```text
who produced the information
whether it succeeded
what values were learned
what error occurred, if any
```

The planner consumes observations on the next iteration.

This creates a clean separation:

```text
decision → action → observation → new state
```

### Side effects

Not every tool is read-only.

`create_escalation` modifies the demo environment.

The runtime therefore knows whether a tool is read-only:

```text
read tool
    ↓
safe to execute normally

side-effecting tool
    ↓
subject to runtime policy
```

This is a small but useful distinction. In a real agent, sending an email, changing a record, placing an order, or deploying code should not be treated exactly like reading a document.

## Branching behavior

The demo intentionally contains several paths.

### Late enough to escalate

For `O-1002`:

```text
get order
  ↓
get tracking
  ↓
get policy
  ↓
get customer history
  ↓
create escalation
  ↓
finish
```

The agent gathers evidence before taking the side effect.

### Within policy

For `O-1003`:

```text
get order
  ↓
get tracking
  ↓
get policy
  ↓
finish
```

The agent does not call customer history because it has no reason to consider an escalation.

It also does not call the escalation tool simply because that tool is available.

### Recent escalation

For `O-1004`:

```text
get order
  ↓
get tracking
  ↓
get policy
  ↓
get customer history
  ↓
finish → manual review
```

The agent stops instead of creating a duplicate escalation.

### Late but below threshold

For `O-1005`:

```text
get order
  ↓
get tracking
  ↓
get policy
  ↓
get customer history
  ↓
finish → no escalation yet
```

The system has enough information to know the shipment is late, but not enough reason to take the strongest action.

This is an important pattern in agent design:

> More information does not necessarily mean more actions.

## Guardrails are part of the agent system

The planner is not trusted blindly.

The runtime checks:

### Tool existence

A planner can name a capability that is not registered.

The runtime turns that into a controlled failure instead of an exception escaping into the program.

### Side-effect policy

The same agent can be run with:

```python
allow_side_effects=False
```

Then the planner may still decide that escalation is appropriate, but the runtime refuses to execute the mutating tool.

This models a useful real-world separation:

```text
What the planner wants
        ≠
What the runtime permits
```

### Repeated calls

A planner stuck in a loop can repeatedly choose the exact same tool and arguments.

The state records normalized tool calls.

If the same call is attempted again, the runtime stops the run.

### Tool-call budget

The runtime also has a maximum tool-call count.

This is separate from the step limit.

That distinction matters because a future agent could perform several non-tool decisions between tool calls, and production systems often need more than one bound.

### Step limit

A maximum number of reasoning/acting steps is the final escape hatch.

It prevents an agent from running forever even when the planner makes no useful progress.

## Why the trace matters

A normal function often gives you:

```text
input → output
```

An agent needs a trace:

```text
decision
action
observation
decision
action
observation
...
```

The demo prints this trace so you can see where each new piece of evidence entered the run.

For `O-1002`, the important shape is:

```text
[1] decision
[1] action
[1] observation

[2] decision
[2] action
[2] observation

[3] decision
[3] action
[3] observation

...
```

The trace is also useful for evaluation and debugging.

If an agent eventually makes a wrong decision, the trace lets us ask:

- Did it retrieve the wrong fact?
- Did it skip a needed tool?
- Did it misunderstand the observation?
- Did a guardrail block the action?
- Did it terminate too early?

## What the LLM would change

The LLM would primarily change the planner.

Today:

```text
Agent
  ├── deterministic planner
  ├── state
  ├── memory
  ├── tools
  └── runtime guardrails
```

A future version could become:

```text
Agent
  ├── LLM planner
  ├── state
  ├── memory
  ├── tool registry
  ├── validation
  ├── runtime guardrails
  └── trace / evaluation
```

The LLM would decide among tool calls and final responses.

The rest of the system would still be necessary.

This is why it is useful to separate:

```text
model capability
from
agent runtime
```

## What an LLM-backed iteration might look like

A simplified planner prompt could contain:

```text
Goal:
  Investigate shipment O-1002.

Current state:
  shipping_method = express
  actual_days = 4
  tracking_status = in_transit

Available tools:
  get_customer_history(customer_id)
  create_escalation(order_id, reason)

Choose exactly one next action.
```

The model might return:

```text
get_customer_history(customer_id=C-02)
```

The runtime would still:

1. validate that the tool exists,
2. validate the arguments,
3. check whether it is permitted,
4. execute it,
5. store the observation,
6. call the planner again.

The model supplies flexible planning.

The runtime supplies control.

## Evaluation

The repository includes a small deterministic evaluator.

The demo contains expected scenarios and checks whether the observed result matches each scenario.

This is intentionally simple.

The point is to establish the evaluation boundary:

```text
scenario
  ↓
agent run
  ↓
trace + result
  ↓
expected outcome
  ↓
evaluation
```

A production evaluation suite could add measurements such as:

- unnecessary tool calls,
- invalid tool arguments,
- failure recovery,
- policy violations,
- latency,
- cost,
- final-answer quality.

The important idea is that an agent should be evaluated as a system.

## Failure is also a behavior

The project includes a case where tracking information is unavailable.

The agent does not invent a tracking result.

Instead:

```text
tool failure
  ↓
failed observation
  ↓
planner sees missing evidence
  ↓
safe failure
```

This matters because an agent should not turn missing evidence into confident action.

## Project structure

```text
HowAgentsWork/
├── .github/
│   └── workflows/
│       └── tests.yml
├── README.md
├── pyproject.toml
├── src/
│   └── how_agents_work/
│       ├── __init__.py
│       ├── __main__.py
│       ├── agent.py
│       ├── data.py
│       ├── evaluation.py
│       ├── main.py
│       ├── memory.py
│       ├── models.py
│       ├── planner.py
│       └── tools.py
└── tests/
    ├── test_agent.py
    ├── test_evaluation.py
    ├── test_memory.py
    ├── test_planner.py
    └── test_tools.py
```

## Running the project

Python 3.11 or newer is required.

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it, then install the project and test dependency:

```bash
python -m pip install -e ".[dev]"
```

Run the demo:

```bash
python -m how_agents_work
```

Run the tests:

```bash
pytest
```

Runtime dependencies are limited to the Python standard library. `pytest` is a development dependency.

## Why the data is fixed

A networked example would make the demo depend on things that are not the point:

- external availability,
- credentials,
- API changes,
- network latency,
- provider differences.

Fixed data gives us a stable laboratory for the control loop.

The environment can later be replaced without changing the conceptual architecture.

## What this project intentionally does not include

This repository is not a production agent framework.

It does not attempt to solve:

- prompt engineering,
- model selection,
- RAG,
- embeddings,
- vector databases,
- persistent memory,
- distributed execution,
- multi-agent coordination,
- authentication,
- streaming,
- deployment orchestration.

Those are separate layers.

The focus here is narrower:

> **Understand how an agent turns observations into its next action, while remaining bounded and inspectable.**

## The mental model to keep

A useful way to remember the architecture is:

```text
Goal
  +
Current State
  +
Available Capabilities
  +
Runtime Rules
  ↓
Next Action
  ↓
Observation
  ↓
Updated State
  ↓
Repeat
```

The model can be swapped.

The tools can be swapped.

The environment can be swapped.

The runtime loop remains recognizable.

## Design goal

The project should be small enough to read, but not so small that it becomes a toy pipeline.

The main question is:

> **How does a system repeatedly turn evidence into the next action without losing control of the run?**
