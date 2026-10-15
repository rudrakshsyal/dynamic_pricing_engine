# Tool-based model selection: methodology and results

## Outcome and execution status

Completed October 14, 2026. Local training evaluated eight candidates for each of seven daily targets and three candidates for each of two demand curves across three validation windows: 186 candidate/fold evaluations, with no recorded failures in the complete run.

**No paid calls were made.** The OpenAI Agents SDK coordinator is prepared; the completed experiment used a deterministic runner invoking the same experiment operations. These results measure ML model selection, not an incremental benefit from an LLM. Production pricing and the explanation UI remain unchanged.

The LLM's proposed role is to call bounded training/evaluation tools and summarize their scores. Python trains the models and chooses the lowest validation error. The coordinator cannot invent forecasts, execute arbitrary code, override the winner, or access final-test scores while selecting. This is a controlled experiment coordinator, not an autonomous search over every possible model.

## Data and time splits

Inputs are the existing processed fleet availability, flight-leg, daily enquiry and enriched quote parquet tables. Daily history covers 2024–2025. Four availability rates, program legs, non-program legs and enquiry counts are forecast separately. Source-file hashes, candidate registry, seed and implementation hash are saved in the manifest.

Expanding training windows end June 30, August 31 and September 30, 2025; each predicts the following 28 days (July 1–28, September 1–28, October 1–28). Candidate selection uses only those validation periods. Choices are frozen to disk before the final fit through October 31 and final evaluation on November 1–28.

Daily targets use all observations through each cutoff. Demand-curve training additionally requires quote date and departure date on or before the cutoff. Held-out curve rows require quote dates in the forecast window and departure by its end. Departure is only a maturity proxy: historical final extracts do not recreate exactly what was known at each cutoff. These are retrospective tests, not a previously untouched prospective holdout; original recipes were already developed on these historical years.

## Candidate models

Every daily target receives the same candidate registry:

- Current recipe: existing monthly averages for AOG/UMX, training mean for CNA, Prophet for SMX, program/non-program legs and enquiries, as implemented in `model_benchmark.py`.
- Seasonal naive: repeat the last observed week.
- Monthly mean: training-history mean for the target calendar month; overall mean fallback.
- Rolling mean: last 28 observed days.
- Ridge: standardized features, regularization alpha 10.
- Extra Trees: 150 trees, minimum leaf size 7, all features, seed 42.
- Shallow XGBoost: depth 2, 120 boosting rounds.
- Medium XGBoost: depth 4, 180 rounds.

Both XGBoost variants use squared-error objective, learning rate .04, minimum child weight 8, full rows/features, histogram trees and seed 42. No hyperparameters are changed after inspecting the final test.

ML features are lags 1/7/14/28 days, rolling means and standard deviations over 7/28 days, cyclical weekday/year-day and calendar month. Forecasts recurse using earlier predictions, never future actuals. Predictions are nonnegative; availability rates are capped at one. Each target's candidate is chosen by pooled RMSE across the three validation windows; exact ties favor registry order, starting with the current recipe.

Quote multiplier candidates: current LOWESS, constant one and half-strength LOWESS deviation from one. Selection uses held-out normalized quote-bin count MAE, weighted by available bins across folds. This evaluates an observational bin relationship, not causal elasticity; bins without observations are not treated as zero-volume days.

Conversion candidates: current exponential curve, constant eligible training conversion and monotonically decreasing isotonic regression weighted by training bin counts. Selection uses pooled quote-level log loss; Brier score is also reported. Evaluation uses eligible yields from $7,500 to $15,000; pricing still uses the existing $7,000 floor, so behavior below the scoring range is not validated by this metric.

## Final forecast results

Positive error reduction means lower RMSE. Rate errors below are percentage points; leg/enquiry errors are counts per day.

| Component | Validation selection | Current RMSE | Selected RMSE | Reduction |
|---|---|---:|---:|---:|
| AOG rate | 28-day mean | 3.847 | 3.377 | 12.2% |
| SMX rate | Current | 6.084 | 6.084 | 0.0% |
| UMX rate | Extra Trees | 3.035 | 3.209 | −5.7% |
| CNA rate | 28-day mean | 1.737 | 1.243 | 28.4% |
| Program legs | Medium XGBoost | 7.040 | 6.528 | 7.3% |
| Non-program legs | Medium XGBoost | 2.750 | 2.798 | −1.7% |
| Enquiries | Medium XGBoost | 21.891 | 17.680 | 19.2% |

The validation winner did not always generalize: UMX and non-program errors increased. Lag/calendar models may capture recent nonlinear patterns that the current recipes miss, but this experiment does not isolate which features caused the gains. The rolling-mean wins also show that extra complexity is not always useful.

The selected quote multiplier worsened final bin MAE from 0.1760 to 0.2075. Isotonic conversion slightly improved log loss from 0.17184 to 0.17041 and Brier score from 0.041695 to 0.041605, over 473 eligible rows. Do not re-select a curve based on these final results and then report it as untouched evaluation.

## Downstream pricing evaluation

Three arms separate effects: current forecasts/current curves; selected forecasts/current curves; selected forecasts/selected curves. All retain the existing supply arithmetic, productivity factor 1.06, price bounds and equilibrium solver. Fleet size for prediction is the last observed size. Non-program activity includes OD; no separate booked-OD correction is introduced.

The diagnostic reference supplies actual historical daily components to the same solver with the current train-only curve. It is **not an observed optimal selling price**, realized revenue, or a causal demand label.

| Metric | Current | Selected forecasts | Selected forecasts + curves |
|---|---:|---:|---:|
| Remaining-supply proxy RMSE, legs | 6.056 | 5.173 | 5.173 |
| Solver-status agreement with reference | 17.9% | 10.7% | 10.7% |
| DNQ disagreement with reference | 60.7% | 64.3% | 64.3% |
| Price MAE on same 10 non-DNQ dates, USD/EFT hour | 3,435 | 2,484 | 2,443 |

Supply RMSE improved about 14.6%, and comparable-date price MAE fell about 28.9% for the full selection. However, status agreement fell and DNQ disagreement increased. The ten-date price comparison excludes zero-supply/DNQ cases and cannot establish overall pricing superiority. Small supply errors near zero can change a discrete DNQ decision even when aggregate RMSE improves.

**Recommendation:** retain production models for now. Selected forecasts merit a broader shadow evaluation; the experiment does not support a wholesale replacement or a revenue-uplift claim. Compare more fixed origins/horizons, report uncertainty, diagnose near-zero capacity cases and improve as-of data/date alignment before operational decisions. Revenue improvement ultimately requires credible causal evaluation or a controlled business trial.

## Running and reviewing

Offline, no API key or paid calls:

```bash
uv run python -m src.model_selection --out experiments/component_selection_new
```

Optional coordinator, only when paid execution is explicitly approved and `OPENAI_API_KEY` is configured:

```bash
uv run python -m src.model_selection_agent \
  --out experiments/coordinator_new --model gpt-5.5 --allow-paid
```

The coordinator has two tools: `evaluate_component` and `freeze_selection`. It sees component names and aggregate validation scores, not raw customer rows. All components and all candidate folds must complete before freezing. Final evaluation runs outside the agent after it finishes. Model output is capped at 2,500 tokens per response and the run at 16 turns; these are not dollar caps. SDK tracing is disabled. This paid path has not been live-tested; local tests verify tool exposure without an API call.

The local XGBoost installation needed macOS OpenMP. A verified Homebrew runtime was downloaded into the chat workspace and loaded through `DYLD_LIBRARY_PATH`; no system installation was changed. For your normal environment, install the platform's OpenMP runtime (commonly `brew install libomp` on macOS) if XGBoost reports a missing `libomp.dylib`. The initial incomplete run was superseded after resolving this dependency, without changing candidates or tuning to final scores.

Outputs: `manifest.json`, `validation_scores.json` (every candidate/fold, failures and timing), `frozen_selection.json`, `final_results.json`, `final_predictions_*.csv`, `final_actuals.csv`, `final_pricing.csv`, `tool_audit.json` and `report.md`. Paid runs additionally save `coordinator.json` with summary and usage. Use a new output directory for each run to preserve evidence. Local data and generated experiment outputs are not committed.

Six synthetic/offline tests cover time separation, lag construction, all eight forecast implementations, maturity filtering, freeze guards and coordinator tool restrictions. Run `python -m unittest discover -s tests -p 'test_model_selection.py' -v` in the project environment.

Implementation: `src/model_selection.py` and `src/model_selection_agent.py`, reusing `src/model_benchmark.py`. Agent API reference: [OpenAI agent definition guide](https://developers.openai.com/api/docs/guides/agents/define-agents).
