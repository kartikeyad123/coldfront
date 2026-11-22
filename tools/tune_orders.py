"""Set the targets of every work-order problem set from model runs, and write
coldfront/order_numbers.py. For each set it runs three plays: do nothing, the
reference 'passing' play and the reference 'solution'. The pass limit sits just
beyond the passing play and the A level sits between passing and solution, so
an A always exists and doing nothing never passes.
Run from the repo root:  python tools/tune_orders.py"""
import math
import os
import pprint
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from coldfront import contracts as C   # noqa: E402

EFF = dict(first_shift="pue", heatwave="pue", chiller_down="pue", price_spike="cost_cooling", not_a_drop="pue",
           blackwell="pue")
SAME = dict(chiller_down=(0.05, 0.012), blackwell=(0.012, 0.001))     # (pass margin, A margin) when one play does both


def up(x, step):
    return round(math.ceil(x / step - 1e-9) * step, 6)


def metrics(o, steps):
    return C.run_order(o, C.plans_for(o, steps)).metrics


out = {}
for key in C.VARIANTS:
    out[key] = []
    for i in range(3):
        o = C.VARIANTS[key][i]
        m = EFF[key]
        N, P, S = (metrics(o, st) for st in ((), o.passing, o.solution))
        cost = m == "cost_cooling"
        if key in SAME:
            lim, a = S[m] + SAME[key][0], S[m] + SAME[key][1]
        else:
            gap = P[m] - S[m]
            assert gap > 0, (key, i, P[m], S[m])
            lim, a = P[m] + 0.35 * gap, S[m] + 0.35 * gap
        lim = up(lim, 50) if cost else up(lim, 0.001)
        a = up(a, 50) if cost else up(a, 0.001)
        d = dict(limit=lim, a=a)
        if key == "heatwave":
            d["permit"] = up(max(P["water_m3"], S["water_m3"]) * 1.04, 10)
            d["tower_all"] = round(N["water_m3"], -1)
            assert d["permit"] < N["water_m3"]
        assert S[m] <= a < lim and (lim < N[m] or key in SAME or key == "heatwave"), (key, i, S[m], a, lim, N[m])
        out[key].append(d)
        print(key, i, "nothing", round(N[m], 3), "passing", round(P[m], 3), "solution", round(S[m], 3), d)

with open(os.path.join(ROOT, "coldfront", "order_numbers.py"), "w") as f:
    f.write('"""Targets for each work-order problem set. Written by tools/tune_orders.py; do not edit by hand."""\n')
    f.write("NUMBERS = " + pprint.pformat(out, width=100) + "\n")
