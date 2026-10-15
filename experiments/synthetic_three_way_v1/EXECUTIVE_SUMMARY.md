# Executive results — synthetic three-way pilot

**The current ML engine performed best in this pilot.** More synthetic history did not make direct GPT-5.5 forecasts or the agent-designed pipeline better overall. This is a simulator result, not a real-world revenue conclusion.

## Scope

- One baseline path: 3,652 synthetic daily observations and 232,609 enquiries, labeled 2026–2035.
- Six initial training years; four 90-day validation folds in 2032.
- Three final 90-day windows beginning January 1 in 2033, 2034 and 2035: 270 unique test days.
- Reported 14/28-day results are prefixes of the same forecasts, not separate runs.
- A new $4 budget was approved for this path only. All five generated datasets were pushed separately, but the other paths were not benchmarked.

## Primary 90-day results

| Approach | Supply RMSE | Change vs current | Diagnostic price MAE | DNQ disagreement |
|---|---:|---:|---:|---:|
| current | 3.594 legs | +0.0% | $2,090.56 | 31.1% |
| direct_llm | 4.696 legs | +30.7% | $3,337.07 | 46.7% |
| agent | 3.634 legs | +1.1% | $2,297.39 | 33.0% |

Higher error is worse. Price MAE uses the same 52 non-DNQ dates for all approaches; it measures distance from a diagnostic reference, not an observed optimal price. The current engine also had the lowest supply and diagnostic price error at 14 and 28 days.

## What the agent decided

The agent ran 20 validation trials, kept the current recipes for six daily targets and the quote multiplier, selected Ridge for SMX, and selected isotonic conversion. SMX RMSE improved from 0.02926 to 0.02863 (about 2.2%), but supply error rose 1.1% and diagnostic price MAE rose 9.9%. The selected Ridge model used 1,095 training days; full history was available, and the agent chose the shorter window.

The agent could inspect, plan, batch its chosen trials, review errors, blend and select. It did not use an ensemble in this run. Current recipes retained their original full-history behavior, regardless of unused recipe fields in audit records.

## Why the direct LLM struggled

Enquiry RMSE was 50.77 versus 17.69 for the current engine. Its overall enquiry bias was small, but its day-by-day pattern was wrong: it predicted about 96 enquiries on Saturdays and 91 on Sundays, versus actual averages of 42 and 40. It underpredicted Tuesdays/Wednesdays. This is consistent with poor weekday alignment, not simply a level bias. We cannot isolate the cause from one run.

To control cost, direct requests used chronological daily rows with implicit dates, low precision for rates and reasoning effort none. The agent used low reasoning effort. Thus this is not a definitive test of every possible prompt, calendar encoding or reasoning configuration. Changing the direct prompt after seeing these test outcomes would require a new evaluation to avoid tuning to the test.

## Cost and records

Conservatively accounted API cost: **$2.1438**, leaving **$1.8562** unused. There were 13 model requests: 10 for the agent and 3 direct forecasts. No additional paid calls were used for final scoring or documentation. Cached-input discounts are ignored in the ledger.

All numerical outputs passed independent pooled-RMSE, matched-price-sample, decision-agreement and budget checks. The 12 synthetic/comparison tests and 21 research/budget tests passed. API credentials and original operational data are excluded.

## Recommendation

Keep the current production engine. These results support further controlled experiments, not a replacement or revenue claim. Before spending more, improve explicit calendar encoding for direct forecasts, predeclare any changes, and test other seeds and stress scenarios. Synthetic data reflect their generator; performance gains must eventually transfer to genuinely unseen real observations.

See REPORT.md for every horizon, aggregate_results.json for metrics, pricing.csv and forecast_comparison.csv for independent calculations, plan.json for the protocol, budget.json for every reservation/call, and agent/ for the experiment audit and final choices.
