"""
explain.py - Cause and effect in plain words. Given two solved days (before and
after a change), say what was changed, which equipment felt it and by how much.
Every number is read from the two model runs; nothing is estimated here.
"""
import numpy as np

NAMES = dict(T_chws_C="water supply", dT_chw="water temperature rise", n_chillers="chillers available", fluid="refrigerant",
             eta_rated="compressor efficiency", rejection="heat rejection", free_cooling="free cooling", tank="storage tank",
             tank_MWh="tank size", tank_rate_MW="tank rate", price_charge="charge price", price_discharge="discharge price",
             rack_cooling="rack cooling")
UNITS = dict(T_chws_C=" °C", dT_chw=" °C", tank_MWh=" MWh", tank_rate_MW=" MW", price_charge=" $/MWh", price_discharge=" $/MWh")
WORDS = {True: "on", False: "off", "tower": "cooling tower", "dry": "dry cooler", "air": "air", "liquid": "liquid"}


def _v(k, v):
    if isinstance(v, (bool, str)):
        return WORDS.get(v, str(v).replace("(E)", ""))
    return f"{v:g}{UNITS.get(k, '')}"


def stats(day):
    """A few daily numbers per piece of equipment."""
    x, m = day.series, day.metrics
    on = x["n_on"] > 0
    hours = float(x["hour"][-1] - x["hour"][0]) if len(x["hour"]) > 1 else 24.0
    mean = lambda a: float(np.mean(a)) * hours / 1e6            # W -> MWh over the run
    avg_on = lambda k: float(np.mean(x[k][on])) if on.any() else float("nan")
    return dict(
        lift=float(np.mean((x["T_cond"] - x["T_evap"])[on])) if on.any() else float("nan"),
        T_evap=avg_on("T_evap"), T_cond=avg_on("T_cond"), cop=m["cop_mean"], E_comp=m["E_comp_MWh"],
        E_pump=mean(x["P_chw"] + x["P_cw"]), E_fan=mean(x["P_fans"]), sink=float(np.mean(x["T_sink"])),
        fc_h=m["free_cooling_hours"], water=m["water_m3"], peak=m["T_inlet_max"], lost=m["compute_lost_pct"],
        over=m["minutes_over_limit"], pue=m["pue"], bill=m["cost_cooling"], E_it=m["E_it_MWh"],
        E_dis=mean(x["Q_dis"]), flow=float(np.mean(x["m_chw"])), n_on=float(np.mean(x["n_on"])),
        short=float(np.max(x["shortfall"])) / 1e6, peak_it=float(np.max(x["Q_it_req"])) / 1e6)


def _chg(a, b, nd=1, unit=""):
    return f"{a:,.{nd}f} → {b:,.{nd}f}{unit}"


def fx_html(fx, cls="cf-fx"):
    """The same cause-and-effect chain as a block of page HTML."""
    chips = "".join(('<span class="arrow">→</span>' if k else "") + f'<div class="chip"><b>{x["label"]}</b>{x["text"]}</div>'
                    for k, x in enumerate(fx["items"]))
    return f'<div class="{cls}"><div class="h">{fx["head"]}</div><div class="chain">{chips}</div></div>'


def effects(prev, cur, prev_ctx=None, cur_ctx=None, labels=None, stages=None):
    """What changed between two days and what it did. `ctx` is an optional
    (site label, workload label, price label) tuple. Returns None if nothing
    changed, else dict(head, items=[dict(dev, label, text)], result)."""
    a, b = prev.settings.__dict__, cur.settings.__dict__
    changed = [k for k in NAMES if a.get(k) != b.get(k)]
    if not cur.settings.tank:
        changed = [k for k in changed if not k.startswith(("tank_", "price_"))]
    what = [f"{NAMES[k]} {_v(k, a[k])} → {_v(k, b[k])}" for k in changed]
    if stages:                      # a shift played in stages: list of (when, settings before, settings now)
        what, changed = [], []
        for when, pa, pb in stages:
            ks = [k for k in NAMES if pa.get(k) != pb.get(k) and (pb.get("tank") or not k.startswith(("tank_", "price_")))]
            changed += ks
            what += [f"{when}, {NAMES[k]} {_v(k, pa[k])} → {_v(k, pb[k])}" for k in ks]
        a, b = stages[-1][1], stages[-1][2]
        for when, pa, pb in stages:
            if pa.get("T_chws_C") != pb.get("T_chws_C"):
                a, b = pa, pb
    for i, name in enumerate(("site", "workload", "electricity price")):
        if prev_ctx and cur_ctx and prev_ctx[i] != cur_ctx[i]:
            what.append(f"{name}: {cur_ctx[i]}")
    if not what:
        return None
    A, B = stats(prev), stats(cur)
    ok = lambda k: A[k] == A[k] and B[k] == B[k]
    rel = lambda k, tol: ok(k) and abs(B[k] - A[k]) > tol * max(abs(A[k]), 1e-9)
    absd = lambda k, tol: ok(k) and abs(B[k] - A[k]) > tol
    up = lambda k: "rose" if B[k] > A[k] else "fell"
    items = []
    if absd("peak_it", 0.2) or (prev_ctx and cur_ctx and prev_ctx[1] != cur_ctx[1]):
        items.append(dict(dev="hall", label="Data hall: heat to remove",
                          text=f"The servers turn their power into heat. Peak heat load {_chg(A['peak_it'], B['peak_it'], 1, ' MW')}."))
    if "n_chillers" in changed:
        cap = cur.settings.chiller_cap_MW
        items.append(dict(dev="chiller", label="Chiller capacity",
                          text=f"Cooling available from chillers {a['n_chillers'] * cap:g} → {b['n_chillers'] * cap:g} MW. "
                               f"Worst shortfall {_chg(A['short'], B['short'], 1, ' MW')}."))
    if absd("sink", 0.5):
        items.append(dict(dev="tower", label="Heat rejection",
                          text=f"The water it sends back {up('sink')}: {_chg(A['sink'], B['sink'], 1, ' °C')} on average. "
                               "That is the hot side the chillers push against."))
    if ok("lift") and (absd("lift", 0.4) or absd("cop", 0.15)):
        why = ""
        if "T_chws_C" in changed:
            why = "Warmer water raises the evaporating temperature. " if b["T_chws_C"] > a["T_chws_C"] else "Colder water lowers the evaporating temperature. "
        lift = (f"Lift {_chg(A['lift'], B['lift'], 1, ' K')}, so COP {_chg(A['cop'], B['cop'], 1)}" if absd("lift", 0.4)
                else f"Same lift ({B['lift']:.0f} K), but COP {_chg(A['cop'], B['cop'], 1)}")
        items.append(dict(dev="chiller", label="Chillers",
                          text=f"{why}{lift} and the compressors used {_chg(A['E_comp'], B['E_comp'], 1, ' MWh')}."))
    elif A["cop"] == A["cop"] and B["cop"] != B["cop"]:
        items.append(dict(dev="chiller", label="Chillers", text=f"They never had to run. Compressor electricity {_chg(A['E_comp'], B['E_comp'], 1, ' MWh')}."))
    elif rel("E_comp", 0.03):
        items.append(dict(dev="chiller", label="Chillers", text=f"Compressor electricity {_chg(A['E_comp'], B['E_comp'], 1, ' MWh')}."))
    if absd("fc_h", 0.3):
        items.append(dict(dev="fc", label="Free cooling",
                          text=f"It works when the tower water is colder than the return water. Full-load hours {_chg(A['fc_h'], B['fc_h'], 1, ' h')}."))
    if rel("E_pump", 0.05):
        items.append(dict(dev="pump_chw", label="Pumps",
                          text=f"Average chilled-water flow {_chg(A['flow'], B['flow'], 0, ' kg/s')}; pump electricity {_chg(A['E_pump'], B['E_pump'], 2, ' MWh')}."))
    if absd("E_dis", 0.3):
        items.append(dict(dev="tank", label="Storage tank",
                          text=f"Cooling delivered from stored cold water: {_chg(A['E_dis'], B['E_dis'], 1, ' MWh')}. The chillers rest while it discharges."))
    if rel("water", 0.05) or (A["water"] > 1) != (B["water"] > 1):
        items.append(dict(dev="tower", label="Water", text=f"Make-up water {_chg(A['water'], B['water'], 0, ' m³')}."))
    if absd("peak", 0.3) or absd("lost", 0.05):
        t = f"Hottest moment at the racks {_chg(A['peak'], B['peak'], 1, ' °C')}."
        if A["lost"] > 0 or B["lost"] > 0:
            t += f" Compute lost {_chg(A['lost'], B['lost'], 1, ' %')}."
        items.append(dict(dev="hall", label="Data hall: result", text=t))
    result = f"PUE {_chg(A['pue'], B['pue'], 3)} · cooling bill ${A['bill']:,.0f} → ${B['bill']:,.0f}"
    if not items:
        items.append(dict(dev="hall", label="No visible effect", text="That change did not move anything by a noticeable amount on this day."))
    head = ("You changed " if labels is None else labels) + "; ".join(what) + ".  " + result
    return dict(head=head, items=items[:6], result=result)
