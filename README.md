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
| Console | Free play in four numbered steps: choose the scenario, set the plant, watch the day, explore the results. After every change a strip says what you changed and which equipment felt it. "Ask the plant" answers questions typed in your own words (keyword matching on the run's numbers, not an AI). |
| Chiller lab | One refrigeration cycle: refrigerant, temperatures, efficiency, P-h and T-s diagrams. |
| Compare | Two plans on the same day, with a table of differences. |
| Proof | Every validation check, recomputed live. |
| Build a chiller | A three-minute game for visitors with no engineering background: put the four parts of a chiller in a loop, watch the refrigerant go round, then choose how cold to make the water. |

The plant drawing on every page shows each machine's state by colour (normal, high demand, inefficient, critical, offline), animates the water in its flow direction, marks the day's key moments on the timeline, and has an "Explore connections" mode: click a machine or a pipe to light up what it is connected to. Every page has its own guided tour.

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
