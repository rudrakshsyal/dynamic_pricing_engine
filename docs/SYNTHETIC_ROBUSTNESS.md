# Offline robustness of frozen agent choices

This experiment transfers the GPT-5.5-selected pipeline from the previous synthetic pilot to three baseline seeds and two stress scenarios. It makes no API calls, performs no new model selection, and changes no production pricing code.

## Method

- Inputs: separately stored `experiments/synthetic_fleet_v1` datasets; seeds 42, 123 and 2026, plus paired seed42 demand-growth and maintenance-stress scenarios.
- Freeze: exact recipes from `experiments/synthetic_three_way_v1/agent`. Six daily components retain the current recipes. Scheduled maintenance uses ridge with 1,095 recent training days; conversion uses isotonic regression. Quote multiplier retains current LOWESS.
- Training: expanding history from 2026-01-01 through each origin, except the frozen ridge history window. Outcomes used for curve fitting must have both enquiry and departure dates on or before the origin.
- Test: 12 quarterly origins from 2032-12-31 to 2035-09-30. Predict the next 90 days once and score its 14/28/90-day prefixes. Quarterly windows cover June/July maintenance shocks. There are 1,080 distinct 90-day test dates per path, 5,400 path-days total; paths are related simulations, not independent real observations.
- Comparators: current Prophet/historical-mean pipeline versus frozen agent-selected pipeline. Both use the same deterministic pricing solver, origin-known fleet size, training cutoff and test dates. Identical current-component predictions are reused to avoid redundant fitting.
- Primary measure: remaining-supply RMSE at 90 days. Also record seven component errors, DNQ disagreement, conversion diagnostics and price deviation on identical non-DNQ dates within each path/horizon.
- Reference price: realized test components passed through training-only **current** demand curves. This is a diagnostic reference with a structural preference for current curves, not an independently observed optimal price. Price deviation cannot establish revenue improvement.

## Reproduce

From the repository root:

```sh
uv run python -m src.synthetic_robustness \
  --root experiments/synthetic_fleet_v1 \
  --frozen experiments/synthetic_three_way_v1/agent \
  --out experiments/synthetic_robustness_new
```

Use a fresh output directory. No API key is needed. `plan.json` is written before fitting and records dataset hashes, frozen-choice hashes, recipes, windows and runner hash. `predictions.csv` contains forecasts and actuals once per 90-day window; `pricing.csv` and `fold_results.json` include each horizon. `aggregate_results.json`, `REPORT.md`, and `EXECUTIVE_SUMMARY.md` contain final results. `status.json` confirms completion and zero API cost.

## Interpretation limits

The synthetic generator was calibrated on the same two historical years. More simulated rows broaden stress coverage but do not add independent historical evidence. The previous baseline42 pilot already exposed three January windows; those windows are included for comparability, so this is expanded robustness testing, not an entirely untouched holdout. No recipes were revised after those results.

Stress paths share seed42, so compare them against baseline42 as paired scenarios rather than count them as independent evidence. Forecasts can respond to newly available history at later origins; the agent itself does not replan. No fresh company data are available. Direct LLM forecasting and Gemini are not rerun in this offline experiment. A future provider comparison would need matched tools, budget, validation protocol and frozen test conditions.
