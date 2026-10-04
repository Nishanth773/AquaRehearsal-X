# AquaRehearsal-X

**Early-Warning and Resilience-Planning Platform for Freshwater Streams**  
*OneAquaHealth IEEE Global Hackathon 2026 — Track 6: Resilience Informatics: Enable Early Warning & Resilience Planning*

---

## Project Vision & Research Question
AquaRehearsal-X addresses a critical water security question:
> **"How much storm can this stream tolerate before severe dissolved-oxygen depletion, how likely is an incoming storm to cross that boundary, how much time remains to act, and which interventions could potentially increase resilience?"**

To ensure scientific defensibility, this platform is engineered in strict phased stages:
- **Stage 1: Real Data Foundation (Completed)** — Discovery, ingestion, and rigorous audit of USGS water quality sensors across 8 candidate monitoring stations.
- **Stage 2: 72-Hour Dissolved Oxygen Forecasting Engine (Completed)** — Baseline models, LightGBM quantile regression, split conformal calibration, and leakage prevention.
- **Stage 2.5: Historical Depth + Real Precipitation Upgrade (Completed & Validated)** — Multi-year record extension (2023–2026, 32,807 hours), authoritative ECMWF ERA5 hourly liquid rain (`rain_mm`) integration, Model A vs Model B testing, and 10 publication-grade scientific figures.
- **Stage 3: Storm Tolerance Envelope & Early Warning (Completed & Validated)** — Dynamic multi-dimensional resilience boundaries, thermal & antecedent moisture conditioning, boundary-crossing probability ($P_{\text{cross}}$), time-to-trough operational action windows, 8 publication-grade scientific figures, and 58 automated tests.
- **Stage 4: Action Window & Intervention Rehearsal Engine (Completed & Validated)** — Empirical action-window bounds, continuous Streeter-Phelps oxygen balance simulation across 4 intervention archetypes (Aeration, Runoff Reduction, Detention, Shading), strict time-feasibility filtering, anti-ranking compliance, interactive HTML platform, and 67 automated tests.
- **Stage 5: Field Check & Citizen Verification (Completed & Validated)** — Structured 4-tier field observation submission pipeline, privacy-first coordinate coarsening (~1.1 km), automated quality assurance, 15-minute duplicate hash detection, spatio-temporal forecast matching ($\le 20\text{ km}$, $\le 72\text{h}$), human-in-the-loop review workflow, dual-track validation ledger, and 77 automated tests.
- **Stage 6: Full System Integration (Completed & Validated)** — End-to-end mission control platform ([`data/reports/stage6/mission_control.html`](file:///c:/Users/Nishanth/OneDrive/Desktop/AquaRehearsal-X/data/reports/stage6/mission_control.html)), live 9-subsystem observability monitor, strict historical storm replay (Event 54 - August 2026), 3-5 minute guided hackathon demo mode, and 89 automated tests (100% pass rate).
- **Stage 7: Final Hackathon Readiness (Completed & Validated)** — Visual hierarchy refinement with Storm Tolerance Envelope as visual centerpiece, 7-step guided 3-minute hackathon demo script, visible scientific limitations panel, comprehensive judge-facing technical summary, reproducible offline demo environment, and presentation collateral ([`docs/STAGE7_FINAL_READINESS.md`](file:///c:/Users/Nishanth/OneDrive/Desktop/AquaRehearsal-X/docs/STAGE7_FINAL_READINESS.md), [`docs/HACKATHON_PRESENTATION.md`](file:///c:/Users/Nishanth/OneDrive/Desktop/AquaRehearsal-X/docs/HACKATHON_PRESENTATION.md)).

---

## Scientific Integrity Mandate
In strict adherence to hackathon integrity standards:
- **Zero Fabrication:** We **never** fabricate environmental observations, rainfall values, dissolved oxygen (DO) measurements, station metadata, missing data, storm events, model accuracy metrics, scientific thresholds, intervention effects, or API responses.
- **Unavailable Data Transparency:** If a parameter is not monitored or an API endpoint is unavailable, it is reported explicitly as `UNAVAILABLE` or `INSUFFICIENT`.
- **Synthetic Test Isolation:** Synthetic datasets exist **exclusively inside automated software unit test fixtures** (`tests/`) and are explicitly labeled `TEST DATA`.
- **Precipitation Missingness Rule:** Missing precipitation remains strictly NaN (`missing = NaN`, `dry hour = 0.0 mm`). No silent zero-imputation is permitted.
- **Geographic Representation Boundary:** Reanalysis precipitation represents point/grid estimates at monitoring coordinates (Lat 40.0° N, Lon -75.25° W) and is NOT equivalent to catchment-average rainfall.

---

## Directory Structure

```text
AquaRehearsal-X/
│
├── data/
│   ├── raw/                  # Unaltered raw API responses (with provenance)
│   ├── processed/            # Cleaned, standardized time series (native, 1h, 1d)
│   └── reports/              # Scientific reports and CSV evaluations
│       ├── plots/            # Publication-grade real-data visualizations
│       ├── station_candidates.csv
│       ├── data_quality_report.csv
│       ├── candidate_storm_events.csv
│       ├── statistics_01474500_overall.csv
│       ├── statistics_01474500_monthly.csv
│       ├── statistics_01474500_seasonal.csv
│       └── DATA_FOUNDATION_REPORT.md
│
├── src/
│   ├── data/                 # Ingestion, cleaning, resampling, discovery
│   │   ├── usgs_client.py    # USGS REST API client with provenance & caching
│   │   ├── cleaner.py        # Boundary checking & audit logging
│   │   ├── resampler.py      # Multi-scale temporal aggregation
│   │   └── discovery.py      # Multi-station discovery & evaluation
│   ├── analysis/             # Statistics, quality, disturbance, plotting
│   │   ├── quality.py        # Missingness & co-occurrence analyzer
│   │   ├── statistics.py     # Parametric, non-parametric, seasonal stats
│   │   ├── disturbance.py    # Candidate storm disturbance detection
│   │   └── plotting.py       # Publication-ready matplotlib visualizations
│   ├── config/               # Transparent configurations & thresholds
│   │   └── settings.py
│   ├── features/             # Future ML feature generation interfaces
│   │   └── feature_engineering.py
│   ├── weather/              # Weather & precipitation interface architecture
│   │   └── weather_interface.py
│   ├── utils/                # Standardized logger
│   │   └── logger.py
│   └── pipeline.py           # Master reproducible pipeline orchestrator
│
├── tests/                    # Automated pytest suite (labeled test fixtures)
│   ├── test_usgs_client.py
│   ├── test_cleaner.py
│   ├── test_resampler.py
│   ├── test_quality.py
│   └── test_disturbance.py
│
├── requirements.txt          # Python dependencies
├── DATA_FOUNDATION_REPORT.md # Top-level copy of the scientific report
├── README.md                 # Project documentation
└── .gitignore
```

---

## Installation & Environment Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13.2)
- Git

### 2. Clone and Setup Environment
```bash
git clone https://github.com/YourRepo/AquaRehearsal-X.git
cd AquaRehearsal-X

# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Linux / macOS
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## How to Run the Pipeline and Tests

### Run Automated Tests
```bash
pytest -v
```
All 14 unit tests execute against labeled test fixtures, verifying:
- USGS JSON parsing and metadata extraction
- UTC timezone normalization and sorting
- Duplicate timestamp resolution
- Physical boundary violation flagging
- Multi-scale resampling (15m, 1h, 1d)
- Suitability scoring (`GOOD`, `WARNING`, `INSUFFICIENT`)
- Candidate hydrologic disturbance surge detection

### Run the Master Data Pipeline
```bash
python src/pipeline.py
```
This executes the end-to-end scientific pipeline:
1. Queries 8 candidate USGS stations across multiple states.
2. Ingests raw data with full provenance and caches in `data/raw/`.
3. Performs cleaning and boundary validation (with audit trail).
4. Generates multi-scale resampled time series in `data/processed/`.
5. Computes parametric, non-parametric, and seasonal statistics.
6. Detects candidate hydrologic disturbance events.
7. Produces 9 real-data scientific plots in `data/reports/plots/`.
8. Generates the final foundation report `DATA_FOUNDATION_REPORT.md`.

---

## Data Sources & Provenance Approach

### Official Data Sources
1. **USGS Instantaneous Values (IV) REST API**  
   Endpoint: `https://waterservices.usgs.gov/nwis/iv/`  
   Parameters audited:
   - `00300`: Dissolved Oxygen (mg/L)
   - `00010`: Water Temperature (°C)
   - `00060`: Stream Discharge (cfs)
   - `00076` / `63680`: Turbidity (NTU / FNU)
   - `00065`: Gage Height (feet)
2. **USGS Water Services Site Service**  
   Endpoint: `https://waterservices.usgs.gov/nwis/site/`

### Data Provenance
Every raw response is saved **completely unchanged** in `data/raw/` wrapped with an immutable provenance payload:
```json
{
  "provenance": {
    "source": "USGS Water Services - Instantaneous Values (IV) API",
    "retrieval_date_utc": "2026-09-28T16:10:54+00:00",
    "station_id": "01474500",
    "parameter_codes": ["00300", "00010", "00060", "00076", "63680", "00065"],
    "requested_period": "P180D",
    "api_endpoint": "https://waterservices.usgs.gov/nwis/iv/?sites=01474500&..."
  },
  "data": { ... }
}
```

---

## Candidate Station Suitability Assessment

Candidate stations were classified according to transparent, configurable numerical criteria in `src/config/settings.py`:
- **GOOD:** DO availability $\ge 80\%$, Temperature $\ge 75\%$, Discharge $\ge 70\%$, Max continuous gap $\le 14$ days, Total observations $\ge 5,000$.
- **WARNING:** DO availability $\ge 50\%$, Discharge $\ge 40\%$, Max continuous gap $\le 45$ days.
- **INSUFFICIENT:** Missing DO entirely, or DO availability $< 50\%$, or missing discharge.

### Findings Across Investigated Stations
| Station ID | Station Name | Available Parameters | DO Availability | Discharge Availability | Classification |
|---|---|---|---|---|---|
| **01474500** | **Schuylkill River at Philadelphia, PA** | DO, Temp, Q, Turbidity, Gage Height | **99.69%** | **99.99%** | **GOOD (Recommended)** |
| **08048000** | **W Fk Trinity Rv at Ft Worth, TX** | DO, Temp, Q, Turbidity, Gage Height | **66.23%** | **99.97%** | **WARNING (Secondary)** |
| 01463500 | Delaware River at Trenton, NJ | DO, Temp, Q, Turbidity, Gage Height | 24.95% | 99.97% | INSUFFICIENT (DO missingness) |
| 01646500 | Potomac River nr Wash, DC Little Falls | Q, Gage Height (DO seasonal offline) | 0.0% | 100.0% | INSUFFICIENT (DO offline) |
| 02087500 | Neuse River near Clayton, NC | Q, Gage Height | 0.0% | 100.0% | INSUFFICIENT (No DO sensor) |
| 01651800 | Watts Branch at Washington, DC | Temp, Q, Gage Height, Turbidity | 0.0% | 99.93% | INSUFFICIENT (No DO sensor) |
| 01589440 | Jones Falls at Sorrento, MD | Q, Gage Height | 0.0% | 100.0% | INSUFFICIENT (No DO sensor) |
| 01651000 | Northwest Branch Anacostia River, MD | None | 0.0% | 0.0% | INSUFFICIENT (Gage offline) |

---

## Candidate Hydrologic Disturbance Events
In accordance with scientific rules, events are identified strictly through observed discharge surges ($\ge 2.5\times$ rolling median and $\ge 90\text{th}$ percentile) without inventing arbitrary DO crash thresholds:
- **16 candidate disturbance events** were discovered at USGS 01474500 across 180 days.
- Discharge surges reached up to **9.6x baseline** (peak 6,940 cfs).
- During summer high-temperature periods ($>25^\circ\text{C}$), runoff surges triggered post-event DO drops of up to **7.3 to 9.7 mg/L**, accompanied by turbidity surges up to **24.1 FNU**.

---

## Limitations of Current Data
1. **Rainfall Sensor Decoupling:** In-stream USGS gages do not measure localized precipitation. Stage 2 must co-locate radar-derived precipitation (NOAA MRMS / HRRR).
2. **Optical Sensor Drift & Cleaning:** Turbidity and DO optical sensors experience periodic calibration drift or biofouling, documented in USGS provisional qualifier codes.
3. **Temporal Scope:** While 180 days captures critical warm-season hypoxia risk windows, multi-year archives are necessary for multi-decadal recurrence interval statistics.

---

## What Stage 2 Implemented (72-Hour DO Forecasting Engine)

In Stage 2, AquaRehearsal-X built its first predictive component: a site-specific probabilistic short-horizon forecasting engine predicting **future minimum dissolved oxygen over the next 72 hours**.

### Key Deliverables:
1. **Target Construction:** Strictly future-window target $TARGET(t) = \min_{\tau \in (0, 72\text{h}]} \text{DO}(t + \tau)$.
2. **Leakage-Free Features:** 144 engineered features (lags, rolling backward statistics, rate of change, Benson-Krause theoretical DO saturation, and cyclical seasonality). Proved 100% leakage-free via automated future-mutation tests.
3. **Rigorous Chronological Validation:** Train (Apr–Jul, 2,624 obs) $\to$ Validation (Jul–Aug, 864 obs) $\to$ Test (Aug–Sep, 760 obs).
4. **Baseline Benchmarks:** Persistence (Baseline A) and Regularized Linear/Seasonal (Baseline B).
5. **Main ML Forecaster:** LightGBM Regressor with early stopping, outperforming Persistence by 38.8% in RMSE and 24.0% in MAE.
6. **Uncertainty Quantification:** Pinball loss Quantile LightGBM ($q_{10}, q_{50}, q_{90}$) and Inductive Split Conformal Prediction.
7. **Storm-Event Backtesting:** Pre-event forecasting across 16 historical candidate disturbance events.
8. **Basic Input-Domain Warning Checker:** Automatic OOD flags for extreme excursions outside historical training bounds.
9. **Clean Programmatic Prediction API:** `predict_min_do(input_features)`.

---

## Stage 2 Model Performance Summary (Unseen Test Set)

| Model | MAE (mg/L) | RMSE (mg/L) | $R^2$ | Median AE (mg/L) | Within $\pm 0.5$ mg/L (%) | Within $\pm 1.0$ mg/L (%) | Test Disturbance MAE |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Baseline A (Persistence: Current DO)** | 0.871 | 1.275 | -2.3315 | 0.600 | 47.17% | 67.85% | 0.940 |
| **Baseline B (Linear: DO + Temp + Season)** | 3.537 | 3.599 | -25.5590 | 3.456 | 0.00% | 0.00% | 3.778 |
| **LightGBM Regressor (Stage 2 Main ML)** | **0.662** | **0.780** | **-0.2491** | **0.684** | **38.42%** | **75.53%** | **1.020** |

*See [`docs/STAGE2_MODEL_REPORT.md`](file:///c:/Users/Nishanth/OneDrive/Desktop/AquaRehearsal-X/docs/STAGE2_MODEL_REPORT.md) and [`docs/MODEL_CARD.md`](file:///c:/Users/Nishanth/OneDrive/Desktop/AquaRehearsal-X/docs/MODEL_CARD.md) for full scientific analysis, feature importances, and limitations.*

---

## How to Run Stage 2 Pipeline and Tests

### 1. Run Automated Test Suite (26 Unit & Integration Tests)
```bash
pytest -v
```
Verifies:
- All 14 Stage 1 data integrity, resampling, and disturbance tests
- Target construction and minimum future observation validation
- Strict exclusion of current time $t$ from target window
- Backward lag shifts and rolling window directionality
- Rigorous leakage prevention via future-data mutation testing
- Baseline models and LightGBM model fitting
- Uncertainty quantile ordering and non-crossing constraints
- Split conformal calibration
- Basic input-domain / OOD range checking
- Prediction API structured inference

### 2. Run Stage 2 Master Pipeline
```bash
python src/stage2_pipeline.py
```
This executes the end-to-end scientific modeling workflow:
1. Audits sensor completeness and prints data verification report.
2. Builds 72h future minimum target and filters invalid incomplete windows.
3. Constructs 144 causal features.
4. Partitions data chronologically (Train $\to$ Val $\to$ Test).
5. Fits Baseline A, Baseline B, and LightGBM.
6. Calibrates Quantile LightGBM and Split Conformal Prediction.
7. Computes regression metrics and test-set baseline comparison table.
8. Executes pre-event backtests across candidate storm disturbance events.
9. Generates 9 publication-grade figures in `data/reports/stage2/`.
10. Saves trained models, feature lists, domain ranges, and metadata in `data/reports/stage2/models/`.

### 3. Programmatic Prediction API Usage
```python
from src.models import predict_min_do

# Provide pre-event environmental observations
input_sample = {
    "dissolved_oxygen": 8.2,
    "water_temperature": 23.5,
    "discharge": 1450.0,
    "turbidity": 6.8,
}

forecast = predict_min_do(input_sample)
print(forecast)
# {
#   'target': 'minimum_dissolved_oxygen_next_72h',
#   'unit': 'mg/L',
#   'point_forecast_mg_L': 6.85,
#   'lower_bound_10th_percentile_mg_L': 5.88,
#   'upper_bound_90th_percentile_mg_L': 7.92,
#   'domain_warning': {'has_domain_warning': False, ...},
#   ...
# }
```

---

## Stage 2 Generated Artifacts & Reports

```text
AquaRehearsal-X/
├── data/reports/stage2/
│   ├── 1_actual_vs_predicted_scatter.png        # Scatter plot with 1:1 identity line
│   ├── 2_timeseries_forecast_trajectory.png     # Chronological test forecast trajectory
│   ├── 3_prediction_intervals_test.png          # 80% Quantile interval test series
│   ├── 4_residual_distribution.png              # Residual histogram and normal overlay
│   ├── 5_residuals_vs_predicted.png             # Residuals vs predictions (heteroscedasticity)
│   ├── 6_baseline_vs_ml_comparison.png          # MAE / RMSE comparison bar chart
│   ├── 7_feature_importance.png                 # Top 15 features by model relative gain
│   ├── 8_disturbance_backtesting_errors.png     # Storm event backtest actual vs predicted
│   ├── 9_interval_coverage_reliability.png      # Nominal vs observed coverage diagram
│   ├── model_comparison_metrics.csv             # Structured model benchmark table
│   ├── backtest_results.csv                     # Candidate storm event backtesting log
│   ├── test_predictions.csv                     # Full test-set predictions & intervals
│   ├── feature_importance.csv                   # All 144 feature gain/split importances
│   └── models/
│       ├── lgbm_regressor.joblib                # Trained LightGBM model artifact
│       ├── lgbm_quantile_10.joblib              # 10th percentile quantile regressor
│       ├── lgbm_quantile_50.joblib              # 50th percentile quantile regressor
│       ├── lgbm_quantile_90.joblib              # 90th percentile quantile regressor
│       ├── baseline_b_model.joblib              # Fitted Baseline B Ridge pipeline
│       ├── domain_ranges.json                   # Learned training distributions for OOD checks
│       ├── feature_list.json                    # Feature column order
│       └── model_metadata.json                  # Training date ranges, hyperparameters, seeds
│
├── docs/
│   ├── MODEL_CARD.md                            # Comprehensive model documentation
│   ├── STAGE2_MODEL_REPORT.md                   # 23-point scientific model evaluation report
│   ├── STAGE2_5_REPORT.md                       # Historical depth & ECMWF ERA5 precipitation report
│   └── STAGE3_REPORT.md                         # Storm Tolerance Envelope & early-warning report
```

---

## What Stage 3 Implemented (Storm Tolerance Envelope & Early Warning)

Stage 3 transforms our predictive 72-hour forecasting model into an operational decision-support tool by computing dynamic ecological resilience boundaries and early-warning alerts:

### Key Deliverables:
1. **Dynamic Multi-Dimensional Tolerance Envelope:** Replaces static water quality limits with a state-conditioned boundary function calculating critical rainfall ($R_{\text{crit}}$) and critical discharge surge ($Q_{\text{crit}}$) before standard violation.
2. **Resolution of Static Calibration Deficit:** Implements **thermally stratified split-conformal uncertainty intervals** (Cold, Moderate, Warm) to capture heightened summer biological volatility.
3. **Regulatory Boundary-Crossing Probabilities:** Derives exact non-linear exceedance probabilities:
   - $P_{\text{cross}}(5.0\text{ mg/L})$: Standard PA DEP Warm Water Fishes daily criterion.
   - $P_{\text{cross}}(4.0\text{ mg/L})$: Acute instantaneous minimum criterion.
   - $P_{\text{cross}}(2.0\text{ mg/L})$: Severe ecological hypoxia / lethal fish kill limit.
4. **Operational Action Window Latency:** Quantifies time-to-trough ($t_{\text{trough}}$) across 58 historical storm disturbances (median = 7.0h, expanding to 35h in summer heatwaves), characterizing actionable intervention lead times.
5. **Historical Stress-Testing:** Validated across all 58 detected historical storm events (2023–2026), achieving **100% sensitivity** (0 missed regulatory hazards) and **60.3% specificity**.
6. **Programmatic STE API:** Clean `evaluate_storm_tolerance()` interface exposing real-time risk tiers, critical thresholds, buffer margins, and out-of-distribution flags.
7. **8 Publication Figures:** High-resolution phase-space contours, thermal shrinkage comparisons, lag distributions, and chronological case studies in `data/reports/stage3/`.

### Running Pipelines & Tests

```bash
# Run Full Master Verification Suite (89 Tests Passing across Stages 1–6)
pytest -v

# Run Stage 6 Master Full System Integration Pipeline
python src/stage6_pipeline.py

# Run Individual Stage Pipelines (Optional)
python src/pipeline.py          # Stage 1: Data Ingestion & Quality Foundation
python src/stage2_pipeline.py   # Stage 2: DO Forecasting Prototype
python src/stage2_5_pipeline.py # Stage 2.5: Historical Multi-Year + Rain Integration
python src/stage3_pipeline.py   # Stage 3: Storm Tolerance Envelope
python src/stage4_pipeline.py   # Stage 4: Action Window & Intervention Rehearsal
python src/stage5_pipeline.py   # Stage 5: Field Check & Citizen Verification
```

### Stage 6 Unified Workflow & Decision-Support Usage

```python
from src.integration.unified_workflow import UnifiedWorkflow

# Initialize Master Decision Support Engine
workflow = UnifiedWorkflow(threshold_mg_L=5.0, risk_limit=0.20)

# Run complete end-to-end pipeline
result = workflow.run_full_pipeline(
    simulated_storm_rain_mm=26.5,
    custom_water_temp_c=26.5,
)

print("Current DO:", result["stream_conditions"]["dissolved_oxygen_mg_l"], "mg/L")
print("72h Min DO Forecast:", result["forecast_72h"]["predicted_min_do_mg_l"], "mg/L")
print("Storm Tolerance Allowance:", result["storm_tolerance_envelope"]["safe_boundary_rainfall_allowance_mm"], "mm")
print("Breach Risk Probability:", result["storm_tolerance_envelope"]["estimated_breach_probability"])
```

### Interactive Web Deliverables
- 🌟 **Stage 6 Unified Mission Control Platform:** [`data/reports/stage6/mission_control.html`](file:///c:/Users/Nishanth/OneDrive/Desktop/AquaRehearsal-X/data/reports/stage6/mission_control.html)
- **Stage 5 Field Check Dashboard:** [`data/reports/stage5/field_check_dashboard.html`](file:///c:/Users/Nishanth/OneDrive/Desktop/AquaRehearsal-X/data/reports/stage5/field_check_dashboard.html)
- **Stage 4 Action Window & Rehearsal Web App:** [`data/reports/stage4/intervention_rehearsal_app.html`](file:///c:/Users/Nishanth/OneDrive/Desktop/AquaRehearsal-X/data/reports/stage4/intervention_rehearsal_app.html)
- **Stage 3 Storm Tolerance Envelope Web App:** [`data/reports/stage3/storm_tolerance_envelope_app.html`](file:///c:/Users/Nishanth/OneDrive/Desktop/AquaRehearsal-X/data/reports/stage3/storm_tolerance_envelope_app.html)

