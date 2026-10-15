# Three-way synthetic comparison — pilot protocol

## Scope and approval

User approved a **new $4 maximum** for one synthetic baseline path, with instructions to minimize spend. This is separate from the earlier $2.8575 adaptive research run. Use baseline_seed42 only; the other seeds and stress paths remain available for a later explicitly budgeted expansion. No Google API calls are involved.

Dataset: `experiments/synthetic_fleet_v1/baseline_seed42`, 3,652 simulated days and 232,609 simulated enquiries, calendar labels 2026–2035. These labels are not predictions of real future years. All source hashes and the protocol are recorded before paid execution in `experiments/synthetic_three_way_v1/plan.json`.

## Common time design

- Initial training begins January 1, 2026 and ends December 31, 2031 (six years).
- Four validation origins: December 31, 2031; March 31, June 30 and September 30, 2032. Each predicts 90 days.
- Agent selections freeze after validation and before any final outcomes are scored.
- Three final origins: December 31 of 2032, 2033 and 2034. Each predicts the next 90 days.
- Report the first 14, 28 and all 90 days of each forecast. Primary horizon: 90 days, giving 270 unique final-test days. Shorter horizons give 42 and 84 days; they overlap the 90-day forecasts and are not independent evidence.
- Refit on expanding observed history at each final origin. Later origins may use observations from earlier years, but cannot change frozen recipes using final scores.

This is a cost-conscious subset of the full 12-final-origin simulation plan; it does not claim all years were continuously forecast or all five paths evaluated.

## Approaches

1. **Current ML pipeline:** existing Prophet/seasonal/mean recipes refit on the full available training history; existing observational demand curves and equilibrium solver.
2. **Direct GPT-5.5:** three independent paid calls, one per final origin. Receives all daily training rows in chronological order (rates rounded to four decimals) and training-only quote/conversion bins. Returns seven 90-value forecast arrays and two 17-point curve arrays. No forecasting tools. Reasoning effort none to fit the pilot budget; this configuration is not a claim about the best possible direct LLM performance. Output is strictly checked for dimensions, finiteness and bounds. No automatic correction or fallback.
3. **GPT-5.5 agent with ML tools:** chooses its plan, inspections, model recipes/settings, validation trials, potential ensembles, error reviews and final choices. At most 20 trials and 12 model turns; related trials are batched in one call to reduce overhead. Reasoning effort low. Full history is available, while the agent can deliberately choose a shorter training window (180–3,652 days). No final-test tool or observations are exposed to it.

The agent has the current recipe as a required baseline for each component, but does not follow a fixed grid or automatically choose the minimum score. Its final choices and reasons are preserved. The underlying forecast tools, not the LLM text, generate the agent pipeline's numerical forecasts.

## Fairness and metrics

All approaches forecast identical dates from the same eligible historical period. Direct LLM inputs retain all daily rows, with small rate rounding; ML tools use full precision. Direct and agent configurations use different reasoning effort and information interfaces, so this compares specified end-to-end pipelines, not a pure model architecture ablation. Adaptive search gets validation feedback; the direct prompt is fixed and not tuned on final outcomes. The experiment does not isolate agent benefit from extra ML training effort.

Pool RMSE by sample-weighted squared errors, not by averaging fold RMSE. Report MAE and bias alongside RMSE for every component and the remaining-supply proxy. Report solver-status agreement, DNQ disagreement and diagnostic price MAE. Price MAE uses the identical non-DNQ date intersection across all three approaches and the reference, separately for each horizon. Unpaired dates still contribute to decision metrics.

The reference price uses actual simulated daily inputs and the current training-only curve. It is not a true optimal price or a revenue label. The generator uses calendar regression and resampled historical residual blocks, so it may favor seasonal/statistical predictors and cannot add genuine business information beyond the two calibration years. Results must not be advertised as real-world revenue uplift.

## Execution, cost and files

`src/synthetic_benchmark.py` is separate from the original historical benchmark and old agent runner. It supports the new 90-day protocol without changing historical run outputs. `Recipe.train_days` now allows up to 3,652 days while retaining the 730-day default for compatibility.

First run offline preparation, then paid execution only when authorized:

```bash
uv run python -m src.synthetic_benchmark \
  --root experiments/synthetic_fleet_v1/baseline_seed42 \
  --out experiments/synthetic_three_way_new
uv run python -m src.synthetic_benchmark \
  --root experiments/synthetic_fleet_v1/baseline_seed42 \
  --out experiments/synthetic_three_way_new --allow-paid
```

The shared `BudgetedResponses` guard reserves each request before dispatch and blocks spending above $4. Both the agent and direct calls use the same ledger. Standard-tier GPT-5.5 rates are conservatively applied without cached-input discounts; maximum input/output charges are reserved first. No automatic retries. An existing paid ledger prevents restarting/resetting the run. No additional calls are made to write the final report.

Results live separately under `experiments/synthetic_three_way_v1`: protocol, per-origin predictions and direct prompts/outputs, per-fold/pooled metrics, shared price table, budget ledger, visible responses, agent trial/audit logs and frozen choices. Source dataset files remain under the separate `synthetic_fleet_v1` directory. API keys and original operational datasets are excluded.

Six comparison tests cover forecast validation, long-history eligibility, temporal separation, tool exposure and direct-input construction. The six synthetic-data tests and 21 agent/budget tests also passed before paid execution.

## Completed outcome

The run completed for $2.143795 conservatively accounted. Current ML supply RMSE was 3.594, direct GPT-5.5 4.696 and the agent pipeline 3.634 on the primary 90-day test. Current ML also had the lowest diagnostic price error at all three horizons. See [executive results](../experiments/synthetic_three_way_v1/EXECUTIVE_SUMMARY.md) and [full horizon report](../experiments/synthetic_three_way_v1/REPORT.md). No production models were replaced.
