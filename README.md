# COLDFRONT

**Run the cooling plant of an AI data center.** An interactive thermodynamics game built on a
vapor-compression refrigeration cycle. AME 310 (Engineering Thermodynamics I, USC) final project,
Part D: refrigeration cycle. Kartikeya Daiya, Fall 2026.

You are the shift engineer for an 8 MW AI data hall. Set the plant, run the day, react when
something breaks, and get graded on engineering margins.

## Run it

```
pip install -r requirements.txt
streamlit run app.py
```

## What is inside

| View | What it does |
|---|---|
| Work orders | Six shifts with fixed event timelines. The day pauses at each event so you can react. Grades A to D from margins. |
| Console | Free play: any site, workload, price and plant. |
| Chiller lab | One refrigeration cycle: refrigerant, temperatures, efficiency, P-h and T-s diagrams. |
| Compare | Two plans on the same day, with a table of differences. |
| Proof | Every validation check, recomputed live. |

## The model (`coldfront/`)

- `chiller.py`: CoolProp refrigeration cycle; evaporator and condenser of fixed size; variable-speed
  centrifugal compressor map calibrated to ASHRAE 90.1 reference ratings.
- `tower.py`: cooling-tower approach (YorkCalc correlation) and water mass balance.
- `plant.py`: the plant at one instant: staging, free cooling, pumps (pump work becomes heat), fans.
- `day.py`: 24-hour simulation. Two transient control volumes (data hall, storage tank), forward Euler.
- `checks.py`: textbook benchmark, ratings, calibration, first and second laws, lost-work closure, audits.
- `contracts.py`, `scenarios.py`: work orders, events, weather, workloads, prices.

The interface (`app.py`, `ui/`) contains no physics.

## Proof

```
pytest -q        # 21 physics tests
```

- Textbook cycle (Cengel and Boles, Example 11-1): within 0.06 %.
- Chiller: 0.577 kW/ton at full load and 0.362 kW/ton IPLV (ASHRAE 90.1 limits 0.585 and 0.380).
- First and second laws at 108 operating points; Gouy-Stodola lost-work closure; whole-day energy
  and mass balances.

`python report_figures.py && python gen_numbers.py` regenerates every figure and number in the report.
