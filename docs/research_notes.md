# COLDFRONT research notes: grounding the model fixes

Research date: Nov 19, 2026. Purpose: answer the professor-review critiques with published data before changing the model.

## 1. Real chiller efficiency (the COP ~11 question)

**Code limits, ASHRAE 90.1 Table 6.8.1-3, water-cooled centrifugal, ≥600 tons (our 3 MW = 853 tons):**
- Path A (full-load optimized): FL ≤ 0.560 kW/ton, IPLV ≤ 0.500
- Path B (part-load / VSD): FL ≤ 0.585 kW/ton, IPLV ≤ 0.380
- Source: WA State Energy Code table C403.3.2(3), a replica of 90.1 Table 6.8.1-3.

**Rating points, AHRI 550/590 IPLV:**
- 44 °F leaving chilled water.
- Weighting: 1% at 100% load / 85 °F entering condenser water (ECWT), 42% at 75% / 75 °F, 45% at 50% / 65 °F, 12% at 25% / 65 °F.
- Sources: Trane, ASHRAE Journal Dec 2009; PE study guide.

**Reference performance curves, 90.1-2022 Appendix J (via COMNET):**

- EIR-FT = a + b·t_chws + c·t_chws² + d·t_cws + e·t_cws² + f·t_chws·t_cws (°F; valid t_chws 39–60 °F, t_cws 55–104 °F).
- EIR-FPLR = a + b·PLR + c·PLR².
- P = P_rated × EIR-FT × EIR-FPLR × CAP-FT.
- Minimum PLR 0.25 when these curves are used.

| ≥600 tons | a | b | c | d | e | f |
|---|---|---|---|---|---|---|
| EIR-FT Path A | 0.551957 | −0.036196 | 0.0003 | 0.028396 | −0.000147 | 0.000029 |
| EIR-FT Path B | 0.593414 | −0.028948 | 0.000224 | 0.024197 | −0.000126 | 0.000027 |
| EIR-FPLR Path A | 0.290891 | 0.059366 | 0.649421 | | | |
| EIR-FPLR Path B | 0.058583 | 0.205486 | 0.736345 | | | |

- CAP-FT (COMNET default, centrifugal): a −0.29861976, b 0.02996076, c −0.00080125, d 0.01736268, e −0.00032606, f 0.00063139.
- Checked: both EIR-FT curves equal 1.000 at 44/85 °F.
- IPLV from the curves: Path A 0.491, Path B 0.388 kW/ton. These match the code limits (0.50 / 0.38), so the curves are a consistent reference.

**Comparison with the current model (electrical COP):**

| CHWS / ECWT (°C) | Model, full load | Ref. A, full load | Ref. B, full load | Ref. B, 50% load |
|---|---|---|---|---|
| 6.7 / 29.4 (AHRI) | 6.42 | 6.29 | 6.01 | 8.70 |
| 10 / 23.9 | 9.66 | 6.95 | 6.58 | 9.53 |
| 10 / 18.3 | 12.93 | 7.75 | 7.21 | 10.44 |
| 16 / 21 | 17.84 | 7.40 | 7.06 | 10.23 |

**Conclusion: the professor is right.**
- At low lift and full load, the model is about 40–150% too optimistic, because η_s is constant. Real full-load COP rises only slowly as lift falls.
- The real large gains at low lift come at **part load with VSD**. One example: 0.57 kW/ton at 50% load and 85 °F falls to 0.25 kW/ton at 60 °F, about 10–13% better per 5 °F of condenser relief (Facilitiesnet).
- VSD centrifugals are most efficient around 40–60% load; including pumping, the best system point is 60–75% (ACHR News). Constant-speed machines peak at 70–90%.
- Current model IPLV is 0.398, but its part-load shape is backwards: it penalizes 25% load.

**Minimum load / surge:**
- VFD centrifugal: about 10–15% minimum load. Standard centrifugal: 40–50%.
- COMNET default minimum unloading: centrifugal 10%. The Appendix J curves use 0.25.
- Some modern two-stage data-center machines claim stability to 10% load and "virtually zero" minimum lift (Carrier 19MV).
- Optimum efficiency sits near the surge line.

**Data-center chillers today:**
- Carrier 19MV4 (R-1234ze, magnetic bearings): COP 6.75 and IPLV 11.4 at AHRI conditions; chilled water up to 35 °C.
- Mitsubishi MECH-iC: 65–75 °F leaving water, 18–20 °F ΔT.
- Trane 1 GW AI factory reference design: facility loop 22/32 °C and 26/36 °C; chillers of 6.87–10.24 MW.

## 2. Plan for the chiller model (keeps the thermodynamic cycle as the engine)

1. Keep the CoolProp cycle and per-device S_gen.
2. Replace constant η_s with η_s(PR, PLR): it falls at low pressure ratio (centrifugal impeller off its design head) and peaks near 50–70% PLR for VSD.
3. Calibrate the η_s function by least squares so the cycle reproduces the Path B reference curves inside their valid range.
4. **Validate on held-out points:** IPLV vs 0.380 limit; full load at AHRI vs 0.585; the 50% / 60 °F point vs about 0.25–0.35 kW/ton.
5. Minimum PLR 0.15 (VSD); below that, cycle on/off. Chiller staging uses the most efficient number of machines, not the fewest.
6. Show second-law efficiency vs lift. It should now fall at low lift, as real machines do.

Effect on results: design-day COP will drop from about 11 toward 7–9 at full load. Low-lift, part-load operation stays high. Every report number and resume number gets regenerated.

## 3. Pump heat
- EnergyPlus assumes all pump shaft heat ends up in the closed-loop fluid (head is lost to friction). It adds a user fraction of motor losses to the fluid.
- **Fix:** add CHW pump shaft power to the chilled-water load, and condenser-water pump shaft power to the condenser load. Motor losses go to the room.

## 4. Cooling tower and water balance
- **Approach model:** the YorkCalc correlation (EnergyPlus default, 27 coefficients) gives approach = f(T_wb, range, liquid-to-gas ratio), in °C.
  - Valid: T_wb −34.4 to 26.7 °C; range 1.1–22.2 °C; approach 1.1–40 °C; water flow ratio 0.75–1.25.
  - Coefficients are in the EnergyPlus Engineering Reference, cooling towers chapter.
  - This makes the approach an output that shrinks at part load, not a fixed 4 K.
- **Design guidance:** specify towers for a 5–7 °F approach in data centers (LBNL data-center guide).
- **Water balance (makeup = evaporation + drift + blowdown):**
  - Evaporation by the saturated-exit-air method: ṁ_air·(ω_out − ω_in). Rule of thumb: about 1% of circulating flow per 10 °F of range.
  - Drift: 0.001–0.2% of circulating flow (0.01% with drift eliminators).
  - Blowdown = E / (COC − 1), with typical cycles of concentration 3–5.
  - Sources: EPA WaterSense; DOE FEMP BMP #10; EnergyPlus.
- **Fix:** replace the flat ×1.25 with E + drift + E/(COC−1), and report it as a mass balance table.

## 5. Liquid cooling (only if time allows)
- ASHRAE TC9.9 5th ed. classes: W17, W27, W32, W40, W45, W+ (facility water supply limits, °C).
- Uptime Institute: facility water is converging around 32 °C.
- GB200 NVL72:
  - Up to about 132 kW per rack.
  - Maximum liquid inlet 45 °C, maximum return 65 °C, up to 130 L/min per rack (QCT).
  - About 1.5 L/min per kW.
- CDUs: about 4–5 °C approach (Gigabyte in-row 1,350 kW at 4 °C; CoolIT CHx2000, 2 MW at 5 °C).

## 6. Sources
- WA State Energy Code, Table C403.3.2(3) (replica of ASHRAE 90.1 Table 6.8.1-3).
- COMNET Modeling Guidelines §3.8.2 Chillers (90.1-2022 Appendix J curves).
- Trane / ASHRAE Journal, Dec 2009, IPLV article.
- Facilitiesnet, "Ignore peak load chiller efficiency"; ACHR News, "Optimizing centrifugal chiller systems".
- EnergyPlus Engineering Reference: Pumps; Cooling Towers (YorkCalc, evaporation, drift, blowdown).
- EPA WaterSense at Work §6.3; DOE FEMP BMP #10.
- Upsite / ASHRAE TC9.9 5th ed. liquid classes; DCD on Uptime's 32 °C facility water.
- QCT QoolRack GB200 brief; NVIDIA Blackwell blog; Gigabyte GB200 POD page.
- Carrier 19MV product page; Mitsubishi MECH-iC; Trane 1 GW AI Factory Reference Design.
