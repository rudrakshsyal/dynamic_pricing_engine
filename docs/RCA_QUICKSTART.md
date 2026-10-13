# Read-only DPE explanation workflow

## What is implemented

One selected date → fixed saved-file snapshot → supply/demand/solver checks → offline report → optional tool-calling OpenAI agent.

The existing notebooks and pricing calculations are not changed. No tool accepts a new price, a scenario, arbitrary file paths, or another date during the agent run. The command-line `--root` is an operator option, not an agent tool argument.

### Layers

- `src/rca_tools.py`: your original recommendation and supply lookup functions, preserved.
- `src/rca_evidence.py`: loads a snapshot; reconstructs supply and demand; checks the solver branch; renders the offline report. This is the stronger evidence layer used by the new workflow.
- `src/rca_agent.py`: one OpenAI agent with three read-only tools for supply, demand and solver evidence. SDK imports happen only when this mode is requested.
- `src/explain_price.py`: terminal entry point using the same evidence and agent functions as the UI.
- `tests/test_rca_evidence.py`: synthetic tests that require neither private data nor an API key.

## First run: offline, no API key

From the repository root:

```bash
uv run python -m src.explain_price 2026-01-05
uv run python -m src.explain_price 2026-01-01
uv run python -m src.explain_price 2026-01-03
```

The output includes a saved yield or DNQ marker, the supply subtraction, demand at the floor/selected yield/ceiling, consistency checks, limitations and an evidence snapshot fingerprint.

For machine-readable evidence:

```bash
uv run python -m src.explain_price 2026-01-05 --json
```

No files are written by these commands. A missing date or failed consistency check exits with code 2. The agent will not run on evidence marked `needs_review` or `not_found`.

## Optional AI explanation

Install the optional dependency into your project when ready:

```bash
uv add "openai-agents==0.23.1"
```

Set `OPENAI_API_KEY` in your local process environment, and select a model available to your OpenAI API project. Do not paste credentials into chat. This CLI does not automatically load `.env`.

```bash
uv run python -m src.explain_price 2026-01-05 --agent --model YOUR_MODEL_ID
```

This makes paid model calls and sends the selected date's evidence and caveats to the model. It does not upload raw quote histories. SDK trace export is disabled for this initial version; tool names are returned locally. The engine's stored recommendation is never recalculated or overwritten.

The brief allows eight agent turns per attempt and at most one correction attempt for invalid output. The agent must call all three tools and cite valid evidence IDs. Its generated prose is displayed alongside the deterministic report. Reference checks do not establish that every sentence is semantically correct: evaluate the narrative before relying on it. A local Streamlit UI provides an on-demand Explain button. Read-only follow-up chat retains the last four exchanges within the selected evidence scope.

## Important interpretation details

- `$15,000` on a DNQ row is a marker, not an offer to sell.
- Saved DNQ demand is forced to zero; independently reconstructed demand at $15,000 can be positive.
- Supply and enquiries are expected values. Fractional legs are not physical allocations.
- The current solver uses a $7,000 floor, despite the parameter file's $6,000 floor. Constants are read as Python literals from the solver notebook without executing it.
- Demand logic mirrors the inspected solver: interpolation with boundary clamping, multiplied by absolute exponential conversion. If solver logic changes, update this adapter; it is not a general notebook interpreter.
- The saved yield is rounded to whole dollars, saved demand to two decimals, and root tolerance is $1. Comparisons allow that rounding.
- Hashes identify the current loaded files, not the original historical engine run. Capturing files is sequential; it is not a transactional snapshot of a running writer. Do not regenerate artefacts during loading. Cross-file checks detect some inconsistencies, not all provenance errors.
- Existing supply category overlap, date-basis mismatch and conversion limitations are disclosed rather than repaired.
- Full snapshot loading happens per request. This is appropriate for these small saved tables; a production API may need a versioned immutable cache.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```

The SDK adapter was checked with openai-agents 0.23.1 using a mocked runner (no live model call). SDK wiring tests skip when the optional package is absent.

Tests cover solver statuses, missing/invalid dates, duplicates, non-finite numbers, changed inputs, malformed curves and unsupported agent references. A manual audit can also iterate all dates in the local saved recommendation file; that is numerical reconciliation, not validation of the underlying models.

## What to review together

1. Inspect one solved report and one DNQ report.
2. Confirm terminology is understandable to a pricing manager.
3. Install the SDK, choose a model, and run one agent explanation.
4. Compare every generated claim with its cited evidence.
5. Review the same dates in the local interface. Read-only chat is available; automatic data-team escalation remains deferred.

Official SDK reference: https://developers.openai.com/api/docs/guides/agents/quickstart?lang=python

## Local Explain interface

From the repository root, in a terminal with `OPENAI_API_KEY` already set:

```bash
uv run --with "streamlit==1.58.0" streamlit run app.py --server.address 127.0.0.1
```

Open the local address printed by Streamlit. Select a departure date, inspect the saved recommendation, and click **Explain**. The model defaults to `gpt-5.5`, which has been used successfully in this project; change it in the sidebar if needed. Loading the page and selecting dates do not make model calls. Without a key, the calculations are still available and Explain is disabled. This UI does not automatically load `.env`.

The explanation includes expandable evidence references. Supply arithmetic, demand evaluations, consistency checks, limitations, file hashes and an evidence JSON download are available underneath. DNQ days show **Do not quote**, not a sellable $15,000 price. Failed evidence checks block generation.

Changing the date, model or evidence snapshot clears the previous explanation. Ordinary rerenders retain the current explanation without another API call; clicking Explain again generates a new response. The interface uses the existing pricing outputs and does not modify them. Draft data-team questions are displayed locally and are not sent anywhere.

The launch command supplies Streamlit without changing the project's dependency files. To run the optional UI tests as well:

```bash
uv run --with "streamlit==1.58.0" python -m unittest discover -s tests -v
```

UI interaction tests use synthetic data and a mocked agent: no API charges. They cover on-demand calls, missing credentials, DNQ presentation, stale explanation clearing on model changes, failed evidence checks and sanitized provider errors. They do not establish the quality of live model prose.


## Revenue brief checks

Before displaying an AI brief, the application requires three insights of at most 18 whitespace-separated words each. It rejects internal field names, hours in the capacity insight, selected unsupported business claims, and numbers that do not match cited numeric evidence at the displayed precision. The decision must name the saved outcome (balanced, floor, ceiling or do not quote). Rejected prose is withheld; the saved report remains available. There is at most one additional correction call for invalid AI output; the UI discloses it.

These are targeted checks, not full semantic verification: a number can match evidence while being described incorrectly, and wording rules cannot detect every contradiction. Unresolved data-team questions are not semantically validated. Tests use synthetic examples and a mocked runner, not live model-quality evaluations.


## Read-only follow-up chat

Expand **Ask about this date**, type a question, and select **Ask**. Each submission calls the selected model and sends the selected snapshot's evidence, limitations, question, and up to four recent exchanges. No API call occurs simply from typing or rerendering. Chat uses the same API-key environment as Explain.

The agent has one parameterless, read-only tool bound to the selected date. It cannot write prices, access another date through that tool, or send messages. Instructions require declining new-price and what-if requests. Questions that need unavailable evidence receive a draft question for the data team; nothing is transmitted to the team. Citation and response-length checks are enforced, but they cannot prove factual accuracy or perfect adherence to the scope instructions.

Chat is kept in the browser's Streamlit session, with no application database. Changing date, model or snapshot clears the conversation; Clear chat also resets it. Provider retention follows the API project's settings. SDK tracing remains disabled. Current chat tests use a mocked SDK runner and mocked UI agent, not live model evaluations.


## Benchmark and runtime update

See [model comparison plan](MODEL_BENCHMARK_PLAN.md) for offline historical evaluation and optional LLM replacement scripts. Benchmarks are separate from the read-only explanation app.

The UI now retains a process-lifetime async event loop for SDK connections. Invalid structured answers can receive one correction attempt using the retrieved evidence, so one button click may make additional model calls. Persistent validation failures remain visible. No paid test was performed; restart the Streamlit process once after updating to ensure old imported modules are replaced.
