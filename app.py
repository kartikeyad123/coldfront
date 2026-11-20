"""
COLDFRONT - run the cooling plant of an AI data center.
Interactive thermodynamics laboratory for AME 310 (Part D, refrigeration cycle).

This file is the interface only: page layout, controls and the game flow.
All thermodynamics lives in the coldfront/ package.      Run:  streamlit run app.py
"""

from dataclasses import replace
import numpy as np
import pandas as pd
import streamlit as st

from coldfront.plant import PlantSettings, DEVICES, C2K
from coldfront.day import simulate_day
from coldfront.chiller import solve_cycle, REFRIGERANTS, ETA_PEAK
from coldfront.scenarios import CLIMATES, WORKLOADS, TARIFFS
from coldfront.contracts import ORDERS, WORK_ORDERS, run_order, evaluate
from coldfront import checks
from ui import charts
from ui.theme import CSS, header
from ui.plant_view import plant_html
from ui.cycle_view import cycle_html

st.set_page_config(page_title="COLDFRONT", page_icon="❄", layout="wide", initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)

VIEWS = ["Home", "Work orders", "Console", "Chiller lab", "Compare", "Proof"]
GWP = {"R134a": "GWP 1430", "R1234ze(E)": "GWP 1", "R717": "GWP 0", "R290": "GWP 3"}
PRESETS = {
    "As built": dict(),
    "Warm water": dict(T_chws_C=16.0, dT_chw=8.0),
    "Storage": dict(tank=True, tank_MWh=40.0, tank_rate_MW=5.0),
    "Dry (no water)": dict(rejection="dry", T_chws_C=16.0, dT_chw=8.0),
    "Liquid-cooled GPU hall": dict(rack_cooling="liquid", T_chws_C=30.0, dT_chw=8.0),
}
PLANT_H = 850


def go(view, **kw):
    st.session_state["view"] = view
    st.session_state.update(kw)


def H(text):
    st.markdown(f'<div class="cf-h">{text}</div>', unsafe_allow_html=True)


def card(html, cls="cf-card"):
    st.markdown(f'<div class="{cls}">{html}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- cached model calls
def freeze(d):
    return tuple(sorted(d.items()))


@st.cache_data(show_spinner=False, max_entries=96)
def run_day(settings_items, climate, workload, tariff="retail"):
    return simulate_day(PlantSettings(**dict(settings_items)), climate, workload, tariff_key=tariff)


@st.cache_data(show_spinner=False, max_entries=96)
def run_wo(key, plans_items, until):
    return run_order(WORK_ORDERS[key], [PlantSettings(**dict(p)) for p in plans_items], until)


@st.cache_data(show_spinner=False, max_entries=32)
def cycle_anim(settings_items, climate, workload, tariff, kind):
    return charts.cycle_day_animation(run_day(settings_items, climate, workload, tariff), kind)


@st.cache_data(show_spinner=False)
def proof_data():
    rows, _ = checks.textbook_benchmark()
    eb = []
    for c in CLIMATES:
        m = simulate_day(PlantSettings(), c, "inference").metrics
        eb.append(dict(site=CLIMATES[c].label, energy=m["energy_balance_err_pct"], tower=m["tower_mass_err_pct"],
                       pue=m["pue"], cop=m["cop_mean"]))
    mt = simulate_day(PlantSettings(n_chillers=3, tank=True, tank_soc0=1.0), "la_typical", "training").metrics
    return dict(tb=rows, mv=checks.map_validation(), law=checks.cycle_law_checks(), ex=checks.exergy_audit(),
                audit=checks.step_audit()[0], eb=eb, tank=mt, neg=checks.negative_control(),
                ts=checks.timestep_study(), we=checks.worked_example(), ahri=checks.ahri_rating()["kw_per_ton"])


@st.cache_data(show_spinner=False)
def P_iplv():
    return checks.iplv()["iplv"]


# ---------------------------------------------------------------- shared pieces
def settings_toolbar(prefix, locks=None, defaults=None):
    """Four drop-down panels, one per part of the plant. Locked settings (set
    by a work order) are shown but cannot be changed."""
    locks = locks or {}
    d = PlantSettings().__dict__.copy()
    d.update(defaults or {})
    d.update(locks)
    v = dict(defaults or {})
    c = st.columns(4)
    with c[0].popover("Chilled water", width="stretch"):
        v["rack_cooling"] = st.radio("Cooling at the racks", ["air", "liquid"], ["air", "liquid"].index(d["rack_cooling"]),
                                     format_func=lambda k: "Air: coils and fans, limit 27 °C inlet" if k == "air"
                                     else "Liquid: direct-to-chip, limit 40 °C coolant",
                                     key=prefix + "rc", disabled="rack_cooling" in locks)
        hi = 20.0 if v["rack_cooling"] == "air" else 40.0
        v["T_chws_C"] = st.slider("Water supply temperature [°C]", 6.0, hi, min(float(d["T_chws_C"]), hi), 0.5,
                                  key=prefix + "chws" + v["rack_cooling"])
        v["dT_chw"] = st.slider("Return minus supply [K]", 4.0, 12.0, float(d["dT_chw"]), 0.5, key=prefix + "dt")
        st.caption("Warmer water means a smaller lift and less compressor work. "
                   "The racks receive this water plus " + ("8 K." if v["rack_cooling"] == "air" else "4 K."))
    with c[1].popover("Chillers", width="stretch"):
        v["n_chillers"] = st.slider("Chillers available", 1, 4, int(d["n_chillers"]), key=prefix + "n",
                                    disabled="n_chillers" in locks)
        v["fluid"] = st.selectbox("Refrigerant", list(REFRIGERANTS), list(REFRIGERANTS).index(d["fluid"]),
                                  format_func=lambda k: f"{REFRIGERANTS[k]} · {GWP[k]}", key=prefix + "fl")
        v["eta_rated"] = st.slider("Compressor peak isentropic efficiency", 0.60, 0.90, float(d["eta_rated"]), 0.01,
                                   key=prefix + "eta")
        st.caption(f"Default {ETA_PEAK:.2f} is calibrated to ASHRAE 90.1 chiller ratings.")
    with c[2].popover("Heat rejection", width="stretch"):
        v["rejection"] = st.radio("Equipment", ["tower", "dry"], ["tower", "dry"].index(d["rejection"]),
                                  format_func=lambda k: "Cooling tower (uses water)" if k == "tower" else "Dry cooler (no water)",
                                  key=prefix + "rej", disabled="rejection" in locks)
        v["free_cooling"] = st.toggle("Free cooling", bool(d["free_cooling"]), key=prefix + "fc")
        st.caption("Free cooling lets cold tower water pre-cool the return water, with no compressor.")
    with c[3].popover("Storage tank", width="stretch"):
        v["tank"] = st.toggle("Chilled-water storage tank", bool(d["tank"]), key=prefix + "tk", disabled="tank" in locks)
        off = not v["tank"]
        v["tank_MWh"] = st.slider("Capacity [MWh of cooling]", 5.0, 60.0, float(d["tank_MWh"]), 5.0, key=prefix + "tkc",
                                  disabled=off or "tank_MWh" in locks)
        v["tank_rate_MW"] = st.slider("Largest charge or discharge [MW]", 1.0, 8.0, float(d["tank_rate_MW"]), 0.5,
                                      key=prefix + "tkr", disabled=off or "tank_rate_MW" in locks)
        v["price_charge"] = st.slider("Charge when the price is at or below [$/MWh]", 10.0, 120.0, float(d["price_charge"]), 5.0,
                                      key=prefix + "pc", disabled=off)
        v["price_discharge"] = st.slider("Discharge when the price is at or above [$/MWh]", 20.0, 300.0,
                                         float(d["price_discharge"]), 5.0, key=prefix + "pd", disabled=off)
    v.update(locks)
    return v


def scorecard(m, s):
    c = st.columns(6)
    c[0].metric("Daily PUE", f"{m['pue']:.3f}")
    c[1].metric("Cooling bill", f"${m['cost_cooling']:,.0f}")
    c[2].metric("Margin to limit", f"{m['margin_T']:.1f} K",
                delta=None if m["minutes_over_limit"] == 0 else f"{m['minutes_over_limit']:.0f} min over limit",
                delta_color="inverse")
    c[3].metric("Compute lost", f"{m['compute_lost_pct']:.2f} %")
    c[4].metric("Make-up water", f"{m['water_m3']:,.0f} m³")
    cop = m["cop_mean"]
    c[5].metric("Chiller COP", "off all day" if cop != cop else f"{cop:.1f}")


def what_happened(day, prev=None):
    """Plain-language account of the run, built from the numbers."""
    m, x, s = day.metrics, day.series, day.settings
    out = []
    if m["minutes_over_limit"] > 0:
        k = int(np.argmax(x["shortfall"]))
        out.append(f"<b>Cooling fell short.</b> At {int(x['hour'][k]):02d}:{int(x['hour'][k] % 1 * 60):02d} the plant was "
                   f"{x['shortfall'][k] / 1e6:.1f} MW short, the hall reached {m['T_inlet_max']:.1f} °C and the GPUs gave up "
                   f"{m['compute_lost_pct']:.1f} % of the day's compute.")
    else:
        out.append(f"<b>The servers stayed safe</b>, with {m['margin_T']:.1f} K to spare at the worst moment.")
    if m["cop_mean"] == m["cop_mean"]:
        lift = float(np.nanmean(np.where(x["n_on"] > 0, x["T_cond"] - x["T_evap"], np.nan)))
        out.append(f"The chillers lifted heat across {lift:.0f} K on average and reached an electrical COP of "
                   f"{m['cop_mean']:.1f}, about {100 * m['eff2_mean']:.0f} % of the Carnot limit for the cycle.")
    else:
        out.append("The chillers never ran: the outdoor air carried the whole load through the free-cooling exchanger.")
    if m["free_cooling_hours"] > 0.2 and m["cop_mean"] == m["cop_mean"]:
        out.append(f"Free cooling helped for the equivalent of {m['free_cooling_hours']:.1f} full hours.")
    share = 100 * m["E_comp_MWh"] / max(m["E_cool_MWh"], 1e-9)
    out.append(f"Cooling used {m['E_cool_MWh']:.1f} MWh, {share:.0f} % of it in the compressors; "
               f"the tower took {m['water_m3']:,.0f} m³ of water." if s.rejection == "tower" else
               f"Cooling used {m['E_cool_MWh']:.1f} MWh, {share:.0f} % of it in the compressors, and no water.")
    if prev is not None and abs(prev["pue"] - m["pue"]) > 5e-4:
        d = m["pue"] - prev["pue"]
        why = ""
        if prev["cop_mean"] == prev["cop_mean"] and m["cop_mean"] == m["cop_mean"]:
            why = f" The chiller COP went from {prev['cop_mean']:.1f} to {m['cop_mean']:.1f}."
        out.append(f"<b>Compared with your last run</b>, the PUE {'rose' if d > 0 else 'fell'} by {abs(d):.3f}.{why}")
    return " ".join(out)


def day_dashboard(day, key, anim=None, start="hot"):
    st.iframe(plant_html(day, start=start), height=PLANT_H)
    st.caption("Click any equipment in the drawing to see inside it. Drag the slider to move through the day.")
    H("The day in numbers")
    scorecard(day.metrics, day.settings)
    a, b = st.columns(2)
    a.plotly_chart(charts.temperature_chart(day), width="stretch", key=key + "t")
    b.plotly_chart(charts.sources_chart(day), width="stretch", key=key + "s")
    a, b = st.columns(2)
    a.plotly_chart(charts.power_chart(day), width="stretch", key=key + "p")
    b.plotly_chart(charts.money_chart(day), width="stretch", key=key + "m")
    if anim:
        H("The refrigeration cycle through the day")
        a, b = st.columns(2)
        for colm, kind in ((a, "ph"), (b, "ts")):
            fig = cycle_anim(*anim, kind)
            if fig is None:
                colm.info("The chillers did not run on this day.")
            else:
                colm.plotly_chart(fig, width="stretch", key=key + kind)


# ================================================================ page
st.session_state.setdefault("view", "Home")
st.session_state.setdefault("grades", {})
st.markdown(header("Run the cooling plant of an AI data center"), unsafe_allow_html=True)
view = st.segmented_control("View", VIEWS, key="view", label_visibility="collapsed") or "Home"

# ---------------------------------------------------------------- HOME
if view == "Home":
    L, R = st.columns([1, 1.15], gap="large")
    with L:
        st.markdown('<div class="cf-hero">Run the cooling plant<br>of an AI data center.</div>', unsafe_allow_html=True)
        st.markdown('<div class="cf-lede">Eight megawatts of GPUs turn electricity into heat. Your job is to get that '
                    'heat outdoors for a day, using as little power and water as you can, without letting the servers '
                    'overheat. Every number comes from a real refrigeration-cycle model.</div>', unsafe_allow_html=True)
        st.write("")
        b = st.columns(3)
        b[0].button("Start first shift", type="primary", width="stretch", on_click=go, args=("Work orders",),
                    kwargs=dict(wo_key="first_shift"))
        b[1].button("Open the console", width="stretch", on_click=go, args=("Console",))
        b[2].button("Compare two plans", width="stretch", on_click=go, args=("Compare",))
        H("What the model found")
        air = run_day(freeze({}), "phoenix", "inference").metrics
        liq = run_day(freeze(PRESETS["Liquid-cooled GPU hall"]), "phoenix", "inference").metrics
        fact = lambda big, small: (f'<div class="cf-card" style="padding:12px 14px"><div class="cf-num" style="font-size:21px">{big}</div>'
                                   f'<div style="color:#8A929C;font-size:12.5px;margin-top:4px">{small}</div></div>')
        m = st.columns(3)
        m[0].markdown(fact(f"PUE {air['pue']:.2f} → {liq['pue']:.2f}", "Phoenix, 43 °C day, with warm-water liquid cooling"), unsafe_allow_html=True)
        m[1].markdown(fact(f"{air['E_comp_MWh']:.0f} → {liq['E_comp_MWh']:.0f} MWh", "compressor energy per day: the chillers switch off"), unsafe_allow_html=True)
        m[2].markdown(fact(f"{P_iplv():.2f} kW/ton", "chiller part-load rating, inside the 0.38 code limit"), unsafe_allow_html=True)
        H("How it works")
        card("<b>1. Pick a shift.</b> Six work orders, from a quiet first day to a chiller failure at 1:30 a.m. "
             "All are open.<br><b>2. Set the plant.</b> Water temperature, chillers, tower or dry cooler, storage.<br>"
             "<b>3. Run the day.</b> It pauses when something happens so you can react.<br>"
             "<b>4. Read the grade.</b> It comes from engineering margins: degrees, percent, kilowatt-hours.<br>"
             "<b>Curious?</b> Click any equipment for its equations and live numbers, or open <b>Proof</b> to see how "
             "the model was checked.")
    with R:
        st.iframe(plant_html(run_day(freeze({}), "la_hot", "inference"), autoplay=True, start="zero", compact=True), height=440)
        st.caption("A hot day in Los Angeles, as built: four chillers, a cooling tower, air-cooled racks.")

# ---------------------------------------------------------------- WORK ORDERS
elif view == "Work orders":
    key = st.session_state.get("wo_key")
    if key not in WORK_ORDERS:
        st.markdown("### Work orders")
        st.caption("Each is one shift at a client's site. All are open; the order below is the recommended one.")
        for i in range(0, len(ORDERS), 3):
            cols = st.columns(3)
            for colm, o in zip(cols, ORDERS[i:i + 3]):
                with colm:
                    g = st.session_state["grades"].get(o.key)
                    card(f'<span class="cf-mono">WORK ORDER {o.number} · {o.client}</span><br>'
                         f'<span style="font-size:19px;font-weight:600">{o.title}</span>'
                         f'{"<span class=cf-badge>grade " + g + "</span>" if g else ""}<br>'
                         f'<span style="color:#B4BAC2">{o.brief}</span><br>'
                         f'<span class="cf-mono">You will use: {o.teaches}</span>')
                    st.button("Open", key="open" + o.key, width="stretch", on_click=go, args=("Work orders",),
                              kwargs=dict(wo_key=o.key))
    else:
        o = WORK_ORDERS[key]
        sk = "wo_plans_" + key
        plans = st.session_state.setdefault(sk, [])
        top = st.columns([5, 1])
        top[0].markdown(f'<span class="cf-mono">WORK ORDER {o.number} · {o.client} · {CLIMATES[o.climate].label} · '
                        f'{WORKLOADS[o.workload].label}</span>', unsafe_allow_html=True)
        top[0].markdown(f"### {o.title}")
        top[1].button("All work orders", width="stretch", on_click=go, args=("Work orders",), kwargs=dict(wo_key=None))
        pauses = o.pauses
        stage = len(plans)
        finished = stage > len(pauses)
        until = 24.0 if finished or stage == 0 else pauses[stage - 1]

        def targets_table(rows=None):
            h = "<table class='cf-t'><tr><th>Target</th><th>Limit</th>" + ("<th>Achieved</th><th>Margin</th><th></th>" if rows else "<th>For grade A</th>") + "</tr>"
            for i, t in enumerate(o.targets):
                f = f"{{:,.{t.nd}f}}"
                lim = f"≤ {f.format(t.limit)} {t.unit}"
                if rows:
                    r = rows[i]
                    colr = "#8FB39A" if r["met"] else "#E06A50"
                    h += (f"<tr><td>{t.label}</td><td class='n'>{lim}</td><td class='n'>{f.format(r['achieved'])} {t.unit}</td>"
                          f"<td class='n' style='color:{colr}'>{'+' if r['margin'] >= 0 else '−'}{f.format(abs(r['margin']))} {t.unit}</td>"
                          f"<td style='color:{colr}'>{'inside' if r['met'] else 'outside'}</td></tr>")
                else:
                    a = f"≤ {f.format(t.a_level)} {t.unit}" if t.a_level is not None else "meet the limit"
                    h += f"<tr><td>{t.label}</td><td class='n'>{lim}</td><td class='n'>{a}</td></tr>"
            return h + "</table>"

        def guide(step):
            if o.guide and step < len(o.guide):
                card(f'<div class="n">GUIDE · STEP {step + 1} OF {len(o.guide)}</div>{o.guide[step]}', "cf-guide")

        if stage == 0:                                   # ---- briefing
            a, b = st.columns([1.2, 1])
            with a:
                card(f"<b>The job.</b> {o.brief}<br><br><b>Grading.</b> A: every target met and the efficiency target "
                     f"beaten. B: every target met. C: servers safe, efficiency missed. D: a safety limit broken.")
                if o.events:
                    card("<b>Expect:</b> the shift pauses when something happens, so you can change the plant and resume.", "cf-note")
            with b:
                card(targets_table())
            guide(0)
            H("Set the plant for the start of the shift")
            v = settings_toolbar(f"wo{key}0", o.locks, o.start)
            if o.locks:
                st.caption("Fixed by this work order: " + ", ".join(k.replace("_", " ") for k in o.locks if k != "tank_soc0") + ".")
            st.button("Start shift", type="primary", on_click=lambda: plans.append(v))
            with st.expander("Hint"):
                st.write(o.hint)
        else:
            day = run_wo(key, tuple(freeze(p) for p in plans), until)
            if not finished:                             # ---- paused at an event
                ev = [e for e in o.events if e.pause][stage - 1]
                card(f'<span class="cf-mono">PAUSED AT {int(ev.t):02d}:{int(ev.t % 1 * 60):02d}</span><br>'
                     f'<span style="font-size:18px;font-weight:600">{ev.title}</span><br>{ev.text}',
                     "cf-alert" if ev.kind == "trip" else "cf-note")
                H("Change the plant, then resume")
                v = settings_toolbar(f"wo{key}{stage}", o.locks, plans[-1])
                c = st.columns([1, 1, 4])
                c[0].button("Resume shift", type="primary", width="stretch", on_click=lambda: plans.append(v))
                c[1].button("Restart", width="stretch", on_click=lambda: plans.clear())
                st.iframe(plant_html(day, start="end", focus="hall" if ev.kind in ("trip", "load") else "tower"), height=PLANT_H)
            else:                                        # ---- debrief
                grade, rows = evaluate(o, day.metrics)
                best = st.session_state["grades"].get(key)
                if best is None or grade < best:
                    st.session_state["grades"][key] = grade
                a, b = st.columns([1, 2.4])
                colr = {"A": "#8FB39A", "B": "#8FB39A", "C": "#D9A441", "D": "#E06A50"}[grade]
                with a:
                    card(f'<span class="cf-mono">SHIFT COMPLETE · GRADE</span><br><span class="cf-grade" style="color:{colr}">{grade}</span><br>'
                         + {"A": "Every target met, with margin.", "B": "Every target met.",
                            "C": "Servers safe. Efficiency target missed.", "D": "A safety limit was broken."}[grade])
                with b:
                    card(targets_table(rows))
                if o.guide:
                    guide(1 if grade in "CD" else 3)
                    if grade in "CD":
                        guide(2)
                card("<b>What happened.</b> " + what_happened(day, st.session_state.get("wo_prev_" + key)))
                if grade in "AB":
                    card("<b>Why it worked.</b> " + o.lesson, "cf-note")
                else:
                    with st.expander("Hint"):
                        st.write(o.hint)
                c = st.columns([1, 1, 4])

                def again():
                    st.session_state["wo_prev_" + key] = day.metrics
                    plans.clear()
                c[0].button("Try again", type="primary" if grade in "CD" else "secondary", width="stretch", on_click=again)
                nxt = ORDERS[(ORDERS.index(o) + 1) % len(ORDERS)]
                c[1].button(f"Next: {nxt.title}", width="stretch", on_click=go, args=("Work orders",), kwargs=dict(wo_key=nxt.key))
                day_dashboard(day, "wo" + key)

# ---------------------------------------------------------------- CONSOLE (free play)
elif view == "Console":
    st.markdown("### Console")
    st.caption("Free play. Any site, any workload, any plant. Nothing is locked and nothing is graded.")
    c = st.columns([1.3, 1.3, 1.3, 1.6])
    climate = c[0].selectbox("Site and weather", list(CLIMATES), format_func=lambda k: CLIMATES[k].label)
    workload = c[1].selectbox("Workload", list(WORKLOADS), format_func=lambda k: WORKLOADS[k].label)
    tariff = c[2].selectbox("Electricity price", list(TARIFFS), format_func=lambda k: TARIFFS[k].label)
    preset = c[3].selectbox("Start from", list(PRESETS))
    v = settings_toolbar("con" + preset, defaults=PRESETS[preset])
    day = run_day(freeze(v), climate, workload, tariff)
    st.session_state["last_day"] = day
    prev = st.session_state.get("con_prev")
    card("<b>What happened.</b> " + what_happened(day, prev if prev is not day.metrics else None))
    st.session_state["con_prev"] = day.metrics
    for w in ([f"Servers above the limit for {day.metrics['minutes_over_limit']:.0f} minutes."] if day.metrics["minutes_over_limit"] > 0 else []):
        card(w, "cf-alert")
    day_dashboard(day, "con", anim=(freeze(v), climate, workload, tariff))

# ---------------------------------------------------------------- CHILLER LAB
elif view == "Chiller lab":
    st.markdown("### Chiller lab")
    st.caption("One vapor-compression refrigeration cycle, with nothing else around it. Set the two temperatures, the "
               "refrigerant and the compressor efficiency yourself.")
    last = st.session_state.get("last_day")
    left, right = st.columns([1, 2.2])
    with left:
        fl = st.selectbox("Refrigerant", list(REFRIGERANTS), format_func=lambda k: f"{REFRIGERANTS[k]} · {GWP[k]}")
        T_e = st.slider("Evaporating temperature [°C]", -10.0, 18.0, 8.0, 0.5)
        T_c = st.slider("Condensing temperature [°C]", 20.0, 60.0, 35.0, 0.5)
        eta = st.slider("Compressor isentropic efficiency", 0.50, 1.00, 0.80, 0.01)
        how = st.radio("Size the chiller by", ["Cooling capacity", "Refrigerant mass flow"], horizontal=True)
        if how == "Cooling capacity":
            Q_kW = st.slider("Cooling capacity [kW]", 100.0, 4000.0, 3000.0, 50.0)
        sh = st.slider("Superheat [K]", 0.0, 10.0, 5.0, 0.5)
        sc = st.slider("Subcooling [K]", 0.0, 10.0, 3.0, 0.5)
    if T_c <= T_e + 5:
        st.error("The condensing temperature must be at least 5 K above the evaporating temperature.")
        st.stop()
    cyc = solve_cycle(fl, T_e + C2K, T_c + C2K, eta, sh, sc)
    with left:
        if how == "Refrigerant mass flow":
            m_ref = st.slider("Refrigerant mass flow [kg/s]", 0.5, 40.0, 10.0, 0.5)
            Q_kW = m_ref * cyc.q_evap / 1e3
        m_ref = Q_kW * 1e3 / cyc.q_evap
    W_kW = m_ref * cyc.w_comp / 1e3
    with right:
        st.iframe(cycle_html(cyc, m_ref, Q_kW, W_kW), height=470)
        g = st.columns(5)
        g[0].metric("COP", f"{cyc.cop:.2f}")
        g[1].metric("Carnot COP", f"{cyc.cop_carnot:.2f}")
        g[2].metric("Second-law efficiency", f"{100 * cyc.second_law_eff:.0f} %")
        g[3].metric("Cooling capacity", f"{Q_kW:,.0f} kW")
        g[4].metric("Compressor power", f"{W_kW:,.0f} kW")
    a, b = st.columns(2)
    a.plotly_chart(charts.ph_diagram(cyc), width="stretch")
    b.plotly_chart(charts.ts_diagram(cyc), width="stretch")
    H("State points")
    names = ["1 compressor inlet", "2 compressor outlet", "3 condenser outlet", "4 evaporator inlet"]
    Pk = [cyc.P_evap, cyc.P_cond, cyc.P_cond, cyc.P_evap]
    st.dataframe(pd.DataFrame({"state": names, "T [°C]": [t - C2K for t in cyc.T], "P [kPa]": [p / 1e3 for p in Pk],
                               "h [kJ/kg]": [h / 1e3 for h in cyc.h], "s [kJ/kg·K]": [s / 1e3 for s in cyc.s]})
                 .style.format(precision=2), hide_index=True, width="stretch")
    sg = checks.entropy_generation(cyc, m_ref, T_e + C2K + 4, T_c + C2K - 4)
    H("Energy and entropy, device by device (each is a steady-flow device)")
    st.dataframe(pd.DataFrame({
        "device": ["evaporator", "compressor", "condenser", "expansion valve"],
        "heat in [kW]": [Q_kW, 0.0, -(Q_kW + W_kW), 0.0],
        "work in [kW]": [0.0, W_kW, 0.0, 0.0],
        "entropy generated [kW/K]": [sg["evaporator"] / 1e3, sg["compressor"] / 1e3, sg["condenser"] / 1e3, sg["valve"] / 1e3],
    }).style.format(precision=3), hide_index=True, width="stretch")
    st.caption("Entropy here assumes water 4 K warmer than the refrigerant in the evaporator and 4 K colder in the condenser.")
    H("Cycle challenges")
    ch = [("Deliver 3,000 kW of cooling with a COP of 7.0 or more", Q_kW >= 2999 and cyc.cop >= 7.0, f"COP {cyc.cop:.2f}"),
          ("Deliver 3,000 kW with 350 kW of compressor power or less", Q_kW >= 2999 and W_kW <= 350, f"{W_kW:,.0f} kW"),
          ("Reach 70 % of the Carnot COP with a low-GWP refrigerant and a compressor efficiency of 0.85 or less",
           fl != "R134a" and cyc.second_law_eff >= 0.70 and eta <= 0.85, f"{100 * cyc.second_law_eff:.0f} % of Carnot")]
    for text, ok, now in ch:
        card(f'{text}<span class="cf-badge" style="color:{"#8FB39A" if ok else "#8A929C"}">{"met" if ok else "not yet"} · {now}</span>')

# ---------------------------------------------------------------- COMPARE
elif view == "Compare":
    st.markdown("### Compare two plans")
    st.caption("Two plants on the same day. The table shows what changed and by how much.")
    c = st.columns(3)
    climate = c[0].selectbox("Site and weather", list(CLIMATES), format_func=lambda k: CLIMATES[k].label, key="abc")
    workload = c[1].selectbox("Workload", list(WORKLOADS), format_func=lambda k: WORKLOADS[k].label, key="abw")
    tariff = c[2].selectbox("Electricity price", list(TARIFFS), format_func=lambda k: TARIFFS[k].label, key="abt")
    H("Plan A")
    va = settings_toolbar("A")
    H("Plan B")
    vb = settings_toolbar("B", defaults=PRESETS["Warm water"])
    A, B = run_day(freeze(va), climate, workload, tariff), run_day(freeze(vb), climate, workload, tariff)
    mean_on = lambda d, k, sc=1.0: float(np.nanmean(np.where(d.series["n_on"] > 0, d.series[k], np.nan)) * sc) if (d.series["n_on"] > 0).any() else float("nan")
    rows = [("Daily PUE", "pue", 3, ""), ("Chiller electrical COP", "cop_mean", 2, ""), ("Second-law efficiency of the cycle [%]", "eff2_mean", 1, "x100"),
            ("Cooling electricity [MWh]", "E_cool_MWh", 1, ""), ("Compressor electricity [MWh]", "E_comp_MWh", 1, ""),
            ("Heat rejected outdoors [MWh]", "E_rej_MWh", 1, ""), ("Cooling bill [$]", "cost_cooling", 0, ""),
            ("Peak at the racks [°C]", "T_inlet_max", 1, ""), ("Smallest margin to the limit [K]", "margin_T", 1, ""),
            ("Compute lost [%]", "compute_lost_pct", 2, ""), ("Make-up water [m³]", "water_m3", 0, ""),
            ("Free cooling [h]", "free_cooling_hours", 1, ""), ("Energy balance error [%]", "energy_balance_err_pct", 5, "")]
    tab = []
    for label, k, nd, sc in rows:
        a_, b_ = (A.metrics[k], B.metrics[k]) if not sc else (100 * A.metrics[k], 100 * B.metrics[k])
        tab.append((label, a_, b_, nd))
    for label, k, sc, nd in (("Evaporating pressure, mean [kPa]", "P_evap", 1e-3, 0), ("Condensing pressure, mean [kPa]", "P_cond", 1e-3, 0),
                             ("Evaporating temperature, mean [°C]", "T_evap", 1.0, 1), ("Condensing temperature, mean [°C]", "T_cond", 1.0, 1),
                             ("Refrigerant mass flow, mean [kg/s]", "m_ref", 1.0, 1), ("Chilled-water flow, mean [kg/s]", "m_chw", 1.0, 0)):
        tab.append((label, mean_on(A, k, sc), mean_on(B, k, sc), nd))
    fm = lambda v, nd: "off" if v != v else f"{v:,.{nd}f}"
    h = "<table class='cf-t'><tr><th>Quantity</th><th>Plan A</th><th>Plan B</th><th>B − A</th></tr>"
    for label, a_, b_, nd in tab:
        d = "" if (a_ != a_ or b_ != b_) else f"{b_ - a_:+,.{nd}f}"
        h += f"<tr><td>{label}</td><td class='n'>{fm(a_, nd)}</td><td class='n'>{fm(b_, nd)}</td><td class='n'>{d}</td></tr>"
    card(h + "</table>")
    a, b = st.columns(2)
    a.plotly_chart(charts.ab_chart(A, B, "T_inlet", "At the racks [°C]"), width="stretch")
    b.plotly_chart(charts.ab_chart(A, B, "cop", "Chiller electrical COP"), width="stretch")
    a, b = st.columns(2)
    a.plotly_chart(charts.ab_chart(A, B, "P_cool", "Cooling electricity [MW]", 1e-6), width="stretch")
    b.plotly_chart(charts.ab_chart(A, B, "pue", "PUE"), width="stretch")

# ---------------------------------------------------------------- PROOF
else:
    st.markdown("### Proof")
    st.caption("Why the numbers can be trusted. Every check on this page is recomputed by the model, and the same "
               "checks run as 21 automated tests.")
    P = proof_data()
    H("1 · The cycle against a textbook")
    st.write("Çengel and Boles, Example 11-1: ideal R-134a cycle, 0.14 to 0.8 MPa, 0.05 kg/s.")
    st.dataframe(pd.DataFrame(P["tb"]).rename(columns={"error_pct": "difference [%]"}).style.format(precision=3),
                 hide_index=True, width="stretch")
    with st.expander("One cycle by hand, the way it is done from property tables"):
        w = P["we"]
        st.markdown(f"""R-134a, {w['T_evap_C']:.0f} °C evaporating, {w['T_cond_C']:.0f} °C condensing, η = {w['eta']:.2f}.
- State 1: h₁ = {w['h1']:.2f} kJ/kg, s₁ = {w['s1']:.4f} kJ/(kg·K)
- Isentropic outlet: h₂ₛ = {w['h2s']:.2f} kJ/kg; actual h₂ = h₁ + (h₂ₛ − h₁)/η = {w['h2']:.2f} kJ/kg
- State 3 and valve: h₃ = h₄ = {w['h3']:.2f} kJ/kg
- q_L = {w['q_evap']:.2f}, w = {w['w_comp']:.2f}, q_H = {w['q_cond']:.2f} kJ/kg
- COP = {w['cop']:.2f}; Carnot COP = {w['cop_carnot']:.2f}""")
    H("2 · The chiller against the industry standards")
    st.write("The compressor map was calibrated on seven rating points. These checks use data it was not fitted to. "
             "kW/ton is electricity per ton of cooling; lower is better.")
    mv = pd.DataFrame(P["mv"]["rows"])[["check", "source", "ref", "model", "ok"]]
    mv.columns = ["check", "reference", "reference value", "model", "passes"]
    st.dataframe(mv.style.format(precision=3), hide_index=True, width="stretch")
    card("<b>One check does not pass, and it is left visible.</b> The model gains more from warmer chilled water than "
         "the 1 to 2 % per °F rule of thumb. Savings from raising the water temperature should be read as an upper bound.", "cf-note")
    H("3 · First and second laws")
    law, ex = P["law"], P["ex"]
    c = st.columns(4)
    c[0].metric("Operating points tested", law["cases"])
    c[1].metric("Worst first-law error", f"{law['worst_first_law_err']:.0e}")
    c[2].metric("Second-law violations", len(law["violations"]))
    c[3].metric("Lost-work closure", f"{ex['closure']:.0e}")
    st.write("Where the compressor work goes at a typical operating point (W = W_reversible + T₀ ΣS_gen):")
    lw = {"reversible minimum": ex["W_rev"], **ex["lost_work"]}
    st.dataframe(pd.DataFrame({"": list(lw), "kW per MW of cooling": [v / 1e3 for v in lw.values()],
                               "share of work [%]": [100 * v / ex["W"] for v in lw.values()]}).style.format(precision=1),
                 hide_index=True, width="stretch")
    H("4 · Conservation in the plant, recomputed from flows and temperatures")
    au = pd.DataFrame(P["audit"])[["balance", "kind", "lhs", "rhs", "unit", "rel_err"]]
    au.columns = ["balance", "kind", "left side", "right side", "unit", "relative error"]
    st.dataframe(au.style.format({"left side": "{:,.4g}", "right side": "{:,.4g}", "relative error": "{:.1e}"}), hide_index=True, width="stretch")
    H("5 · Whole-day energy and mass balances")
    eb = pd.DataFrame(P["eb"]); eb.columns = ["day", "energy balance error [%]", "tower water balance error [%]", "PUE", "chiller COP"]
    st.dataframe(eb.style.format({"energy balance error [%]": "{:.1e}", "tower water balance error [%]": "{:.1e}", "PUE": "{:.3f}", "chiller COP": "{:.1f}"}, na_rep="off"),
                 hide_index=True, width="stretch")
    c = st.columns(3)
    c[0].metric("Storage tank mass balance error", f"{P['tank']['tank_mass_err_pct']:.1e} %")
    c[1].metric("Energy balance, correct ledger", f"{P['neg']['correct_err_pct']:.1e} %")
    c[2].metric("Same balance with pump heat left out", f"{P['neg']['without_pump_heat_err_pct']:.1f} %", "the check can fail", delta_color="off")
    H("6 · Time step")
    ts = pd.DataFrame(P["ts"])[["dt", "T_inlet_max", "compute_lost_MWh", "err"]]
    ts.columns = ["time step [s]", "peak inlet [°C]", "compute lost [MWh]", "error vs finest step [MWh]"]
    st.dataframe(ts.style.format({"peak inlet [°C]": "{:.3f}", "compute lost [MWh]": "{:.4f}", "error vs finest step [MWh]": "{:.1e}"}), hide_index=True, width="stretch")
    st.caption("The app uses 30 s. Forward Euler; at 120 s the step is too coarse for the 5-minute control loop.")
    H("7 · How each device is modeled")
    st.dataframe(pd.DataFrame([dict(device=k, treatment="steady-state steady-flow" if v[0] == "SSSF" else "transient control volume",
                                    balance=v[1]) for k, v in DEVICES.items()]), hide_index=True, width="stretch")
