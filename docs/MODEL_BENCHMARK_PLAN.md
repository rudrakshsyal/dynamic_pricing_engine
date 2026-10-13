# Current models versus LLM forecasts

## Objective and decision rule

Test whether LLM-produced forecasts improve this fleet's forecasts and pricing inputs. Do not replace the operating pipeline until evidence supports a change. No paid calls were authorized or made during initial implementation.

There are two distinct questions:

1. Which method predicts held-out observations more accurately? Use forecast error, conversion scoring, invalid-output frequency, latency and token usage.
2. Which price earns more revenue? Historical forecasts alone cannot establish this. A new price has no observed counterfactual sale outcome. Pricing differences and agreement with a model-based reference are diagnostics, not proof of better pricing.

## Scope

| Component | Current recipe refitted per cutoff | LLM replacement |
|---|---|---|
| AOG rate | Calendar-month mean | Daily rate forecasts |
| SMX rate | Prophet, annual seasonality, changepoint prior 0.05 | Daily rate forecasts |
| UMX rate | Calendar-month mean | Daily rate forecasts |
| CNA rate | Training mean | Daily rate forecasts |
| Program / non-program legs | Prophet, weekly + annual, changepoint prior 0.1 | Daily leg forecasts |
| Enquiries | Multiplicative Prophet, weekly + annual, prior 0.05 | Daily enquiry forecasts |
| Quote-count curve | LOWESS, frac 0.5, normalized at $10,784 | Multiplier grid, normalized identically |
| Conversion curve | Nonnegative exponential fitted to supported price bins | Conversion-probability grid |

The LLM receives all training daily values for the seven targets and historical aggregated quote/conversion bins in one structured request per cutoff. It predicts jointly. The current recipes use each target's series separately; this compares systems with the same available historical dataset, not identical model architectures. Bins use the same filters as the notebook. Records are restricted to quote and departure dates at or before the cutoff to reduce immature outcome leakage.

The deterministic supply arithmetic and bounded solver remain shared. Fixed policy inputs (43 or latest known fleet size, 1.06 legs per tail, bounds, cancellation lookup) are not learned LLM replacements. The separate existing-OD deduction is zero as in the current saved run. This does not estimate a cancellation model because there is no as-of booked-leg inventory in the benchmark. The app's existing saved outputs are never overwritten.

## Execution plan

1. **Inventory and freeze.** Inspect current notebook recipes, historical coverage and saved schemas. Record source hashes and benchmark code hash.
2. **Historical backtest.** At each cutoff, use only preceding daily observations. Refit current recipes and a repeat-last-week baseline. Default cutoffs: June 30, September 30, November 30, 2025; horizon: 14 days each. These 42 days form a small retrospective pilot, not a production certification.
3. **Prepare LLM inputs offline.** Save requests without held-out targets. Use structured output with dates, nonnegative counts, bounded rates and a fixed yield grid. Persist model responses, usage and latency by request hash. Refusals/invalid outputs are failures, not silent baseline substitutions.
4. **Run LLM pilot when authorized.** Start with one cutoff. Review actual token usage and errors before expanding. There is no automatic LLM retry in this benchmark. `--max-calls` caps candidate origins, `--max-output-tokens` caps each response. These are not a guaranteed dollar budget. Dollar cost depends on model pricing; token usage is recorded for reconciliation.
5. **Ablations.** Compare current system, seasonal-naive forecasts, LLM forecasts with current curves, current forecasts with LLM curves, and full LLM replacement. One LLM request supplies both daily forecasts and curves; the variants reuse it.
6. **Measure.** Per target and cutoff: MAE, RMSE, signed bias and WAPE (undefined for an all-zero target). Rates are fractions, so multiply errors by 100 for percentage points. Evaluate conversion Brier score and log loss on eligible held-out rows, and normalized quote-bin shape MAE as a descriptive diagnostic. Report row/bin coverage.
7. **Inspect pricing.** Run all candidates through the same supply formula and bounded solver. Compare DNQ disagreement, decision-status agreement and yield differences against a reference using realized daily components with the train-only current curve. DNQ has no sellable price and is excluded from price MAE, with paired sample counts reported. This reference favors the current curve structurally; it cannot rank causal revenue performance.
8. **Decide next experiment.** Only compare fully completed, identical folds. If the pilot warrants it, preregister more origins/horizons, repeat LLM runs to assess variability, and evaluate a genuinely future holdout. For revenue claims, design an approved shadow trial followed by a controlled pricing experiment with revenue, margin, capacity and customer-impact measures.

## Commands

From the repository root, run the offline benchmark (no API key or network calls):

```bash
uv run python -m src.model_benchmark --out /tmp/dpe-benchmark
```

Review `report.md`, `aggregate_metrics.json`, `results.json`, per-candidate predictions, prepared requests, and `pricing_diagnostics.csv` in that output folder. Keep these local: request files contain historical business aggregates. Use a separate output directory for each experiment; repeated runs in the same directory replace reports and baseline predictions while reusing matching LLM cache entries.

Later, only when paid calls are authorized, run a one-cutoff pilot:

```bash
uv run python -m src.model_benchmark --out /tmp/dpe-llm-pilot \
  --origins 2025-11-30 --horizon 14 \
  --llm --allow-paid --model gpt-5.5 --max-calls 1 --max-output-tokens 8000
```

Without `--allow-paid`, `--llm` only uses an existing matching cache. Missing/invalid responses are marked incomplete and produce exit code 2. API key comes from `OPENAI_API_KEY`; the script does not automatically load `.env`. No customer IDs, airport IDs or raw quote rows are sent, only the numeric histories/bins in the saved request. Output is not stored as an OpenAI response (`store=False`); other API retention policies still apply.

## Limits that matter

- Processed daily actuals end on December 31, 2025. Jan–May 2026 saved predictions have no matching actuals in these processed tables.
- The original recipes were developed using 2024–2025, so these folds are not an untouched holdout for model selection. This is a retrospective comparison with frozen recipes.
- Historical files are final extracts, not archived as-of snapshots. Departure maturity is only a proxy for when final booking status became known. Late corrections and full-history deduplication can still leak information.
- Conversion uses mixed quoted/realized final yield and excludes missing-yield cases. It is observational and does not estimate a causal response to changing prices.
- Quote counts use enquiry date while capacity uses departure date. The benchmark preserves that existing mismatch for comparability.
- The normalization yield and 1.06 capacity factor are fixed existing-engine constants, not refit each fold; their historical provenance is not isolated.
- The 14-day pilot does not establish 151-day forecast quality. Price-grid interpolation also differs from the current exponential conversion curve between points; this is part of the tested replacement.
- Common count/rate clipping is applied to conventional outputs. LLM outputs outside the required bounds are rejected. Availability-component sums are not forced to sum to one, preserving current-engine arithmetic.
- No LLM results means no LLM winner can be declared. A low error against an internal price reference does not establish revenue optimality.

## Button reliability changes

The UI now keeps a persistent async event loop instead of closing it after each click. Both workflows can make one additional correction attempt after output-validation failure, retaining retrieved evidence. Provider failures are not retried by this application wrapper (the underlying SDK may have its own transport retry policy). The UI discloses the possible correction call. Tests exercise repeated invocations, correction success, correction exhaustion and provider failure. These address plausible causes of repeat clicks; a live check is still needed to confirm the reported symptom is resolved.
