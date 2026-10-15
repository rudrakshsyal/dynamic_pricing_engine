# Adaptive GPT-5.5 experiment agent

## Status

Completed October 14, 2026: 24 trials, 47 GPT-5.5 requests, $2.8575 conservatively accounted under the approved $4 cap. The agent pipeline did not outperform the current engine overall. See [completed results](../experiments/gpt55_adaptive_2026-10-14/RUN_SUMMARY.md). The earlier fixed-search results belong to a different experiment.

This agent makes research decisions: what to inspect, which model family to try, which features/settings to change, whether to blend models, when to stop and which successful trial to select. Python fits models and calculates metrics. Unlike `model_selection_agent.py`, this version does not run a fixed candidate grid or automatically choose the smallest score. The agent may choose a simpler or more stable trial and must explain why.

## Workflow and tools

1. `catalog`: read model options, recipe bounds and remaining trial budget.
2. `record_plan`: record an initial strategy or revision.
3. `inspect_data`: inspect aggregate training characteristics, weekday means and lag correlations. Summaries stop at the first training cutoff.
4. `run_trial`: train one agent-chosen recipe across all three fixed validation windows. Returns pooled error and fold results. Failures consume a trial; duplicate configurations reuse their result.
5. `review_errors`: inspect fold errors, weekday bias and forecast-horizon MAE.
6. `blend_trials`: evaluate an agent-chosen weighted average of two or three successful daily model trials.
7. `freeze_choices`: select all seven daily forecasts and two curves, recording a reason for each. The current baseline must have been evaluated for each component. Freezing disables further experiments.

After the agent finishes, a separate evaluator refits selected recipes and the current pipeline on the same training cutoff and evaluates final results. No final-test tool, raw file reader, shell, web search or arbitrary code execution is exposed to the agent. Its workbench contains development-period data only. Raw customer quote rows are never returned by the tools.

## Research freedom and limits

Daily families: current recipes, repeat-last-week, recent mean, Ridge, Extra Trees, XGBoost and configurable Prophet. The agent controls lag days, rolling windows, calendar features, log transform, history length, regularization, tree depth/count, learning rate, leaf settings and Prophet seasonality/changepoint settings where relevant. Parameter bounds are enforced by a strict schema; unused settings do not affect a family.

History length: 180–730 days; lags/windows: 1–90 days; trees: 20–300; depth: 1–8; Ridge alpha: .01–1000; learning rate: .01–.3; minimum leaf/child-weight setting: 2–30. The current recipe always uses full expanding history. Forecasts recurse without injecting validation actuals and are constrained to nonnegative counts and rates between zero and one. Seed 42 is used for tree models.

Curve choices remain bounded to current LOWESS/constant-one/half-strength LOWESS and current exponential/constant/isotonic conversion. The agent can choose their experiment order and final selection, but cannot invent an arbitrary curve estimator in this version. Ensembles apply to daily forecasts only.

This is bounded adaptive research, not unrestricted model-code generation. The agent can investigate fewer candidates than a grid, tune promising ones and change direction after inspecting errors.

## Evaluation contract

Validation origins: June 30, August 31 and September 30, 2025. Each predicts the following 28 days. Daily selection evidence includes pooled RMSE, MAE, bias and fold errors. Conversion uses log loss and Brier; multiplier uses observational normalized-bin MAE. Tools do not force the agent to select the numerical minimum.

Final comparison: November 1–28, 2025, with training through October 31. This period has already been inspected in earlier work; it is explicitly **retrospective**, not a fresh untouched holdout. November data are absent from the agent workbench, but prior human knowledge still limits an independence claim. December was also used in an earlier LLM pilot. A genuinely new test requires a predeclared later dataset or a separately designed evaluation; do not rename these old dates an untouched holdout.

Three arms:

- Current forecasting recipes + current curves (Prophet and seasonal/mean baselines).
- Agent-selected forecasts + current curves.
- Agent-selected forecasts + agent-selected curves.

Report forecast RMSE/MAE/bias, remaining-supply proxy errors, solver-status agreement, DNQ disagreement, conversion metrics and diagnostic price MAE. Price MAE uses the identical intersection of non-DNQ dates across all arms and the reference; it is not comparable across differing subsets.

The reference uses actual historical daily inputs with the current train-only demand curve. It is not a true optimal-price label. No revenue uplift or causal price elasticity is established. Final-extract revisions, mixed quote/realized yields, maturity approximations, fixed productivity and enquiry/departure-date alignment remain limitations.

Any improvement measures the **whole agent-designed search pipeline versus fixed current recipes**. It does not isolate LLM intelligence from extra tuning and compute. To test that incremental contribution, a future experiment needs a compute-matched non-agentic search comparator and repeated independent agent runs.

## Initial run design (subsequently reduced and executed; see budget update below)

Model: GPT-5.5. Maximum 36 distinct trials (including baselines, ensembles and failed trials), each evaluated over three folds; maximum 50 model turns; maximum 2,500 output tokens per model response. Model/tool calls are sequential. No automatic API retries; request timeout 180 seconds. Tracing is disabled and model response storage is disabled. These are count/token bounds, **not a dollar cap or a hard total runtime limit**. Input tokens grow with experiment history. Local model fits have bounded sizes but no process timeout. A failed/incomplete agent run does not trigger final evaluation.

The CLI requires `--allow-paid` and loads `OPENAI_API_KEY` from the repository `.env` without printing it. Merely adding the key does not start anything. A new empty output directory is required; existing results are not overwritten. Missing dependencies and final date coverage are checked before paid execution. Source hashes are checked again before final scoring.

Only after approval:

```bash
uv run python -m src.research_agent \
  --out experiments/gpt55_adaptive_research_01 \
  --model gpt-5.5 --allow-paid \
  --max-trials 24 --max-turns 50 --max-output-tokens 2500 --budget-usd 4
```

On macOS, XGBoost may require `libomp`; follow the existing model-selection methodology runtime instructions. Production models, saved recommendations and the explanation UI are not changed by this experiment.

## Audit and outputs

- `manifest.json`: source/code hashes, dates, model and run limits.
- `audit.jsonl`: plans, inspections, attempted/completed trials, error reviews, blends and frozen choices. This is an action/rationale log, not private reasoning.
- `trials.json`: all trial recipes, metrics, failures and fit times; `validation_<id>.csv`: daily validation predictions.
- `frozen_choices.json`: agent-selected trial IDs and reasons.
- `usage.json`: completed API request/token usage, updated after responses. A failed request may not provide usage, so this is not a billing statement.
- `agent_summary.json`: agent's final methodology/caveats.
- `run_status.json`: execution state; `final_results.json`, `predictions_*.csv`, `final_actuals.csv`, `pricing.csv`, `report.md`: independent final evaluation outputs.

Tests use synthetic data and mocked agent execution, including real SDK tool dispatch without an API request. They cover every supported forecast family, recipe bounds, data isolation, budget/cache behavior, failed trials, ensembles, error diagnostics, discretionary selection, freeze locks, paid gate, incomplete-run handling and final report generation. The subsequent paid run completed successfully; all audit files are linked above.

Implementation: `src/research_experiments.py`, `src/research_agent.py`, `tests/test_research_agent.py`. SDK tools follow [official OpenAI tool guidance](https://developers.openai.com/api/docs/guides/tools).

## Approved budget update — October 14, 2026

User approved a maximum $4 and asked to minimize cost. `research_budget.py` now counts input tokens before each request, reserves standard uncached-input cost plus maximum-output cost, and blocks dispatch if it cannot fit. Completed usage reconciles the reservation, conservatively ignoring cache discounts. Requests use the standard tier and api.openai.com endpoint. Long contexts above 272K, hosted tools, streaming and other models are blocked. Uncertain failures retain the reservation and stop the run. This application ledger is not an account-wide billing limit.

The first run is reduced to 24 trials, with at most 50 turns and 2,500 output tokens per response. Budget tests bring the offline suite to 21 passing tests. `budget.json` retains reservations and usage; `response_*.json` stores visible tool calls and messages, excluding private reasoning and credentials. The first approved run uses `--budget-usd 4 --max-trials 24`.
