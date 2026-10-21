# Fixed-grid AutoML baseline

This is a lightweight conventional AutoML strategy implemented using the existing forecasting tools, not a claim to represent every AutoML package. It automatically trains candidates, scores validation forecasts, chooses the lowest-loss recipe for each component, freezes choices, and refits the resulting pipeline at each test origin. No LLM, API key, or paid model calls are required.

## Protocol fixed before execution

- Daily recipes: current Prophet/historical means, weekly seasonal naive, ridge (alpha 10), and Extra Trees (150 trees, depth 4, minimum leaf 7). Alternatives use a 1,095-day history window, existing lag/calendar features, and existing recursive prediction logic. Defaults and full recipes are recorded in the plan and trial ledger.
- Curves: all three existing choices for each of quote multiplier and conversion.
- 34 component/curve trials × four validation folds; the earlier synthetic research agent used 20 trials and had broader configurable choices. This comparison does not isolate LLM versus conventional search under equal budgets/search spaces.
- Selection uses the same kind of component objective as the earlier agent: pooled daily RMSE, multiplier bin MAE, and conversion log loss. AutoML takes the minimum; exact ties keep the earlier recipe. The agent had discretion. No new downstream objective is introduced in this experiment.
- Selection data: baseline seed42; four 90-day windows after 2031-12-31, 2032-03-31, 2032-06-30, 2032-09-30. Choices freeze before final scoring.
- Evaluation: the same five synthetic paths and twelve quarterly 90-day windows per path as the robustness study. 14/28-day results are prefixes. Current and earlier frozen-agent results are reused; the current pipeline is also recomputed and checked for consistency.
- All these final scenarios have already been examined in previous work. This is a retrospective benchmark extension, not a fresh untouched holdout. No model revisions are permitted in response to its final scores.
- Price comparison recomputes the common non-DNQ intersection across all three candidates. Price reference uses current training curves and realized components; it is diagnostic, not a revenue-optimal label. Supply RMSE is the primary reported result; DNQ disagreements remain separately available.

## Outputs and reproduction

`uv run python -m src.automl_benchmark --out experiments/automl_grid_new`

Use a new output directory. The plan records source hashes before fitting; selection/trials.json and audit.jsonl record trials, validation scores and runtime; frozen_choices.json records the selections. The evaluation subdirectory uses the generic transfer runner's `frozen_agent` label for AutoML only; the top-level comparison_results.json correctly labels current, frozen_agent (the original GPT choices), and automl. comparison_pricing.csv recalculates matched price dates. status.json records completion, trial counts, runtime and zero API spend.

## Limits

Three baseline seeds and two paired stress paths come from the same historical simulator. They are not independent real-world experiments. Synthetic tests cannot establish revenue gains. No claim that AutoML universally outperforms agents (or vice versa) is supported. A future equal-budget study would need the same permitted search space, objective, multiple search repetitions and new held-out conditions.

## Frozen selections

Extra Trees was selected for AOG rate, CNA rate, and enquiry count; ridge for scheduled-maintenance rate. Current recipes were retained for unscheduled maintenance, program legs, and non-program legs. Demand curves selected current LOWESS multiplier and isotonic conversion. These choices came from validation, not final test results.

## Results

See the [executive summary](../experiments/automl_grid_v1/EXECUTIVE_SUMMARY.md) and [complete 90-day table](../experiments/automl_grid_v1/REPORT.md). Selection and code were not changed after final scoring. The original runner source remains byte-for-byte consistent with the pre-run hash in plan.json.
