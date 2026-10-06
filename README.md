# How Agents Work

A small Python project for understanding how an agent works as a **system around a model boundary**.

> This repository is an **agent execution laboratory**, not a production agent framework.

The project makes the execution loop visible: what context a model receives, what response it produces, how that response becomes a structured decision, how the runtime validates and authorizes a tool call, what the environment returns, and how that observation changes the next decision.

There is no trained neural network and no external model API. The repository provides two local model simulations: a deterministic **MockLLM** for reproducible runs and an **OpenEndedMockLLM** for probabilistic, uncertain, domain-agnostic tool selection.

## The execution loop

~~~text
goal
  ↓
state + memory
  ↓
model context
  ↓
model
  ↓
raw model response
  ↓
parser
  ↓
structured decision
  ↓
runtime validation + guardrails
  ↓
tool
  ↓
observation
  ↓
state + memory update
  ↓
new model context
  ↓
model again
  ↓
finish / fail / continue
~~~

The important point is that the model proposes what should happen next, while the runtime controls what is actually allowed to happen.

## Why this repository exists

Many introductory agent examples reduce the idea to:

~~~python
while not done:
    action = llm(...)
    tool_result = tool(action)
~~~

That is a useful sketch, but it leaves several engineering questions unanswered:

- What context does the model receive?
- How are observations carried into the next iteration?
- What happens when a tool fails?
- What happens when the model returns malformed output?
- What prevents an unknown tool from being executed?
- What prevents repeated calls or uncontrolled tool usage?
- Where do side-effect permissions live?
- How can the execution be inspected and evaluated?

This project keeps those boundaries in code.

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

Different evidence produces different paths.

## The model boundary

The project separates the **model interface** from the **agent runtime**.

~~~text
ModelContext
    ↓
MockLLM / future real model
    ↓
raw text response
    ↓
ModelOutputParser
    ↓
Decision
    ↓
Agent runtime
~~~

The model receives:

- the original goal,
- current working memory,
- previous observations,
- available tool descriptions and required arguments,
- runtime constraints such as remaining tool-call budget.

The open-ended simulator uses these inputs as its only decision context. It does not inspect the shipment domain or call `SupportPlanner`.

The model does not execute tools directly.

### MockLLM

MockLLM simulates the response boundary of an LLM.

For a normal step it may produce:

~~~json
{
  "action": "tool",
  "arguments": {
    "order_id": "O-1002",
    "customer_id": "C-02"
  },
  "reason": "I need verified order data before I can investigate the shipment.",
  "tool_name": "get_order"
}
~~~

ModelOutputParser converts that text into the structured Decision used by the runtime.

The simulator is deliberately deterministic. Its decision policy is based on the same reproducible support-planning logic used by the baseline SupportPlanner.

This means:

~~~text
realistic boundary
        +
deterministic behavior
        =
inspectable laboratory
~~~

Both model simulations are local and offline. MockLLM also supports raw response overrides so tests can simulate malformed model responses without requiring a real API.

For example:

~~~text
raw model response
        ↓
invalid JSON
        ↓
parser failure
        ↓
safe agent failure
~~~

The repository therefore demonstrates an important principle:

> **Model output is untrusted input to the runtime.**

## The runtime

Agent is the execution runtime around the model.

At every iteration it:

1. builds a fresh ModelContext,
2. asks the planner/model adapter for a decision,
3. records the raw model response when one exists,
4. validates the structured decision,
5. checks runtime guardrails,
6. executes the selected tool,
7. stores the observation,
8. updates working memory,
9. repeats.

This creates the boundary:

~~~text
what the model proposes
        ≠
what the runtime permits
~~~

## Planner roles

There are two useful planner forms in the repository.

### SupportPlanner

SupportPlanner is the deterministic baseline.

It directly produces a structured Decision from ModelContext.

It is useful as the simplest reference implementation of model-side decision logic.

### MockLLMPlanner

MockLLMPlanner adds the model-response boundary:

~~~text
ModelContext
    ↓
MockLLM
    ↓
JSON text
    ↓
ModelOutputParser
    ↓
Decision
~~~

The agent runtime does not need to know whether the decision came from the deterministic baseline or from the simulated model protocol.

That separation makes a future real LLM adapter possible without rewriting the runtime.

## State and memory

AgentState represents one execution.

It stores:

- the original task,
- observations,
- working memory,
- normalized tool-call history.

WorkingMemory is intentionally small and short-lived.

For example:

~~~text
order_id = O-1002
tracking_id = T-7002
shipping_method = express
actual_days = 4
allowed_days = 2
recent_escalations = 0
~~~

Observations are not discarded after a tool call. They become part of the next model context.

## Tools

The planner chooses named capabilities:

~~~text
get_order
get_tracking
get_shipping_policy
get_customer_history
create_escalation
~~~

ToolRegistry resolves the name to an implementation and exposes structured ToolSpec metadata.

Each tool declares whether it is read-only and which arguments it requires.

This is the place where a larger system could later add:

- authentication,
- permissions,
- schemas,
- rate limits,
- timeouts,
- telemetry,
- tool versioning.

## Guardrails

The model is not trusted blindly.

The runtime checks:

### Tool existence

An unknown tool name is rejected before execution.

### Argument shape

Missing and unexpected arguments are rejected before execution.

### Side-effect policy

create_escalation is mutating.

The runtime can be run with:

~~~python
allow_side_effects=False
~~~

The model may still request the action, but the runtime refuses to perform it.

### Repeated calls

The runtime tracks normalized tool calls and stops an identical call from repeating indefinitely.

### Tool-call budget

A separate tool-call budget limits how many tool executions may occur during a run.

### Step limit

A maximum step count is the final protection against an infinite loop.

## Branching behavior

For O-1002:

~~~text
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
~~~

For O-1003:

~~~text
get order
  ↓
get tracking
  ↓
get policy
  ↓
finish
~~~

For O-1004:

~~~text
get order
  ↓
get tracking
  ↓
get policy
  ↓
get customer history
  ↓
finish → manual review
~~~

For O-1005:

~~~text
get order
  ↓
get tracking
  ↓
get policy
  ↓
get customer history
  ↓
finish → no escalation yet
~~~

The next action depends on the state built from previous evidence.


## Open-ended and uncertain decision-making

A real model does not have to follow one deterministic decision tree. At the same context, several actions can be plausible, and the model may choose among them with different confidence.

`OpenEndedMockLLM` approximates that behavior without pretending to be a neural network:

~~~text
current context
      ↓
candidate tool actions
      ↓
relevance scoring
      ↓
probability distribution
      ↓
temperature-controlled sampling
      ↓
one model response
~~~

This creates two properties that the deterministic planner cannot demonstrate:

- **Open decision space:** the next action is selected from the capabilities exposed in the current context rather than from a hard-coded shipment state machine.
- **Uncertainty:** multiple plausible actions can compete, so repeated runs can produce different model outputs and different confidence values.

The simulation is intentionally limited. Its relevance scoring is lexical and generic; it is **not equivalent to a trained language model understanding an unseen problem**. What it demonstrates is the architectural consequence of introducing an open-ended model boundary: the runtime must be prepared for decisions it did not author and must continue to validate them.

The main demo runs this simulator with side effects blocked so experimentation cannot mutate the environment.

## New problems without shipment-specific rules

The open-ended simulator is not given rules such as:

~~~text
if delayed:
    get_tracking
if threshold crossed:
    create_escalation
~~~

Instead, it sees only a task description and generic tool specifications. Tests include a new problem statement about application errors and service health using tools such as `inspect_logs` and `get_metrics`. The simulator can identify relevant capabilities from their descriptions without importing the shipment planner.

This is the right level of claim for this repository:

> **The model simulation can explore a new tool/problem space without a domain-specific decision tree; it does not possess genuine semantic understanding.**

## Failure is a behavior

The project includes a case where tracking information is unavailable.

The flow becomes:

~~~text
tool failure
  ↓
failed observation
  ↓
model sees missing evidence
  ↓
safe failure
~~~

The project also tests malformed model output:

~~~text
MockLLM
  ↓
malformed response
  ↓
parser rejects it
  ↓
agent stops safely
~~~

This distinction matters because an agent should not turn missing or malformed information into a confident action.

## Trace

A normal function often gives you:

~~~text
input → output
~~~

An agent needs a trace:

~~~text
context
model_response
model_output
tool_call
observation
context
model_response
model_output
tool_call
observation
...
~~~

For example, the trace can expose the transition:

~~~text
[1] context
[1] model_response
[1] model_output
[1] tool_call
[1] observation

[2] context
[2] model_response
[2] model_output
[2] tool_call
[2] observation
~~~

The raw response and parsed decision are intentionally separate trace events.

That makes the model/runtime boundary inspectable instead of implicit.

## Evaluation

The repository includes a small deterministic evaluator.

The flow is:

~~~text
scenario
  ↓
agent run
  ↓
trace + result
  ↓
expected outcome
  ↓
evaluation
~~~

A production evaluation suite could later measure:

- unnecessary tool calls,
- invalid tool arguments,
- failure recovery,
- policy violations,
- latency,
- cost,
- final-answer quality.

The point is to evaluate the agent as a system, not only to inspect its final message.

## Project structure

~~~text
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
│       ├── model.py
│       ├── models.py
│       ├── planner.py
│       └── tools.py
└── tests/
    ├── test_agent.py
    ├── test_evaluation.py
    ├── test_memory.py
    ├── test_model.py
    ├── test_planner.py
    └── test_tools.py
~~~

## Running the project

Python 3.11 or newer is required.

Create a virtual environment:

~~~bash
python -m venv .venv
~~~

Activate it, then install the project and test dependency:

~~~bash
python -m pip install -e ".[dev]"
~~~

Run the demo:

~~~bash
python -m how_agents_work
~~~

Run the tests:

~~~bash
pytest
~~~

Runtime dependencies are limited to the Python standard library. pytest is a development dependency.

## What this project intentionally does not include

This repository is not a production agent framework.

It does not attempt to solve:

- training or serving a neural network,
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

MockLLM is a deterministic simulation of the **model interface**, not a trained language model.

The focus is narrower:

> **Understand how a model, runtime, tools, state, memory, and guardrails cooperate during an agent execution.**

## The mental model to keep

~~~text
Goal
  ↓
Model Context
  ↓
Model / MockLLM
  ↓
Raw Model Response
  ↓
Parser
  ↓
Decision
  ↓
Runtime Validation
  ↓
Tool
  ↓
Observation
  ↓
State + Memory
  ↓
New Model Context
  ↓
Repeat
~~~

The model can be deterministic, probabilistic, or replaced by a real model adapter later. The runtime remains responsible for validation, authorization, tool execution, observations, state, memory, and guardrails.

The tools can be swapped.

The environment can be swapped.

The runtime loop remains recognizable.

## Design goal

The project should be small enough to read, but realistic enough to expose the boundaries that matter in an agent run.

The central question is:

> **How does an agent repeatedly turn a goal and new evidence into the next action without losing control of execution?**
