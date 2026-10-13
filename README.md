# Dynamic Pricing Engine

A supply–demand equilibrium dynamic pricing engine for **one NREG Challenger fleet**, developed as a notebook-based prototype. It combines aircraft availability, committed flight demand, quote-volume forecasts, and estimated price response to recommend a fleet-level yield for each departure date.

The business goal is to produce a **pricing recommendation grid for fleet pricing managers and revenue leadership**: a date-by-date view of remaining capacity, expected demand, recommended yield, and pricing status to support fleet pricing decisions.

This repository is a learning and portfolio rebuild of an earlier production dynamic pricing project at Vista Tech LLC (FLYXO), as described in the project handoff. The rebuild uses anonymised data. Production deployment history and impact are separate from the local notebook results reported here.

The current analysis focuses on Challenger 300 and Challenger 350 aircraft, with North America departure filters in the flight-leg and quote pipelines. The notebooks refer to this scope as **NREG US**. Historical analysis covers 2024–2025, and the saved forecast run covers **January 1–May 31, 2026**.

**Current status:** the repository contains nine analysis/modeling notebooks, a reusable supply calculation module, and HTML visualizations. Execution requires external CSV inputs that are not included. `main.py` is a scaffold that prints a greeting; the working pipeline is in the notebooks.

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

Run the notebooks in the numbered order, using the project environment as the kernel. Review the reproduction issues below first; this is not yet a verified clean-run pipeline. Installing the environment and rerunning models requires the external data and was not performed for this documentation update.

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
- **Model validation:** quote forecasts lack a recorded holdout evaluation; the conversion R² measures fit to historical binned data. Missing 2026 actuals do not prevent rolling-origin backtests within 2024–2025. Keep future booking statuses and realised revenue out of features available at each historical solve date. Forecast accuracy can be backtested; historical realised revenue alone cannot establish the revenue that a different pricing policy would have earned.
- **Price-response assumptions:** booked and unbooked yields come from different sources, and 43.9% of booked quotes still lack yield. Dropping these bookings can distort both the conversion level and curve shape; the direction and size of bias need assessment. The quote-count curve measures observed counts per price bin, which does not establish how inquiry volume changes when price changes. Compare a constant quote-count multiplier of 1 with LOWESS, and test conversion fits restricted to the operating price window before choosing a revised model.
- **Configuration consistency:** notebook 08 uses a $6,000 plotting/parameter floor while notebook 09 uses $7,000. Its normalized composite-demand plot also differs from the solver's booking-unit formula. Some labels and filenames still say January despite the 151-day horizon.
- **Operationalization:** there is no implemented service/API, automated retraining workflow, or test suite in the current tree. Packaging the notebook stages into a configurable pipeline, validating data contracts, and adding forecast/solver tests are future work.

## Author and license

Created by [Rudraksh Syal](https://github.com/rudrakshsyal). No license file is included in the repository; data access and reuse terms also need to be specified.


## On-demand revenue explanation

The read-only RCA interface explains a selected saved recommendation using supply, demand and solver evidence. It includes capacity and demand charts, a short revenue brief, and expandable source details. It does not change prices or train models.

```bash
uv sync
uv run --with "streamlit==1.58.0" streamlit run app.py --server.address 127.0.0.1
```

Set `OPENAI_API_KEY` in the launching terminal to enable **Explain**. Charts and calculations work without an API key. Model calls happen only when Explain is clicked. The default model is `gpt-5.5`; choose a model available to your API project in the sidebar.

Supply these saved files locally under `data/processed/`: `optimal_yield_per_date.parquet`, `jan2026_od_supply.parquet`, `jan2026_may2026_quotes_forecast.parquet`, and `elasticity_params.json`. The adapter also reads constants from `notebooks/09_solver.ipynb`. Datasets are not included in this code update. See [RCA setup and limitations](docs/RCA_QUICKSTART.md). The interface reconstructs the saved calculation, not a historical execution trace.

Run offline and mocked-agent checks with:

```bash
uv run --with "streamlit==1.58.0" python -m unittest discover -s tests -v
```
