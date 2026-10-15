# Dynamic Pricing Engine

A supply–demand equilibrium dynamic pricing engine for **one NREG Challenger fleet**, developed as a notebook-based prototype. It combines aircraft availability, committed flight demand, quote-volume forecasts, and estimated price response to recommend a fleet-level yield for each departure date.

The business goal is to produce a **pricing recommendation grid for fleet pricing managers and revenue leadership**: a date-by-date view of remaining capacity, expected demand, recommended yield, and pricing status to support fleet pricing decisions.

This repository is a learning and portfolio rebuild of an earlier production dynamic pricing project at Vista Tech LLC (FLYXO), as described in the project handoff. The rebuild uses anonymised data. Production deployment history and impact are separate from the local notebook results reported here.

The current analysis focuses on Challenger 300 and Challenger 350 aircraft, with North America departure filters in the flight-leg and quote pipelines. The notebooks refer to this scope as **NREG US**. Historical analysis covers 2024–2025, and the saved forecast run covers **January 1–May 31, 2026**.

**Current status:** nine modeling notebooks feed a local Streamlit pricing interface with charts, an on-demand revenue brief, and read-only follow-up chat. An isolated benchmark compares the existing forecasts with LLM replacements. Historical inputs and saved forecast datasets must be supplied locally. `main.py` remains a greeting scaffold; use `app.py` for the interface or the module commands below.

## Business objective and intended users

For a given departure date, how much fleet capacity remains available for on-demand bookings, and what yield would bring expected bookings into line with that capacity?

The project was initiated to answer this question for a single NREG Challenger fleet by equating forecast supply with expected demand. Fleet pricing managers are the intended users of the daily recommendation grid; revenue leadership is the intended audience for reviewing the fleet's capacity constraints and pricing recommendations across dates.

The implemented solver generates the underlying grid as a table with one row per date:

| Grid field | Decision context |
| --- | --- |
| Departure date | The date being priced |
| Remaining OD supply | Forecast capacity available for on-demand bookings |
| Forecast quote volume | The modeled inquiry-volume input to demand |
| Recommended yield ($/EFT hour) | The clearing yield, or the configured floor/ceiling when a crossing is unavailable |
| Expected bookings at that yield | Demand implied by the price-response model; zero is used as a marker on DNQ rows |
| Pricing status | Whether the date is solved, at a pricing bound, flagged do-not-quote, or requires error review |

The repository includes this generated-table workflow and visualizations. A deployed manager-facing grid and integration into operational pricing decisions remain outside the checked-in implementation.

Here, **yield** means revenue per estimated flight-time hour, expressed in the notebooks as **$/EFT hour**. The solver finds a supply–demand clearing yield within configured bounds. Clearing refers to expected bookings, not a guarantee that every leg sells. Revenue or profit optimality would require additional assumptions about price response, flight duration, costs, and capacity; the current solver does not directly optimise those objectives.

## What has been implemented

- **Availability analysis:** daily fleet aggregation, maintenance and crew-unavailability rates, integrity checks, seasonal patterns, and autocorrelation diagnostics.
- **Availability forecasting:** comparisons of monthly seasonal means, ARIMA, Prophet, TBATS, and a constant crew-unavailability rate; selected forecasts are converted into usable aircraft and live-leg capacity.
- **Flight-leg analysis:** separation of program, non-program, cancelled, and ferry legs; daily aggregation; cancellation rates by booking lead time.
- **Committed-demand forecasting:** separate Prophet models for program and non-program live legs, evaluated against monthly-mean baselines.
- **Residual supply calculation:** a reusable function that subtracts forecast consumption and cancellation-adjusted existing on-demand bookings from raw capacity.
- **Quote preparation:** lifecycle deduplication, booking labels, quoted yield calculation, and recovery of booked yields from flight revenue.
- **Quote forecasting:** Prophet with weekly and yearly multiplicative seasonality.
- **Price-response estimation:** a normalized LOWESS quote-count curve and an exponential conversion-probability curve.
- **Daily pricing solver:** bounded root finding, floor/ceiling handling, and a do-not-quote signal for dates with zero residual capacity.
- **Saved visualizations:** quote forecasts, elasticity curves, solver recommendations, and explanatory supply/demand dashboards.
- **Revenue interface:** capacity waterfall, demand-versus-capacity chart, and short explanations with expandable evidence.
- **Read-only agent and chat:** OpenAI Agents SDK tools bound to one date and evidence snapshot, validation checks, and draft data-team questions.
- **Model benchmark:** rolling-origin refits, optional structured LLM forecasts and curves, component error metrics, and pricing diagnostics.
- **Tests:** synthetic evidence, solver branches, SDK wiring, UI interactions, bounded correction attempts, benchmark validation and caching.

## Data overview

The notebooks read three CSV files from `data/raw/`. The project handoff identifies these as anonymised data used for a rebuild of the Vista/FLYXO pricing project. The raw extraction and anonymisation procedures are not documented here. Raw data is not redistributed, and no public dataset download is provided.

The counts below come from saved notebook outputs, not a fresh execution against the source files.

| Dataset | What a row represents | Recorded scope and size |
| --- | --- | --- |
| `availability_data_2024_2025_2026.csv` | An aircraft's daily availability/status record | 31,469 rows and 17 columns after filtering to 2024–2025; aggregated to 731 daily fleet records |
| `legs_data_2024_2025_2026.csv` | A flight-leg record with schedule, booking, status, aircraft, route, and revenue information | 65,459 raw rows; 50,095 rows after the 2024–2025, North America departure, and Challenger fleet filters; 731 daily aggregates |
| `quotes_data_2024_2025_2026.csv` | A quote-leg lifecycle/status record; multiple rows can describe the same quote | 220,619 raw rows; 182,965 filtered history rows; 47,400 unique quote legs after deduplication; 731 daily aggregates |

Although the filenames include 2026, the historical modeling tables are filtered to 2024–2025. Quotes are filtered by **quote creation date**, while legs are filtered by **scheduled departure date**. A quote created in the historical window can request a later departure.

### Important fields and derived measures

| Data | Fields used | Meaning/use |
| --- | --- | --- |
| Availability | `DATE_DAY`, `FLEET_MODEL`, `AIRCRAFT_DAILY_STATUS` | Daily observation date, aircraft model, and operational status |
| Availability | `MAINTENANCE_AIRCRAFT_ON_GROUND_COUNT`, `MAINTENANCE_SCHEDULED_COUNT`, `MAINTENANCE_UNSCHEDULED_COUNT`, `CREW_NOT_AVAILABLE_COUNT`, `TOTAL_MAINTENANCE_COUNT`, `DELIVERED_COUNT` | Counts aggregated into fleet availability and unavailability rates |
| Legs | `LEG_ID`, `TAIL_NO`, `FLEET_MODEL`, `DEP_MACRO_REGION` | Flight/aircraft identifiers and fleet/geographic scope |
| Legs | `SCHEDULED_DEP_TIME`, `BOOKING_DATE`, `ORDER_TYPE`, `LEG_STATUS`, `IS_FERRY` | Departure date, booking lead time, program classification, cancellation status, and live-versus-ferry classification |
| Legs | `ORDER_ID`, `DEPARTURE_ICAO`, `ARRIVAL_ICAO`, `REVENUE`, `ESTIMATED_FLIGHT_TIME` | Order/route matching and realized revenue per flight-time hour |
| Quotes | `QUOTE_LEG_ID`, `QUOTE_CREATE_DTTM`, `SCHDL_DEPARTURE_DTTM`, `QUOTE_STATUS_NM` | Quote identity, inquiry/departure timing, and booking label |
| Quotes | `FLEET_NAME`, `DEP_MACRO_REGION`, `GV_ORDER_ID`, `DEP_ICAO_CD`, `ARR_ICAO_CD` | Scope filters and matching to flight-leg revenue |
| Quotes | `REVENUE`, `EST_FLIGHT_TIME_VAL` | Quoted yield: revenue divided by estimated flight-time hours |

**Terminology:** AOG = aircraft on ground; SMX = scheduled maintenance; UMX = unscheduled maintenance; CNA = crew not available; OD = on demand; DNQ = do not quote. A “tail” is an aircraft. “Callout” is lead time in days.

### Preparation rules

- Availability counts are aggregated by day and checked so delivered aircraft plus the four unavailability buckets equal total aircraft. Saved outputs report zero count/rate integrity violations.
- Program consumption comprises non-cancelled live legs with `ORDER_TYPE == "Program"`. Non-program consumption comprises all other non-cancelled live order types, including on-demand activity. Ferry legs are excluded from these live-leg series.
- Cancellation rates are calculated across live legs by callout bucket: **17.14%** for 0–7 days, **17.83%** for 8–30 days, **23.27%** for 31–90 days, and **33.21%** for 91+ days.
- Quote histories are grouped by `QUOTE_LEG_ID`. The earliest quote date and maximum non-null revenue are retained; `booked = 1` if any history row is `Confirmed`. This is an ever-confirmed label, not proof of a completed flight.
- The saved quote sample contains **3,860 booked quotes out of 47,400**, or **8.14%**. Initial quoted yield is missing for 3,896 quotes.
- Booked quotes are enriched using landed, revenue-positive live legs matched on order and route. Saved outputs show yield recovered for **2,165 booked quotes (56.1%)**; 1,695 booked quotes still lack yield.

## How the pipeline works

```text
Aircraft availability → availability forecasts ──┐
Flight legs → committed-leg forecasts ───────────┼→ residual OD supply ─┐
Flight legs → cancellation lookup ───────────────┘                      │
                                                                      ├→ daily yield + status
Quote histories → daily quote forecast ─────────┐                      │
Quotes + flight revenue → price-response curves ┴→ expected bookings ───┘
```

### 1. Forecast available supply

The final availability forecast uses monthly seasonal means for AOG and UMX, Prophet for SMX, and a constant training-period mean of approximately 1.84% for CNA. The saved run assumes **43 aircraft** and **1.06 live legs per delivered aircraft**:

```text
delivered_tails = 43 × (1 − AOG_rate − SMX_rate − UMX_rate − CNA_rate)
raw_leg_supply = delivered_tails × 1.06

OD_supply = max(0,
    raw_leg_supply
    − forecast_program_live_legs
    − forecast_non_program_live_legs
    − current_OD_bookings × (1 − cancellation_rate)
)
```

`src/supply.py` selects the cancellation rate using days from the solve date to departure. The saved supply-validation run uses a solve date of `2025-12-31` and an empty current-bookings dictionary.

### 2. Estimate expected bookings at a candidate yield

Quote volume is forecast with Prophet. Notebook 08 estimates a LOWESS multiplier from quote counts in yield bins, normalized at the historical median yield of **$10,784/EFT hour**, and fits conversion probability as:

```text
conversion_probability(Y) = a × exp(−b × Y / 1000)
expected_bookings(Y, date) = forecasted_quotes(date)
                           × quote_count_multiplier(Y)
                           × conversion_probability(Y)
```

The saved conversion fit has `a ≈ 0.2297`, `b ≈ 0.173633`, and **R² = 0.9731** on the fitted yield-bin averages. Conversion fitting excludes bin centers below $7,500. The LOWESS curve has 16 points spanning $7,250–$14,750 and uses boundary values outside that range.

The solver uses **absolute conversion probability** to express demand in expected bookings. Notebook 08 also displays normalized conversion response; that plotted multiplier alone does not convert quotes into bookings. These estimated response curves describe historical associations, not experimentally established causal price effects.

### 3. Solve for the daily yield

Notebook 09 uses SciPy's `brentq` to solve `expected_bookings(Y) = OD_supply` between **$7,000 and $15,000/EFT hour**, with $1 root tolerance.

| Status | Condition | Output behavior |
| --- | --- | --- |
| `DNQ_zero_supply` | Residual supply is zero | Sets yield to $15,000 and `d_at_yield` to zero as a DNQ marker |
| `demand_below_floor` | Demand at $7,000 is no greater than supply | Uses the $7,000 floor |
| `demand_above_ceiling` | Demand at $15,000 is still at least supply | Uses the $15,000 ceiling |
| `solved` | Demand crosses supply within the bounds | Returns the clearing yield |
| `error: ...` | Root finding raises `ValueError` | Falls back to $10,784 and records the error |

The output file, `data/processed/optimal_yield_per_date.parquet`, contains `date`, `od_supply`, `forecasted_quotes`, `optimal_yield`, `d_at_yield`, and `solver_status`. A DNQ row's ceiling value is a status marker, not a recommendation to accept bookings at that price.

## Recorded evaluation and results

Availability and leg models use **January 1, 2024–September 30, 2025** for training (639 days) and **October 1–December 31, 2025** for validation (92 days). The saved forward supply forecasts use those fitted models; the code does not refit them on the entire historical period. Quote forecasting uses all 731 days of 2024–2025 and reports no 2026 actuals for evaluation.

| Component | Model used in final forecast | Validation RMSE | Monthly-mean baseline RMSE |
| --- | --- | --- | --- |
| AOG rate | Monthly seasonal mean | 0.047174 | 0.047174 |
| SMX rate | Prophet | 0.044455 | 0.054457 |
| UMX rate | Monthly seasonal mean | 0.050433 | 0.050433 |
| CNA rate | Constant mean | 0.017446 | 0.016823 |
| Program live legs/day | Prophet | 7.0446 | 7.5173 |
| Non-program live legs/day | Prophet | 2.8464 | 2.8244 |

Rate errors are in fraction units; leg errors are in legs/day. SMX improves RMSE by **18.4%** and program legs by **6.3%** over their baselines. Non-program Prophet and constant CNA do not beat their monthly baselines. AOG ARIMA and UMX Prophet/TBATS were explored but are not used in the final exported availability forecast.

The saved January–May 2026 run reports:

- **151 dates**, with mean raw capacity of 31.08 live legs/day and mean residual OD supply of 0.41 legs/day after clipping.
- Mean quote forecast of **67.6 quotes/day**.
- **120 DNQ dates**, **22 solved dates**, **8 floor dates**, and **1 ceiling date**.
- On solved dates, mean yield of **$13,139/EFT hour**, ranging from **$10,566 to $14,936**.

These are stored model outputs, not observed operational outcomes or evidence of revenue uplift. The high share of zero-supply dates makes supply assumptions and category overlap particularly important to validate.

## Repository guide and execution order

| Order | File | Purpose and main generated artifacts |
| --- | --- | --- |
| 1 | [01_eda_availability.ipynb](notebooks/01_eda_availability.ipynb) | Availability EDA → `avl_fleet_daily.parquet` |
| 2 | [02_models_availability.ipynb](notebooks/02_models_availability.ipynb) | Model comparison → `jan2026_may2026_availability_forecast.parquet`, `models/availability_models.pkl` |
| 3 | [03_eda_legs.ipynb](notebooks/03_eda_legs.ipynb) | Leg/cancellation EDA → `legs_fleet_daily.parquet`, `cancellation_lookup.json` |
| 4 | [04_models_legs.ipynb](notebooks/04_models_legs.ipynb) | Committed-leg forecasts → `jan2026_may2026_legs_forecast.parquet`, `models/legs_models.pkl` |
| 5 | [05_supply_validation.ipynb](notebooks/05_supply_validation.ipynb) | Calls the supply module → `jan2026_od_supply.parquet` (contains January–May despite its name) |
| 6 | [06_eda_quotes.ipynb](notebooks/06_eda_quotes.ipynb) | Quote EDA and revenue enrichment → `quotes_deduped.parquet`, `quotes_deduped_enriched.parquet`, `quotes_fleet_daily.parquet` |
| 7 | [07_model_quotes.ipynb](notebooks/07_model_quotes.ipynb) | Quote forecasting → `jan2026_may2026_quotes_forecast.parquet` |
| 8 | [08_elasticity_curves.ipynb](notebooks/08_elasticity_curves.ipynb) | Price-response fitting → `elasticity_params.json` |
| 9 | [09_solver.ipynb](notebooks/09_solver.ipynb) | Daily recommendations → `optimal_yield_per_date.parquet` |

Unless otherwise noted, generated data artifacts are written under `data/processed/`. Raw data, Parquet files, and fitted pickle models are not present in the checked-in tree.

### Setup

The project declares **Python 3.14 or later** and uses **uv**, with dependencies recorded in `pyproject.toml` and `uv.lock`. Principal libraries include Polars, pandas, NumPy, Prophet, statsmodels, TBATS, SciPy, and Plotly. SciPy is imported by the notebooks but is not explicitly listed as a direct project dependency.

```bash
git clone https://github.com/rudrakshsyal/dynamic_pricing_engine.git
cd dynamic_pricing_engine
uv sync --locked
mkdir -p data/raw data/processed models
```

Supply the three CSV files listed above under `data/raw/`, then launch Jupyter from the notebook directory so `../data/...` paths resolve correctly:

```bash
cd notebooks
uv run jupyter lab
```

Run the notebooks in the numbered order, using the project environment as the kernel. Review the reproduction issues below first; this is not yet a verified clean-run pipeline. The full notebook pipeline has not been verified from a clean checkout. The separate benchmark has been run against locally available processed historical tables.

Once upstream artifacts exist, the supply function can also be called from the repository root:

```python
from pathlib import Path
from src.supply import compute_od_supply

supply = compute_od_supply(
    processed_dir=Path("data/processed"),
    solve_date="2025-12-31",
    current_od_bookings={},
)
print(supply.head())
```

### Visualizations

Download or clone the repository and open the HTML files in a browser:

- [Quote forecast](notebooks/07_quotes_forecast.html)
- [Elasticity curves](notebooks/08_elasticity_curves.html)
- [Solver recommendations](notebooks/09_solver.html)
- [Supply overview dashboard](supply_dashboard.html)
- [Demand overview dashboard](demand_side_dashboard.html)

The root-level dashboards are explanatory presentations with embedded examples. Their model descriptions and January-only figures differ from the executable notebooks: for example, the supply dashboard mentions XGBoost and a maintenance-schedule hybrid, while the checked-in forecast code uses Prophet and the baselines described above. Use notebook code and recorded outputs for implementation details.

## Design intent versus current implementation

The project handoff provides business context and an earlier January-only snapshot. Where it differs from the current executable code, this README describes the code:

| Topic | Handoff / design intent | Current repository |
| --- | --- | --- |
| Horizon | January 2026; 16 DNQ, 10 solved, 5 floor dates | January–May 2026; 151 dates with the results reported above. Earlier January figures are not a fresh validation of this run. |
| Non-program consumption | Non-program **non-OD** legs, with existing OD bookings deducted separately | All non-program live legs, including OD, are forecast; the default existing-OD input is empty. Category definitions need reconciliation. |
| Non-program model | Seasonal mean | Notebook 04 exports Prophet predictions even though the baseline has slightly lower validation RMSE. |
| Environment | Python 3.12 and MLflow mentioned | Project metadata requires Python >=3.14; MLflow is not declared as a dependency. |
| Pricing ceiling | Earlier chart housekeeping pending | Notebook 09 already defines a $15,000 ceiling. |

The intended next iteration should first define the grid's solve date, departure-date horizon, and mutually exclusive commitment categories. Then align expected **remaining** demand to each departure date using booking lead times and information available at the solve date.

## Current limitations and next steps

- **Reproduction:** notebook 06 loads `df_legs_raw` but references an undefined `df_legs_raw_sample` during revenue enrichment. Resolve that variable and confirm the intended scope before a clean run. Some day-of-week plots use a 0–6 index against Polars weekday values of 1–7.
- **Time alignment:** demand is forecast by quote-creation date, then joined directly to supply by departure date. A booking-lead-time mapping is needed to establish departure-date demand properly.
- **Supply accounting:** non-program forecasts already include historical on-demand legs. Define how additional current OD bookings relate to that forecast before using a nonempty bookings dictionary, to avoid overlapping consumption. Forecast aircraft count and productivity are fixed assumptions.
- **Model validation:** the original quote notebook lacks a recorded holdout evaluation; the separate benchmark now evaluates historical quote forecasts. The conversion R² measures fit to historical binned data. Missing 2026 actuals do not prevent rolling-origin backtests within 2024–2025. Keep future booking statuses and realised revenue out of features available at each historical solve date. Forecast accuracy can be backtested; historical realised revenue alone cannot establish the revenue that a different pricing policy would have earned.
- **Price-response assumptions:** booked and unbooked yields come from different sources, and 43.9% of booked quotes still lack yield. Dropping these bookings can distort both the conversion level and curve shape; the direction and size of bias need assessment. The quote-count curve measures observed counts per price bin, which does not establish how inquiry volume changes when price changes. Compare a constant quote-count multiplier of 1 with LOWESS, and test conversion fits restricted to the operating price window before choosing a revised model.
- **Configuration consistency:** notebook 08 uses a $6,000 plotting/parameter floor while notebook 09 uses $7,000. Its normalized composite-demand plot also differs from the solver's booking-unit formula. Some labels and filenames still say January despite the 151-day horizon.
- **Operationalization:** a local UI, evidence checks, chat and tests are implemented. A deployed service/API, automated retraining, archived as-of datasets and a verified end-to-end notebook rebuild remain future work. A regional origin–destination grid is deferred; the current outputs have one fleet/date scope.

## Run the revenue interface

```bash
uv sync --locked
uv run --with "streamlit==1.58.0" streamlit run app.py --server.address 127.0.0.1
```

Set `OPENAI_API_KEY` in the launching terminal to enable **Explain** and **Ask about this date**. Neither entry point automatically loads `.env`. The default model is `gpt-5.5`; choose a model available to your API project in the sidebar. Charts and calculations work without a key. Only clicking Explain or submitting a question starts a workflow; an invalid answer may trigger one additional correction attempt. These model calls incur API charges.

Supply the following local evidence files under `data/processed/`:

- `optimal_yield_per_date.parquet`
- `jan2026_od_supply.parquet`
- `jan2026_may2026_quotes_forecast.parquet`
- `elasticity_params.json`

The adapter also reads literal constants from `notebooks/09_solver.ipynb` without executing it. The interface reconstructs saved calculations, not a historical execution trace. It never changes prices or trains models.

The brief checks tool coverage, citations, length, numerical grounding and selected wording rules. These checks do not prove every claim correct. Chat retrieves the same fixed evidence, retains up to four recent exchanges as context, and clears when the date, model or snapshot changes. Unsupported questions can produce a draft for the data team; nothing is sent. Chat has citation and length checks, not the brief's full numerical checks.

The UI uses a persistent async event loop for SDK connections and permits one correction attempt for invalid responses. Restart Streamlit after code updates. These changes address plausible repeated-click causes; they do not establish that every live provider or validation failure is resolved. See [RCA setup and limitations](docs/RCA_QUICKSTART.md).

## Compare existing models with LLM replacements

The benchmark runs separately from the live explanation workflow and never overwrites operational forecasts. It covers four availability rates, program and non-program legs, enquiry counts, the quote-count multiplier and conversion curve. All variants share the deterministic supply calculation and bounded pricing solver.

| Candidate | Daily forecasts | Demand curves |
| --- | --- | --- |
| `current_refit` | Current notebook recipes, refitted at the cutoff | Current curves, refitted at the cutoff |
| `seasonal_naive` | Repeat last week's observations | Current curves |
| `llm_forecasts_current_curves` | LLM | Current curves |
| `current_forecasts_llm_curves` | Current recipes | LLM |
| `llm_full` | LLM | LLM |

The offline benchmark requires `avl_fleet_daily.parquet`, `legs_fleet_daily.parquet`, `quotes_fleet_daily.parquet`, and `quotes_deduped_enriched.parquet` under `data/processed/`:

```bash
uv run python -m src.model_benchmark --out /tmp/dpe-benchmark
```

Defaults: three cutoffs in 2025 and 14 held-out days per cutoff. No API calls occur by default. For an explicitly paid, one-cutoff LLM pilot:

```bash
uv run python -m src.model_benchmark \
  --out /tmp/dpe-llm-pilot \
  --origins 2025-11-30 --horizon 14 \
  --llm --allow-paid --model gpt-5.5 \
  --max-calls 1 --max-output-tokens 8000
```

LLM requests contain numerical history and aggregated curve bins, not customer IDs or raw quote rows. Responses are cached by request hash; matching cache entries are reused. Call/token limits are not a dollar cap. The benchmark does not automatically retry paid requests. Failed or invalid LLM outputs are recorded without substituting baseline predictions.

The output directory contains `report.md`, `results.json`, `aggregate_metrics.json`, `pricing_diagnostics.csv`, per-candidate predictions, prepared requests, and LLM usage/cache files. Keep these local and copy temporary output folders somewhere permanent if needed. See the [full experiment plan](docs/MODEL_BENCHMARK_PLAN.md).

### Observed pilot results

One GPT-5.5 call was completed on October 13, 2026, using history through November 30, 2025 to predict December 1–14, 2025. All five candidates completed without recorded failures. This is a small retrospective pilot, not an untouched final holdout: the current recipes were developed using these historical years.

| Forecast | Current MAE | LLM MAE | LLM error change |
| --- | ---: | ---: | ---: |
| AOG rate (percentage points) | 2.82 | 4.15 | +47.1% |
| SMX rate (percentage points) | 1.10 | 1.66 | +50.6% |
| UMX rate (percentage points) | 4.92 | 5.81 | +18.1% |
| CNA rate (percentage points) | 1.59 | 1.33 | −16.3% |
| Program legs/day | 5.11 | 6.64 | +30.1% |
| Non-program legs/day | 2.24 | 1.93 | −13.8% |
| Enquiries/day | 14.74 | 14.29 | −3.1% |
| Remaining-supply proxy (legs/day) | 1.98 | 2.64 | +33.2% |

Negative change means lower MAE. CNA and enquiries improved by MAE but slightly worsened by RMSE. Current forecasts matched the diagnostic reference's decision status on 9/14 days versus 7/14 for the full LLM variant. DNQ disagreement rose from 5 to 6 days. LLM conversion scores were effectively unchanged and slightly worse (Brier 0.05456 versus 0.05452 over 224 eligible rows).

Full-LLM yield MAE against the reference was lower, but measured five non-DNQ dates versus six for the current system; these unequal samples do not support a direct pricing-winner claim. The reference uses realized daily inputs with the current train-only curve and is not a true optimal-price label. No revenue uplift was measured.

The call took approximately 68 seconds, using 67,362 input tokens and 6,107 output tokens. Local run metadata and predictions are retained outside the repository; the figures above summarize those outputs. A separate offline 42-day pilot found current forecasts better than repeat-last-week forecasts by RMSE across all seven daily targets.

**Current conclusion:** retain the existing forecasting engine and LLM explanation layer. Non-program-leg forecasting merits further testing, but this single run does not justify replacing the models. Further evaluation should use more origins, forecast horizons and repeated LLM runs before any approved shadow or controlled pricing trial. Historical conversion labels, mixed yield sources, and enquiry/departure-date alignment remain limitations.

## Application modules and tests

| File | Responsibility |
| --- | --- |
| `app.py` | Local charts, brief and read-only chat |
| `src/rca_tools.py` | Original recommendation and supply lookups |
| `src/rca_evidence.py` | Saved-file snapshots and deterministic reconciliation |
| `src/rca_agent.py` | Brief, validation and bounded output correction |
| `src/rca_chat.py` | Follow-up questions scoped to the selected evidence |
| `src/agent_runtime.py` | Persistent async loop for UI calls |
| `src/explain_price.py` | Offline/agent command-line explanation |
| `src/model_benchmark.py` | Historical baseline and optional LLM comparison |

```bash
uv run python -m src.explain_price 2026-01-05
uv run --with "streamlit==1.58.0" python -m unittest discover -s tests -v
```

Tests use synthetic fixtures and mocked model calls, so running them does not incur API charges. They cover evidence consistency, solver branches, missing data, citation/wording checks, chat scope resets, repeated runtime calls, bounded correction, benchmark metrics, output validation, caching and the paid-call gate. Passing tests does not certify live AI factual accuracy.

## Author and license

Created by [Rudraksh Syal](https://github.com/rudrakshsyal). No license file is included in the repository; data access and reuse terms also need to be specified.

## Tool-based ML model selection

A separate experiment now compares eight conventional forecast candidates per daily component and three alternatives per demand curve. Validation choices are frozen before final evaluation. An optional OpenAI Agents SDK coordinator calls bounded experiment tools; model fitting and score-based selection remain in Python. **The completed run was offline; no paid coordinator calls were made.**

On November 1–28, 2025, validation-selected models reduced enquiry RMSE by 19.2%, program-leg RMSE by 7.3% and remaining-supply proxy RMSE by 14.6%. UMX and non-program forecasts worsened. Common-date diagnostic price error fell, but DNQ disagreement increased from 60.7% to 64.3%; this does not establish better operational pricing or revenue. Production models remain unchanged.

```bash
uv run python -m src.model_selection --out experiments/component_selection_new
```

See [full methodology, candidate settings, results and optional coordinator instructions](docs/MODEL_SELECTION_METHODOLOGY.md). Modules: `src/model_selection.py`, `src/model_selection_agent.py`; offline tests: `tests/test_model_selection.py`.

## Adaptive GPT-5.5 research agent — completed experiment

The new `src.research_agent` lets GPT-5.5 plan experiments, inspect training summaries, choose and tune forecast models, review validation errors, test ensembles and select final recipes with reasons. Unlike the fixed coordinator above, its experiment sequence and final choices are not predetermined. Local tools enforce bounds and keep final-test observations outside the agent workbench.

Completed a paid GPT-5.5 run on October 14, 2026: 24 trials and 47 model requests, with $2.8575 conservatively accounted against a $4 cap. All 21 offline tests passed before execution. The separate evaluator compares the selected pipeline against current Prophet/seasonal recipes after choices are frozen. Historical November results remain retrospective, not an untouched holdout. See [research-agent methodology, controls and approval-ready run instructions](docs/AGENTIC_RESEARCH.md).

### Adaptive research results

On the retrospective November 1–28 test, AOG/CNA RMSE improved 12.2%/28.4%, while UMX/non-program RMSE worsened 30.7%/13.3%. SMX, program legs and enquiries retained current recipes. Remaining-supply error increased 2.4%, and DNQ disagreement increased from 60.7% to 67.9%. Keep production models unchanged; no revenue uplift was demonstrated.

- [Executive results and agent selection reasons](experiments/gpt55_adaptive_2026-10-14/RUN_SUMMARY.md)
- [Full adaptive experiment artifacts](experiments/gpt55_adaptive_2026-10-14/)
- [Fixed model-search comparison](experiments/component_selection_complete_2026-10-14/report.md)
- [Earlier direct-LLM pilot](experiments/llm_pilot/report.md)
- [Chronological activity and budget log](docs/AGENTIC_RESEARCH_RUN_LOG.md)

The committed experiment folders contain aggregate daily predictions, scores, model configurations, visible agent actions and usage records. Raw operational datasets and API credentials remain excluded. The $4 application budget guard reserves each request before dispatch; it is not an account-wide billing limit.

## Synthetic fleet simulation

A separate synthetic generator creates ten simulated years (2026–2035 calendar labels) from the 731 observed days and 47,400 enquiries in 2024–2025. Three baseline seeds plus demand-shift and maintenance-stress paths contain 18,260 daily rows and 1,189,346 generated enquiries. Dates are simulation labels, not future forecasts. Source data are unchanged; the generated datasets are archived separately under `experiments/synthetic_fleet_v1`.

The proposed evaluation uses six initial training years, one validation year and three final-test years, with quarterly origins and 14/28/90-day horizons. Existing benchmark date/horizon limits must be adapted before executing it. No ML/LLM performance improvement is claimed from generation alone. See [inventory, quality checks and methodology](docs/SYNTHETIC_DATA.md).

```bash
uv run python -m src.synthetic_data --root . --out /path/to/new/synthetic_fleet
```

### Synthetic three-way comparison — completed

The first baseline-seed pilot compared the current engine, direct GPT-5.5 forecasts and GPT-5.5-directed ML research over three 90-day final windows (270 simulated test days), with four 90-day validation folds. Conservative API cost: **$2.14 of a new $4 cap**. Current ML supply RMSE was **3.594**, versus **4.696** for direct GPT-5.5 and **3.634** for the agent. Current ML also had the lowest diagnostic price error at 14/28/90 days. These simulator results do not prove real-world revenue performance.

- [Separate comparison methodology](docs/SYNTHETIC_COMPARISON.md)
- [Executive results](experiments/synthetic_three_way_v1/EXECUTIVE_SUMMARY.md)
- [All horizon results and artifacts](experiments/synthetic_three_way_v1/REPORT.md)
- [Synthetic datasets and quality report](experiments/synthetic_fleet_v1/REPORT.md)

Only baseline_seed42 was benchmarked under this approval; the other seeds and stress scenarios remain untested.

### Offline synthetic robustness

The frozen agent pipeline was tested against current ML across **five synthetic paths and 60 quarterly folds**, with **zero API calls and $0 API cost**. At the 90-day horizon, supply RMSE improves 2.9% on seed42 and 5.2% under maintenance stress, but worsens 2.5% on seed123 and is nearly tied on seed2026. These mixed simulation results do not establish revenue uplift or justify replacing current ML.

See the [executive summary](experiments/synthetic_robustness_v1/EXECUTIVE_SUMMARY.md), [full results](experiments/synthetic_robustness_v1/REPORT.md), and [methodology and reproduction instructions](docs/SYNTHETIC_ROBUSTNESS.md). Predictions, diagnostics, input hashes and frozen recipes are saved separately under `experiments/synthetic_robustness_v1/`.
