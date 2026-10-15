# Component model-selection experiment

Execution: deterministic runner invoking the same bounded tools as the optional LLM coordinator; no paid calls.
Validation: July 1–28, September 1–28 and October 1–28, 2025. Final test: November 1–28, 2025.
Choices frozen before final-test scoring. This is a historical evaluation, not a new prospective holdout.

| Component | Validation winner | Current test RMSE | Selected test RMSE | Error reduction |
|---|---|---:|---:|---:|
| aog_rate | rolling_mean | 0.03847 | 0.03377 | 12.2% |
| smx_rate | current | 0.06084 | 0.06084 | 0.0% |
| umx_rate | extra_trees | 0.03035 | 0.03209 | -5.7% |
| cna_rate | rolling_mean | 0.01737 | 0.01243 | 28.4% |
| program_live_legs | xgb_medium | 7.04035 | 6.52847 | 7.3% |
| non_program_live_legs | xgb_medium | 2.75031 | 2.79844 | -1.7% |
| daily_quote_count | xgb_medium | 21.89147 | 17.67981 | 19.2% |

Rates are fractions; multiply by 100 for percentage points. Positive reduction is better.

Curve selections: {"quote_multiplier": "shrink_half", "conversion": "isotonic"}

## Pricing diagnostics

| Pipeline | Supply-proxy RMSE | Status agreement | DNQ disagreement | Common-date price MAE |
|---|---:|---:|---:|---:|
| current | 6.056 | 17.9% | 60.7% | 3435.177921649135 (n=10) |
| selected_forecasts | 5.173 | 10.7% | 64.3% | 2483.7664378825716 (n=10) |
| selected_full | 5.173 | 10.7% | 64.3% | 2442.6943624705827 (n=10) |

No revenue or causal pricing improvement is established. The pricing reference uses actual component inputs and the current train-only demand curve.
The test does not choose a new winner after observing final results. The best validation candidate is not necessarily the best future model.
Final extracts, maturity approximations, mixed realized/quoted yields, fixed fleet productivity and enquiry/departure-date mismatch remain limitations.
