# AquaRehearsal-X — Hackathon Presentation Materials
**Stage 7: Final Hackathon Readiness — Presentation Coaching & Demo Script**

---

## 1. Executive Pitches

### One-Sentence Project Pitch
> **AquaRehearsal-X is a scientifically grounded, One Health decision-support platform that transforms raw stream sensors and weather forecasts into a calibrated 2D Storm Tolerance Envelope, allowing watershed managers to rehearse ecological interventions before storms hit.**

### 30-Second Elevator Pitch
> *"Every time an intense storm hits an urban center, runoff and sewer overflows cause rapid, severe deoxygenation in freshwater streams, threatening aquatic life. Today's environmental dashboards only report disaster after it happens. AquaRehearsal-X introduces the **Storm Tolerance Envelope** — an empirical safe boundary that maps pre-storm water temperature against incoming rainfall. By combining LightGBM quantile forecasting, conformal uncertainty bounds, an empirical action window, and continuous mass-balance intervention rehearsal, we give municipal managers a 6-to-10 hour head start to mobilize aerators or runoff controls — backed by privacy-preserving citizen ground truth."*

---

## 2. 6-Slide Presentation Outline

### Slide 1: Title & The Urban Stream Dilemma
- **Title:** AquaRehearsal-X: Probabilistic Safe-Boundary Engine & One Health Decision Support.
- **Hook:** Urban waterways are vulnerable to acute deoxygenation during summer storms: warm water holds less oxygen, while urban runoff and sewer overflows spike biological oxygen demand.
- **Problem:** Environmental dashboards are retrospective monitors or uncalibrated point-forecasts. Decision-makers have no safe-boundary threshold, no lead-time estimation, and no ability to rehearse response options before the storm.
- **Visual:** Split screen: Sunny stream baseline (DO 7.1 mg/L) vs. post-storm deoxygenation nadir (DO 5.65 mg/L).

### Slide 2: The Real-Data Foundation & Predictive Architecture
- **Data Foundation:** Continuous telemetry from USGS 01474500 (Schuylkill River at Philadelphia, PA; 1,893 sq mi drainage basin) paired with Open-Meteo hourly reanalysis & rainfall forecasts (32,809 hourly records across 2023–2026).
- **ML Engine:** LightGBM Model B (156 backward-looking features, strictly isolating pre-event state from future data).
- **Uncertainty Guardrails:**
  - Non-crossing quantile regressors ($q_{10}, q_{50}, q_{90}$).
  - Inductive split conformal calibration ($\pm 1.955\text{ mg/L}$ margin) guaranteeing 90% finite-sample marginal coverage.
- **Visual:** Flow diagram: USGS/Weather APIs $\rightarrow$ Quality Pipeline $\rightarrow$ LightGBM Quantile Forecast.

### Slide 3: The Centerpiece — The Storm Tolerance Envelope (STE)
- **Concept:** Translating complex hydrologic physics into a 2D ecological safe-boundary: **Pre-Storm Water Temperature ($T_0$) vs. Incoming 24h Storm Rainfall ($R_{storm}$)**.
- **Methodology:**
  - Safe-boundary curve $R_{safe}(T)$ indicates the maximum permissible rainfall before threshold breach probability $P(\text{DO} < \tau)$ exceeds the operational risk limit $\alpha$ (e.g., 20%).
  - Higher temperatures compress the safe rainfall allowance from $>50\text{ mm}$ in spring down to $<20\text{ mm}$ during summer heatwaves.
- **Safeguard:** Delaunay convex hull domain refusal ($1.0^\circ\text{C}$ to $31.0^\circ\text{C}$, $0$ to $55\text{ mm}$ rain). The system refuses ungrounded extrapolations.
- **Visual:** 2D Storm Tolerance Envelope canvas with safe boundary curve, advisory zone, and 58 historical storm dots.

### Slide 4: Empirical Action Window & Logistically Gated Intervention Rehearsal
- **Action Window:** Empirical lag-to-nadir distribution from 58 storms ($P_{10} = 6.5\text{h}$, $P_{50} = 10.0\text{h}$, $P_{90} = 18.0\text{h}$).
  - Decision-makers know the operational deadline before oxygen reaches its critical nadir.
- **Intervention Rehearsal:**
  - Continuous Streeter-Phelps mass-balance solver simulating 4 archetypes: Diffused Aeration ($+0.77\text{ mg/L}$), Runoff Reduction ($+0.42\text{ mg/L}$), CSO Detention ($+0.55\text{ mg/L}$), and Riparian Shading ($+0.28\text{ mg/L}$).
- **Logistical Feasibility Gate:**
  - Automatically flags whether an intervention's mobilization time can beat the $P_{10}$ deadline (e.g., Aeration 4.0h mobilization $<$ 6.5h nadir $\rightarrow$ `FEASIBLE_IN_TIME`).
- **Visual:** 72-hour DO sag curve comparing baseline vs. diffused aeration recovery.

### Slide 5: Field Check & One Health Integrity
- **Citizen Field Check:**
  - Community members submit qualitative observations (turbidity, odor, fish behavior) and optional handheld probe readings.
  - Privacy safeguards: Coordinates coarsened to $\sim 1.1\text{ km}$ (2 decimal places), EXIF metadata stripped, PII redacted.
  - Strict Anti-Labeling Isolation: Field observations provide contextual verification; they are NEVER used to fabricate DO training labels.
- **One Health Triad:**
  - Environmental Health: Reaeration assimilative capacity monitored.
  - Aquatic Life: Protection against fish mortality ($>3.0\text{ mg/L}$).
  - Human Contact: **NOT ASSESSED** — explicitly communicating that dissolved oxygen and water appearance do NOT indicate bacterial pathogen safety (*E. coli*).
- **Visual:** One Health dashboard badge strip and Field Check submission interface.

### Slide 6: Real-World Verification & Scientific Transparency
- **Historical Replay (Event 54 — August 5, 2026 Severe Summer Storm):**
  - Reconstructed strictly using information available at forecast issue time $t_0$.
  - Persistence predicted no drop ($7.10\text{ mg/L}$, error $1.45\text{ mg/L}$).
  - LightGBM Model B anticipated the sag ($6.05\text{ mg/L}$ predicted vs. $5.65\text{ mg/L}$ observed, error $0.40\text{ mg/L}$ — a 72.4% error reduction).
- **Scientific Humility & Primary Limitation:**
  - All 58 storms in our catalog remained above $5.0\text{ mg/L}$; breach risk curves represent statistical projections rather than observed collapses.
  - Interventions are theoretical mass-balance simulations, not physically deployed hardware.
- **Visual:** Verification scoreboard: Replay Event 54 metrics and Open Source GitHub repository badge.

---

## 3. 3-Minute Demo Script (Timed Speaker Walkthrough)

| Time | Target Section / UI Action | Speaker Narration |
| :--- | :--- | :--- |
| **0:00 – 0:25** | **Header / Overview**<br>*Click "⚡ 3-Min Guided Demo"* | *"Hello judges. Urban streams face severe ecological shockwaves when summer storms wash hot runoff and sewer overflows into waterways, depleting dissolved oxygen. Current tools only report fish kills after they happen. We built AquaRehearsal-X — an AI-powered One Health decision-support platform that transforms telemetry into an actionable safe boundary."* |
| **0:25 – 0:55** | **Step 1: Stream Conditions**<br>*Auto-focuses KPI row* | *"Step 1: Real stream conditions. We ingest continuous telemetry from USGS station 01474500 on the Schuylkill River at Philadelphia. Right now, stream conditions show a warm summer baseline: Dissolved Oxygen at 7.10 mg/L (88% saturation), Water Temperature at 26.5°C, and Discharge at 900 cfs, with 26.5 mm of rain forecasted."* |
| **0:55 – 1:25** | **Step 2: 72h DO Forecast**<br>*Auto-focuses 72h Trajectory Card* | *"Step 2: Predictive forecasting. For this incoming storm, our LightGBM Model B predicts minimum DO will drop to 6.05 mg/L over the next 72 hours. Naive persistence assumes no change at 7.10 mg/L. Our model anticipates the deoxygenation sag, bounded by non-crossing 80% quantiles and a 90% split-conformal calibration interval."* |
| **1:25 – 2:05** | **Step 3: Storm Tolerance Envelope**<br>*Auto-focuses 2D STE Canvas* | *"Step 3: The visual centerpiece — the Storm Tolerance Envelope. Rather than looking at raw curves, managers inspect this 2D safe boundary mapping rainfall against pre-storm temperature. At 26.5°C, the river's safe rainfall allowance contracts to 21.0 mm. Because the incoming storm is 26.5 mm, the system triggers an ADVISORY alert with a 14.8% breach probability. Notice that our scenario is inside the empirical domain, and our interface transparently discloses that no historical events in our catalog fell below 5.0 mg/L."* |
| **2:05 – 2:35** | **Step 4: Rehearse Intervention**<br>*Selects Diffused Aeration Tab* | *"Step 4: Rehearsing response options. Our empirical action window indicates that oxygen nadir occurs between 6.5 and 10 hours after storm onset. We select Emergency In-Stream Aeration: with a 4-hour mobilization lead time, it is logistically FEASIBLE, projecting a +0.77 mg/L oxygen boost via Streeter-Phelps mass balance. We explicitly note this is an unvalidated simulation, not a deployed field trial."* |
| **2:35 – 2:55** | **Step 5: Field Check & One Health**<br>*Auto-focuses Field Check & Triad* | *"Step 5: Ground-truthing and One Health. Community volunteers submit contextual stream reports with automatic 1.1 km privacy fuzzing. In our One Health panel, aquatic life remains protected, but Human Contact is explicitly marked NOT ASSESSED because dissolved oxygen cannot confirm pathogen safety without microbial lab cultures."* |
| **2:55 – 3:15** | **Closing: Synthesis**<br>*Scrolls to Limitations Panel* | *"In conclusion, AquaRehearsal-X bridges the gap between sensor telemetry, calibrated ML, proactive rehearsal, and community verification. It provides decision-makers with the foresight and operational humility needed to protect urban waterways before the rain falls. Thank you!"* |

---

## 4. 2-Minute Technical Explanation for Judges

> *"AquaRehearsal-X is built upon four rigorous engineering foundations:*
>
> *First, **Data Ingestion and Provenance**: We regularize continuous USGS NWIS stream telemetry (DO, temperature, discharge) with Open-Meteo hourly meteorological reanalysis, producing a clean, leakage-free 32,809-hour dataset spanning 2023 to 2026. All future features are strictly blocked during training.*
>
> *Second, **Machine Learning and Calibrated Uncertainty**: Our core forecaster is a LightGBM gradient-boosted regressor equipped with 156 backward rolling features. Rather than returning uncalibrated point estimates, we train dedicated quantile regressors ($q_{10}, q_{50}, q_{90}$) that enforce monotonicity, coupled with an inductive split conformal calibration step that guarantees a finite-sample 90% marginal coverage band ($\pm 1.955\text{ mg/L}$). If input features fall outside the training domain's Delaunay convex hull, the system refuses extrapolation.*
>
> *Third, **The Storm Tolerance Envelope (STE)**: We formulate an empirical safe-boundary function $R_{safe}(T)$ derived from 58 cataloged historical storm disturbances. As pre-storm water temperature rises from 5°C to 28°C, oxygen saturation decreases, causing the allowable storm rainfall before threshold violation to contract monotonically from $>50\text{ mm}$ to $<20\text{ mm}$.*
>
> *Fourth, **Closed-Loop Decision Support**: We combine empirical lag-to-nadir distributions ($P_{10} = 6.5\text{h}, P_{50} = 10.0\text{h}$) with a continuous Streeter-Phelps mass-balance solver to rehearse intervention archetypes. Interventions are passed through a logistical feasibility filter comparing mobilization lead times against the earliest plausible nadir deadline. Field Check volunteer data is segregated into a dual-track ledger with coordinate coarsening and EXIF stripping, ensuring qualitative observations provide contextual evidence without polluting quantitative training labels.*
>
> *The entire system is reproducible, tested across 89 passing unit and integration tests, and runs fully offline."*

---

## 5. Five Likely Judge Questions & Evidence-Based Answers

### Question 1: "How do you prevent data leakage between historical storm features and your 72-hour forecast target?"
**Answer:**
> *"We enforce strict backward-looking feature engineering. Every rolling mean, standard deviation, and antecedent rainfall sum is computed strictly over $(t_0 - \Delta t, t_0]$. In our test suite (`tests/test_stage2_forecasting.py` and `tests/test_stage6_integration.py`), we explicitly mutate future values at $t > t_0$ and prove that the extracted feature vector and model prediction remain bit-for-bit identical. Furthermore, during Historical Replay (Event 54), all data after the forecast issue time is physically excluded until the verification step."*

### Question 2: "Your Storm Tolerance Envelope shows threshold breach risks below 5.0 mg/L. Did you actually observe fish kills or collapses in your training data?"
**Answer:**
> *"No, and we disclose this prominently on the dashboard and in our model card. In our 58-event historical catalog (2023–2026), the lowest observed storm minimum was 5.65 mg/L during Event 54. The Schuylkill River at Philadelphia has a large drainage basin (1,893 sq mi) that retains substantial baseflow. Therefore, our breach risk curves represent statistically calibrated quantile extrapolations rather than observed ecological collapses. We label the boundary as preliminary and recommend multi-year or smaller-watershed expansions."*

### Question 3: "Why not just use an automated optimization algorithm to tell managers which intervention is best?"
**Answer:**
> *"We implemented a strict Anti-Ranking Rule by design. In environmental systems engineering, recommending an automated 'winner' among interventions without site-specific hydrodynamic validation or regulatory permitting creates severe liability. Instead, AquaRehearsal-X acts as a scenario rehearsal tool: we display the physical assumptions, mass-balance recovery, and logistical feasibility constraints, empowering human domain experts to make the final determination."*

### Question 4: "Citizen science reports are notoriously noisy. How do you prevent bad or malicious submissions from corrupting your forecasts?"
**Answer:**
> *"We implement a 4-Tier Data Segregation Architecture and a strict Anti-Labeling Rule. Citizen observations are stored in an independent validation ledger and are NEVER fed back into the ML model as ground-truth training labels. Submissions pass through automated validation: coordinates are coarsened to ~1.1 km to protect privacy, EXIF metadata is stripped, PII is redacted, and duplicate submissions within 15 minutes are deduplicated. They serve purely as contextual corroboration."*

### Question 5: "How does AquaRehearsal-X incorporate One Health beyond just showing a label?"
**Answer:**
> *"One Health recognizes the interdependence of environmental, animal, and human health. We reflect this through explicit differentiation:
> 1. Environmental health is tracked through continuous reaeration rates and stream assimilative capacity.
> 2. Animal health evaluates whether dissolved oxygen protects warm-water fisheries from acute mortality ($>3.0\text{ mg/L}$).
> 3. Human health: Crucially, we mark Human Contact Risk as **NOT ASSESSED**. Many environmental platforms falsely equate clear or oxygenated water with pathogen safety. We prevent dangerous public health assumptions by explicitly stating that microbial pathogens (*E. coli*, *Enterococci*) cannot be assessed without certified laboratory culture assays."*

---

## 6. Differentiated Contribution & Transparent Limitation

### Differentiated Contribution
Unlike existing environmental dashboards that only display retrospective time-series or uncalibrated black-box forecasts, AquaRehearsal-X provides:
1. **The Storm Tolerance Envelope:** An intuitive 2D safe-boundary engine that operationalizes complex meteorological-hydrological interactions for decision-makers before storm runoff begins.
2. **Action Window Feasibility Gating:** Decision deadlines paired with real-world logistical mobilization lead times, preventing unrealistic emergency responses.
3. **Scientifically Humble Guardrails:** Out-of-domain input refusal, conformal prediction intervals, and strict anti-labeling isolation.

### Transparent Statement of the Primary Scientific Limitation
> **"AquaRehearsal-X is calibrated exclusively on a single monitoring station (USGS 01474500) where the historical storm catalog contains zero observed dissolved oxygen breaches below the 5.0 mg/L standard. As a result, the risk boundaries and simulated intervention benefits represent theoretical and statistical projections that require multi-station calibration and in-situ hydrodynamic dye testing before operational deployment."**
