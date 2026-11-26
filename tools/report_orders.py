"""Write report/orders_table.tex: the work-order table and a few macros for the
report, taken from the work orders themselves (set A) and from model runs.
Run from the repo root:  python tools/report_orders.py"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from coldfront import contracts as C   # noqa: E402

SHORT = dict(T_inlet_max="inlet", compute_lost_pct="compute lost", pue="PUE", cost_cooling="cooling bill",
             water_m3="water", wue_L_per_kWh="water", minutes_over_limit="time above 27\\uC", E_comp_MWh="compressors")
UNIT = {"°C": "\\uC", "%": "\\upct", "$": "", "m³": "\\,m$^3$", "L/kWh": "\\,L/kWh", "min": "\\,min", "MWh": "\\uMWh", "": ""}
EVENT = dict(first_shift="none", heatwave="{t}, +{v:.0f}\\uC\\ until 19:00; water permit",
             chiller_down="{t}, one chiller trips before a 4.5\\uMW\\ training run",
             price_spike="{t}, prices will be $\\times${v:g} from 16:00 to 21:00", not_a_drop="{t}, +{v:g}\\uMW\\ of load",
             blackwell="{t}, two chillers trip")
LEVER = dict(first_shift="water temperature", heatwave="tower or dry cooler, by hour", chiller_down="free cooling",
             price_spike="when the tank charges", not_a_drop="rise; night-charged tank", blackwell="facility water temperature")
THERMO = dict(first_shift="lift and COP", heatwave="wet-bulb against dry-bulb sink", chiller_down="capacity, free cooling",
              price_spike="transient storage tank", not_a_drop="lift by time of day, pump work",
              blackwell="liquid cooling, no cycle")


def tgt(t):
    v = f"{t.limit:,.{t.nd}f}"
    if t.unit == "$":
        v = "\\$" + v
    if t.limit == 0:
        return dict(compute_lost_pct="no compute lost", minutes_over_limit="no time above 27\\uC",
                    wue_L_per_kWh="no water")[t.metric]
    if t.metric == "T_inlet_max" and t.limit > 30:
        return f"coolant $\\le$ {v}\\uC"
    return f"{SHORT[t.metric]} $\\le$ {v}{UNIT[t.unit]}"


rows = []
for key, sets in C.VARIANTS.items():
    o = sets[0]
    ev = [e for e in o.events if e.pause]
    if key == "price_spike":
        v = [e for e in o.events if e.kind == "price"][0].value
    else:
        v = ev[0].value if ev else 0
    e = EVENT[key].format(t=f"{int(ev[0].t):02d}:{int(ev[0].t % 1 * 60):02d}" if ev else "", v=v)
    g, _ = C.evaluate(o, C.run_order(o, C.plans_for(o, o.solution)).metrics)
    g0, _ = C.evaluate(o, C.run_order(o, C.plans_for(o, ())).metrics)
    assert g == "A" and g0 in "CD"
    rows.append(f"{o.number} {o.title.replace('a.m.', 'a.m.')} & {e} & {'; '.join(tgt(t) for t in o.targets)} & "
                f"{LEVER[key]} & {THERMO[key]} \\\\")
tests = open(os.path.join(ROOT, "tests", "test_physics.py")).read()
n_tests = tests.count("def test_") + sum(m.count(",") for m in re.findall(r"parametrize\([^\[]*\[([^\]]*)\]", tests))
from coldfront.plant import MAX_FLOW   # noqa: E402
out = ["% Written by tools/report_orders.py; do not edit by hand.",
       f"\\newcommand{{\\NTests}}{{{n_tests}}}", f"\\newcommand{{\\NSets}}{{{sum(len(v) for v in C.VARIANTS.values())}}}",
       f"\\newcommand{{\\MaxFlow}}{{{MAX_FLOW:g}}}",
       "\\newcommand{\\OrdersRows}{%"] + rows + ["}"]
open(os.path.join(ROOT, "report", "orders_table.tex"), "w").write("\n".join(out) + "\n")
print("\n".join(out))
