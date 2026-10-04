# AquaRehearsal-X - Stage 1 Engineering & Scientific Notes

## Real Data Foundation Notes
- USGS National Water Information System (NWIS) Instantaneous Values (IV) REST API was evaluated.
- Real continuous parameters:
  - Dissolved Oxygen: `00300` (mg/L)
  - Water Temperature: `00010` (°C)
  - Stream Discharge: `00060` (cfs)
  - Turbidity: `63680` (FNU)
  - Gage Height: `00065` (ft)
- Zero synthetic data used in reports or data processing. Synthetic data strictly confined to labeled test fixtures in `tests/`.
- Primary recommended monitoring station: **USGS 01474500 (Schuylkill River at Philadelphia, PA)** with 99.69% DO completeness over 180 continuous days.
