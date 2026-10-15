# GPT-5.5 adaptive research — run log

## October 14, 2026 — preparation, no paid execution

Objective: let GPT-5.5 choose experiments, features, model settings, ensembles and final selections; compare the resulting forecasting/pricing pipeline against current Prophet/seasonal recipes.

Completed: implemented research_experiments.py and research_agent.py, documented AGENTIC_RESEARCH.md, updated repository README. All 15 synthetic/offline tests pass, including real SDK tool dispatch without an API request. Existing fixed-search benchmark results are not results from this adaptive agent.

Latest request: explain the dollar cap, record work in a file and explain progress. User has expressed willingness to proceed, but the dollar limit is not yet agreed. Paid execution remains paused. No GPT-5.5 calls made by this adaptive research workflow; API spend from this workflow so far: $0.

## Cost controls — current state

Implemented limits: 36 distinct trials by default; 50 model turns; 2,500 output tokens per response; no automatic API retries. These limits do not impose a dollar budget. Dollar enforcement is NOT implemented yet.

Proposed initial budget: $10 of model API usage, pending user selection. Before execution, add and test a pre-request budget check that reserves the next request's input and maximum output allowance; stop when it cannot fit. If a strict bound cannot be established for a request, do not dispatch it. Record the pricing assumptions and distinguish application accounting from the provider's final invoice. Do not promise a billing-account cap.

Official GPT-5.5 standard prices checked October 14, 2026: $5 per million input tokens; $0.50 per million cached input tokens; $30 per million output tokens. Prompts above 272K input tokens incur higher rates (2x input, 1.5x output); regional processing adds 10%. Source: https://developers.openai.com/api/docs/models/gpt-5.5

Illustration only, not a run estimate: 1,000,000 uncached input tokens across short-context requests plus 100,000 output tokens costs $8 at standard rates. Conversation history is sent again on subsequent turns, so input usage accumulates. Local ML fitting does not incur an OpenAI model charge.

## Records to retain during execution

- Human-readable updates in this file: action, finding, decision, limitation, next step.
- audit.jsonl: recorded plans/revisions, tool activity, experiment attempts and outcomes, selection reasons.
- trials.json and validation CSVs: recipes, fold scores, predictions, failures and timings.
- frozen_choices.json: committed selections and agent-provided reasons.
- manifest.json: source/code hashes, dates, model and limits.
- usage.json: request/input/output totals; budget ledger to be added before paid execution.
- final_results.json, pricing.csv, predictions and report.md: independent comparison with the current engine.

Never log API credentials. Record actions and decision summaries, not private internal reasoning. Provider usage may be unavailable on failed requests, so cost accounting must handle uncertainty conservatively.

## Interpretation

The agent sees development data and validation evidence only. Final evaluation runs after selection is frozen. November 2025 is retrospective and already inspected in prior work, not a new untouched holdout. Better forecast accuracy or lower diagnostic price error does not prove higher revenue. Report both wins and regressions, including DNQ disagreements.

## Budget approved and enforced

User approved $4 maximum and requested minimum spend. Implemented pre-request token counting and conservative maximum-output reservations, standard-tier pricing, no retries and stop-on-uncertain-failure. All 21 offline tests passed. Preparing one run with 24 trials, up to 50 turns and 2,500 output tokens per response. Output folder: `gpt55_adaptive_2026-10-14`. No previous adaptive-run spend.

## Completed run — October 14, 2026

Completed October 14, 2026. No further API calls planned.

Conservative API accounting: **$2.8575 of $4 approved**. Cache discounts are ignored, so this is not an exact invoice. 47 model requests, 536,922 input tokens and 5,763 output tokens. 24 distinct trials, each evaluated on three folds; zero training failures.

## What actually happened

GPT-5.5 inspected training summaries, recorded its own experiment plan, ran the nine current baselines, then chose 15 additional model/curve trials. It tested rolling averages, Ridge, XGBoost and seasonal naive alternatives. It reviewed validation residuals and selected all nine components with recorded reasons. It did not use the available ensemble tool. The final evaluator ran only after these choices were frozen.

## Selected models and final results

| Component | Agent choice | Current RMSE | Agent RMSE | Error reduction |
|---|---|---:|---:|---:|
| aog_rate | rolling_mean | 0.03847 | 0.03377 | 12.2% |
| smx_rate | current | 0.06084 | 0.06084 | 0.0% |
| umx_rate | xgboost | 0.03035 | 0.03968 | -30.7% |
| cna_rate | rolling_mean | 0.01737 | 0.01243 | 28.4% |
| program_live_legs | current | 7.04035 | 7.04035 | 0.0% |
| non_program_live_legs | xgboost | 2.75031 | 3.11725 | -13.3% |
| daily_quote_count | current | 21.89147 | 21.89147 | 0.0% |

Positive reduction means better. Rate errors are fractions; multiply by 100 for percentage points.

## Interpretation

The agent-designed pipeline did not beat the current engine overall in this retrospective test. AOG and CNA improved, while UMX and non-program legs worsened. SMX, program legs and enquiries kept the current recipe and therefore have identical predictions.

The selected XGBoost recipes won on validation but did not generalize to November. This is evidence of validation-to-test instability, not proof that XGBoost or agents are intrinsically inferior. The lean search also differs from the earlier exhaustive registry: depth-2 boosting, different lag/window choices and log transforms for counts can produce different winners. It did not explore every model or parameter combination.

Remaining-supply proxy RMSE rose from 6.05565 to 6.20180 (+2.4%). DNQ disagreement rose from 60.7% to 67.9%. Status agreement improved from 17.9% to 21.4%, but that isolated improvement does not outweigh the other regressions.

On the same six non-DNQ dates, diagnostic price MAE rose from $2,074.72 to $2,995.03 (+44.4%) for the full agent pipeline. This six-date subset differs from the earlier fixed-search comparison; do not compare those MAEs across experiments without realigning dates.

This is a retrospective November 1–28, 2025 comparison against a diagnostic reference, not a true optimal-price label or a revenue trial. Keep the production engine unchanged. No additional paid runs are needed to state this result.

## Agent selection reasons

**aog_rate:** Rolling 28-day mean beat the current baseline on validation score (0.02790 vs 0.02893 RMSE) and review showed small fold biases, appropriate for noisy weakly autocorrelated AOG.

**smx_rate:** Current recipe remained best; ridge alternative was materially worse. Fold RMSEs were stable around 0.027-0.031 with only modest bias swings.

**umx_rate:** Conservative xgboost had the lowest validation score among tried UMX models (0.04920) and substantially reduced the current recipe's positive bias, with similar RMSE across folds.

**cna_rate:** Rolling 28-day mean improved over current (0.01531 vs 0.01655) and reduced overforecast bias for this sparse low-rate series; review showed stable fold MAE.

**program_live_legs:** Current recipe outperformed ridge and seasonal-naive alternatives by validation score; despite some fold/weekday bias, the tried simpler models had higher errors.

**non_program_live_legs:** Conservative xgboost clearly improved over current and ridge (score 2.218 vs 2.625/2.552) with low fold-to-fold RMSE variation and reduced underbias.

**daily_quote_count:** Current recipe had the best validation score; xgboost and ridge log-lag alternatives underforecasted later folds and were worse. Selected current despite residual bias because validation error was lower.

**quote_multiplier:** Shrink-half curve was best of all bounded candidates (score 0.12265 vs 0.15181 current_lowess and 0.14884 constant_one) and was stable across folds.

**conversion:** Isotonic curve slightly improved log loss and Brier over current exponential across all folds; constant curve was worse.

## Audit files

- `audit.jsonl`: plan, tool actions, trial outcomes, reviews and freeze event.
- `response_*.json`: visible agent tool calls and messages, excluding private reasoning.
- `trials.json`, `validation_*.csv`: all experiment recipes, scores and daily predictions.
- `frozen_choices.json`, `manifest.json`: final decisions, limits and data/code hashes.
- `budget.json`, `usage.json`: reservations and usage accounting.
- `report.md`, `final_results.json`, `pricing.csv`, `predictions_*.csv`: independent final evaluation.

Detailed artifacts are in `gpt55_adaptive_2026-10-14/`. Execution exited successfully. No more API calls made after final scoring.
