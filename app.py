"""
COLDFRONT - run the cooling plant of an AI data center.
Interactive thermodynamics laboratory for AME 310 (Part D, refrigeration cycle).

This file is the interface only: page layout, controls and the game flow.
All thermodynamics lives in the coldfront/ package.      Run:  streamlit run app.py
"""
import os
import re

from dataclasses import replace
import numpy as np
import pandas as pd
import streamlit as st

from coldfront.plant import PlantSettings, DEVICES, C2K
from coldfront.day import simulate_day
from coldfront.chiller import solve_cycle, REFRIGERANTS, ETA_PEAK
from coldfront.scenarios import CLIMATES, WORKLOADS, TARIFFS
from coldfront.contracts import ORDERS, WORK_ORDERS, SETS, get_order, run_order, evaluate
from coldfront import checks
from ui import charts
from ui.theme import CSS, header
from ui.plant_view import plant_html
from ui.cycle_view import cycle_html
from ui import tour as T

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
PLANT_H = 930

# Small line drawings for the work-order cards (decoration only)
_L = 'fill="none" stroke="#5E6670" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'
ART = {
    "first_shift": f'<path {_L} d="M8 78 H132"/><path fill="none" stroke="#D9A441" stroke-width="1.8" stroke-linecap="round" d="M44 78 a26 26 0 0 1 52 0 M70 38 V28 M40 50 l-7 -7 M100 50 l7 -7 M30 78 h-9 M119 78 h-9"/>'
                   f'<path {_L} d="M100 78 V60 h22 v18 M106 66 h10 M106 72 h10"/>',
    "heatwave": f'<circle cx="52" cy="42" r="19" fill="none" stroke="#D97B3F" stroke-width="1.8"/><path fill="none" stroke="#D97B3F" stroke-width="1.8" stroke-linecap="round" d="M52 12 v-7 M52 79 v-7 M22 42 h-7 M89 42 h-7 M31 21 l-5 -5 M73 21 l5 -5 M31 63 l-5 5 M73 63 l5 5"/>'
                f'<path {_L} d="M108 18 a6 6 0 0 1 12 0 V56 a11 11 0 1 1 -12 0 Z M114 64 V34"/>',
    "chiller_down": f'<path fill="none" stroke="#D9A441" stroke-width="1.8" stroke-linecap="round" d="M40 16 a20 20 0 1 0 18 28 a16 16 0 0 1 -18 -28 Z"/>'
                    f'<rect x="78" y="26" width="44" height="52" rx="3" fill="none" stroke="#E06A50" stroke-width="1.6" stroke-dasharray="5 4"/><path fill="none" stroke="#E06A50" stroke-width="1.8" stroke-linecap="round" d="M90 42 l20 20 M110 42 l-20 20"/>',
    "price_spike": f'<path {_L} d="M14 10 V78 H130"/><path fill="none" stroke="#D9A441" stroke-width="2" stroke-linejoin="round" d="M14 62 H40 V54 H76 V18 H104 V56 H130"/>',
    "not_a_drop": f'<path fill="none" stroke="#6FA8DC" stroke-width="1.8" stroke-linejoin="round" d="M70 10 C56 32 46 44 46 56 a24 24 0 0 0 48 0 C94 44 84 32 70 10 Z"/><path fill="none" stroke="#D97B3F" stroke-width="2.2" stroke-linecap="round" d="M34 78 L106 16"/>',
    "blackwell": f'<rect x="42" y="8" width="56" height="74" rx="3" {_L}/><path {_L} d="M50 22 h40 M50 36 h40 M50 50 h40 M50 64 h40"/>'
                 f'<path fill="none" stroke="#6FA8DC" stroke-width="1.8" stroke-linecap="round" d="M14 30 H42 M14 58 H42 M98 30 H126 M98 58 H126"/>',
}
BLURB = dict(
    first_shift="A normal day. The servers are safe, but the plant is wasting power. Bring the PUE down.",
    heatwave="A desert heatwave and a city water permit that covers only part of the day. Lose no compute.",
    chiller_down="A chiller trips half an hour before a 4.5 MW training run. Get through the night.",
    price_spike="Evening prices are about to triple. You have an empty storage tank and a cooling bill to hold.",
    not_a_drop="A 43 °C day with a water permit of zero. Dry coolers only. Hold the PUE anyway.",
    blackwell="Liquid-cooled GPU racks, and two chillers about to fail at the hottest hour.")
_T = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests", "test_physics.py")).read()
N_TESTS = _T.count("def test_") + sum(m.count(",") for m in re.findall(r"parametrize\([^\[]*\[([^\]]*)\]", _T))
LOCK_NAMES = dict(rejection="heat rejection", rack_cooling="rack cooling", tank="tank installed", tank_MWh="tank size",
                  tank_rate_MW="tank rate", T_chws_C="water temperature", dT_chw="water temperature rise")
VERDICT = {"A": "Excellent shift. Every target met, with room to spare.", "B": "Solid shift. Every target met.",
           "C": "Safe, but wasteful. The efficiency target was missed.", "D": "A safety limit was crossed. Try another setup."}


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
def run_wo(key, var, plans_items, until):
    return run_order(get_order(key, var), [PlantSettings(**dict(p)) for p in plans_items], until)


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
def settings_toolbar(prefix, locks=None, defaults=None, limits=None):
    """Four drop-down panels, one per part of the plant. Locked settings (set
    by a work order) are shown but cannot be changed."""
    locks = locks or {}
    limits = limits or {}
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
        lo, hi = limits.get("T_chws_C", (6.0, 20.0 if v["rack_cooling"] == "air" else 40.0))
        if "T_chws_C" in locks:
            st.markdown(f'<div class="cf-mono">Water supply temperature: fixed at {locks["T_chws_C"]:g} °C</div>', unsafe_allow_html=True)
        else:
            v["T_chws_C"] = st.slider("Water supply temperature [°C]", lo, hi, max(lo, min(float(d["T_chws_C"]), hi)), 0.5,
                                      key=prefix + "chws" + v["rack_cooling"], format="%.1f")
            if "T_chws_C" in limits:
                st.caption(f"This client allows {lo:g} to {hi:g} °C.")
        v["dT_chw"] = st.slider("How much the water warms up in the hall [°C]", 4.0, 12.0, float(d["dT_chw"]), 0.5,
                                key=prefix + "dt", format="%.1f", disabled="dT_chw" in locks)
        st.caption("Warmer water is easier for the chillers to make, so they use less electricity. "
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
    base = PlantSettings().__dict__
    base.update(defaults or {})
    base.update(locks)
    def item(text, keys):
        changed = any(v.get(k) != base.get(k) for k in keys)
        return f'<span style="color:{"#6FA8DC" if changed else "#B4BAC2"}">{text}{" (changed)" if changed else ""}</span>'
    parts = [item(f"water {v['T_chws_C']:g} °C, rise {v['dT_chw']:g} °C", ("T_chws_C", "dT_chw")),
             item(f"{v['n_chillers']} chillers, {v['fluid'].replace('(E)', '')}", ("n_chillers", "fluid", "eta_rated")),
             item(("cooling tower" if v["rejection"] == "tower" else "dry cooler") + (", free cooling on" if v["free_cooling"] else ", free cooling off"), ("rejection", "free_cooling")),
             item(f"tank {v['tank_MWh']:g} MWh" if v["tank"] else "no tank", ("tank", "tank_MWh", "tank_rate_MW", "price_charge", "price_discharge")),
             item("liquid-cooled racks" if v["rack_cooling"] == "liquid" else "air-cooled racks", ("rack_cooling",))]
    st.markdown('<div class="cf-set"><span style="color:#8A929C">Set now:</span> ' + " · ".join(parts) + '</div>'
                '<div class="cf-mono" style="margin:2px 0 8px 0">These four buttons are your controls. Open one, change it, '
                'then click anywhere outside to close it.</div>', unsafe_allow_html=True)
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


def what_happened(day, prev=None, focus="pue"):
    """Plain-language account of the run, built from the numbers."""
    m, x, s = day.metrics, day.series, day.settings
    out = []
    if m["minutes_over_limit"] > 0:
        k = int(np.argmax(x["shortfall"]))
        short_now = float(np.max(x["shortfall"])) / 1e6
        out.append(f"<b>Cooling fell short.</b> At {int(x['hour'][k]):02d}:{int(x['hour'][k] % 1 * 60):02d} the plant was "
                   f"{x['shortfall'][k] / 1e6:.1f} MW short, the hall reached {m['T_inlet_max']:.1f} °C and the GPUs gave up "
                   f"{m['compute_lost_pct']:.1f} % of the day's compute.")
    else:
        out.append(f"<b>The servers stayed safe</b>, with {m['margin_T']:.1f} °C to spare at the worst moment.")
    if m["cop_mean"] == m["cop_mean"]:
        lift = float(np.nanmean(np.where(x["n_on"] > 0, x["T_cond"] - x["T_evap"], np.nan)))
        out.append(f"The chillers lifted heat across a {lift:.0f} °C gap on average and delivered {m['cop_mean']:.1f} units "
                   f"of cooling per unit of electricity (COP), about {100 * m['eff2_mean']:.0f} % of the theoretical best.")
    else:
        out.append("The chillers never ran: the outdoor air carried the whole load through the free-cooling exchanger.")
    if m["free_cooling_hours"] > 0.2 and m["cop_mean"] == m["cop_mean"]:
        out.append(f"Free cooling helped for the equivalent of {m['free_cooling_hours']:.1f} full hours.")
    share = 100 * m["E_comp_MWh"] / max(m["E_cool_MWh"], 1e-9)
    out.append(f"Cooling used {m['E_cool_MWh']:.1f} MWh, {share:.0f} % of it in the compressors; "
               f"the tower took {m['water_m3']:,.0f} m³ of water." if m["water_m3"] > 0.5 else
               f"Cooling used {m['E_cool_MWh']:.1f} MWh, {share:.0f} % of it in the compressors, and no water.")
    if prev is not None:
        cmp = []
        if focus == "cost_cooling" and abs(prev["cost_cooling"] - m["cost_cooling"]) >= 1:
            d = m["cost_cooling"] - prev["cost_cooling"]
            cmp.append(f"the cooling bill {'rose' if d > 0 else 'fell'} by ${abs(d):,.0f} ({'worse' if d > 0 else 'better'}).")
        elif abs(prev["pue"] - m["pue"]) > 5e-4:
            d = m["pue"] - prev["pue"]
            cmp.append(f"the PUE {'rose' if d > 0 else 'fell'} by {abs(d):.3f} ({'worse' if d > 0 else 'better'}).")
            pc, mc = prev["cop_mean"], m["cop_mean"]
            if pc == pc and mc == mc:
                cmp.append(f"The chiller COP went from {pc:.1f} to {mc:.1f}.")
                dfc = m["free_cooling_hours"] - prev["free_cooling_hours"]
                if d < 0 and mc <= pc + 0.05 and dfc > 0.5:
                    cmp.append(f"The COP did not rise because free cooling took over the easy hours "
                               f"({prev['free_cooling_hours']:.1f} to {m['free_cooling_hours']:.1f} h); the chillers now "
                               "run only when the lift is largest.")
        po, mo = prev["minutes_over_limit"], m["minutes_over_limit"]
        if po > 0 or mo > 0:
            ps, ms = prev.get("short_MW", 0.0), float(np.max(x["shortfall"])) / 1e6
            if abs(po - mo) < 15 and abs(ps - ms) < 0.1 and mo > 0:
                cmp.append("The cooling shortfall did not change: that setting adds no capacity when it is needed.")
            else:
                cmp.append(f"Time above the limit went from {po:.0f} to {mo:.0f} min and the worst shortfall from "
                           f"{ps:.1f} to {ms:.1f} MW.")
        if cmp:
            out.insert(0, "<b>Compared with your last run</b>, " + cmp[0][0].lower() + cmp[0][1:] + " " + " ".join(cmp[1:]))
    return " ".join(out)


def day_dashboard(day, key, anim=None, start="hot"):
    st.caption("Press Play day or drag the slider to move through the day. Click any equipment in the drawing "
               "(a chiller, the tower, the data hall) to see inside it.")
    st.iframe(plant_html(day, start=start), height=PLANT_H)
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
_nav = st.columns([6, 1])
with _nav[0]:
    view = st.segmented_control("View", VIEWS, key="view", label_visibility="collapsed") or "Home"
_nav[1].button("Take the tour", width="stretch",
               on_click=lambda: st.session_state.update(tour_force=st.session_state.get("tour_force", 0) + 1))
FORCE = st.session_state.get("tour_force")

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
        m[0].markdown(fact(f"{air['pue']:.2f} → {liq['pue']:.2f}", "PUE in Phoenix on a 43 °C day, with warm-water liquid cooling"), unsafe_allow_html=True)
        m[1].markdown(fact(f"{air['E_comp_MWh']:.0f} → {liq['E_comp_MWh']:.0f} MWh", "chiller electricity per day: with warm water the chillers switch off"), unsafe_allow_html=True)
        lost = run_day(freeze(dict(n_chillers=3)), "la_typical", "training").metrics["compute_lost_pct"]
        m[2].markdown(fact(f"{lost:.1f} % lost", "of a day's computing when one chiller fails during a night training run"), unsafe_allow_html=True)
        st.markdown('<div class="cf-mono">PUE = total power ÷ computer power. 1.00 would be perfect; lower is better.</div>', unsafe_allow_html=True)
        H("How it works")
        card("<b>1. Pick a shift.</b> Six work orders, from a quiet first day to a chiller failure at 1:30 a.m. "
             "Each has three sets of numbers. All are open.<br><b>2. Set the plant.</b> Water temperature, chillers, tower or dry cooler, storage.<br>"
             "<b>3. Run the day.</b> It pauses when something happens so you can react.<br>"
             "<b>4. See how it went.</b> Each attempt earns a grade from A to D. Retry as often as you like; your best one is kept.<br>"
             "<b>Curious?</b> Click any equipment for its equations and live numbers, or open <b>Proof</b> to see how "
             "the model was checked.")
    with R:
        st.iframe(plant_html(run_day(freeze({}), "la_hot", "inference"), autoplay=True, start="zero", compact=True), height=380)
        st.caption("A hot day in Los Angeles, as built: four chillers, a cooling tower, air-cooled racks.")
    T.tour("home", T.HOME, FORCE)

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
                    card(f'<div style="min-height:150px;position:relative">'
                         f'<svg viewBox="0 0 140 90" width="124" style="position:absolute;top:-2px;right:-4px">{ART[o.key]}</svg>'
                         f'<div style="padding-right:128px;min-height:84px"><span class="cf-mono">WORK ORDER {o.number} · {o.client}</span><br>'
                         f'<span style="font-size:19px;font-weight:600">{o.title}</span>'
                         f'{"<br><span class=cf-badge style=margin-left:0>BEST SO FAR · " + g + "</span>" if g else ""}</div>'
                         f'<span style="color:#B4BAC2">{BLURB[o.key]}</span></div>')
                    st.button("Open", key="open" + o.key, width="stretch", on_click=go, args=("Work orders",),
                              kwargs=dict(wo_key=o.key))
    else:
        var = st.session_state.setdefault("wo_var_" + key, 0)
        o = get_order(key, var)
        sk = "wo_plans_" + key
        plans = st.session_state.setdefault(sk, [])

        last = st.session_state.get("wo_last_" + key)        # the plans of the previous attempt
        tries = st.session_state.setdefault("wo_try_" + key, 0)

        def new_numbers():
            st.session_state["wo_var_" + key] = (var + 1) % len(SETS)
            st.session_state.pop("wo_prev_" + key, None)
            st.session_state.pop("wo_last_" + key, None)
            plans.clear()

        def reset_plant():
            st.session_state.pop("wo_last_" + key, None)
            st.session_state["wo_try_" + key] = tries + 1
        top = st.columns([5, 1])
        top[0].markdown(f'<span class="cf-mono">WORK ORDER {o.number} · SET {SETS[var]} · {o.client} · {CLIMATES[o.climate].label} · '
                        f'{WORKLOADS[o.workload].label}</span>', unsafe_allow_html=True)
        top[0].markdown(f"### {o.title}")
        top[1].button("All work orders", width="stretch", on_click=go, args=("Work orders",), kwargs=dict(wo_key=None))
        pauses = o.pauses
        stage = len(plans)
        finished = stage > len(pauses)
        until = 24.0 if finished or stage == 0 else pauses[stage - 1]

        def targets_table(rows=None):
            h = "<table class='cf-t'><tr><th>Target</th><th>Limit</th>" + ("<th>Achieved</th><th>Margin</th><th></th>" if rows else "<th>For an A</th>") + "</tr>"
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
            return (h + "</table><div class='cf-mono' style='margin-top:8px'>PUE = total power ÷ computer power; lower is better. "
                    "Server inlet = temperature of the air (or coolant) reaching the servers. "
                    "Compute lost = work the GPUs skipped because they got too hot.</div>")

        def guide(step):
            if o.guide and step < len(o.guide):
                card(f'<div class="n">GUIDE · STEP {step + 1} OF {len(o.guide)}</div>{o.guide[step]}', "cf-guide")

        if stage == 0:                                   # ---- briefing
            a, b = st.columns([1.2, 1])
            with a:
                card(f"<b>The job.</b> {o.brief}<br><br><b>How it is scored.</b> Each attempt earns a grade for the setup you chose. A: every target met, with room "
                     f"to spare. B: every target met. C: servers safe, efficiency missed. D: a safety limit crossed. Retry as often as you like.", "cf-card cf-job")
                if o.events:
                    card("<b>Expect:</b> the shift pauses when something happens, so you can change the plant and resume.", "cf-note")
            with b:
                card(targets_table(), "cf-card cf-targets")
            guide(2 if ("wo_prev_" + key) in st.session_state else 0)
            H("Set the plant for the start of the shift")
            v = settings_toolbar(f"wo{key}{var}t{tries}s0", o.locks, dict(o.start, **last[0]) if last else o.start, o.limits)
            if last:
                st.caption("These are the settings from your last attempt.")
            fixed = [LOCK_NAMES[k] for k in o.locks if k in LOCK_NAMES]
            if fixed:
                st.caption("Fixed by this work order: " + ", ".join(fixed) + ".")
            c = st.columns([1, 1, 1, 3])
            c[0].button("Start shift", type="primary", width="stretch", on_click=lambda: plans.append(v))
            c[1].button("New numbers", width="stretch", on_click=new_numbers, key="nn0",
                        help="Same problem with different numbers. There are three sets.")
            if last:
                c[2].button("Reset the plant", width="stretch", on_click=reset_plant,
                            help="Put every setting back to where this work order starts.")
            with st.expander("Hint"):
                st.write(o.hint)
            T.tour("brief", T.BRIEF, FORCE)
        else:
            day = run_wo(key, var, tuple(freeze(p) for p in plans), until)
            if not finished:                             # ---- paused at an event
                ev = [e for e in o.events if e.pause][stage - 1]
                card(f'<span class="cf-mono">PAUSED AT {int(ev.t):02d}:{int(ev.t % 1 * 60):02d}</span><br>'
                     f'<span style="font-size:18px;font-weight:600">{ev.title}</span><br>{ev.text}',
                     ("cf-alert" if ev.kind == "trip" else "cf-note") + " cf-event")
                H("Change the plant, then resume")
                dflt = dict(plans[-1])
                if last and stage < len(last):               # repeat what you changed at this pause last time
                    dflt.update({k: x for k, x in last[stage].items() if last[stage - 1].get(k) != x})
                    if dflt != plans[-1]:
                        st.caption("The change you made at this pause last time is already applied.")
                v = settings_toolbar(f"wo{key}{var}t{tries}s{stage}", o.locks, dflt, o.limits)
                c = st.columns([1, 1, 4])
                c[0].button("Resume shift", type="primary", width="stretch", on_click=lambda: plans.append(v))
                c[1].button("Restart", width="stretch", on_click=lambda: plans.clear())
                with st.expander("Hint"):
                    st.write(o.hint)
                st.iframe(plant_html(day, start="end", focus="hall" if ev.kind in ("trip", "load") else "tower"), height=PLANT_H)
                T.tour("pause", T.PAUSE, FORCE)
            else:                                        # ---- debrief
                grade, rows = evaluate(o, day.metrics)
                best = st.session_state["grades"].get(key)
                if best is None or grade < best:
                    st.session_state["grades"][key] = grade
                a, b = st.columns([1, 2.4])
                colr = {"A": "#D9A441", "B": "#D9A441", "C": "#D9A441", "D": "#8A929C"}[grade]
                with a:
                    card(f'<span class="cf-mono">SHIFT COMPLETE</span><br><span class="cf-grade" style="color:{colr}">{grade}</span><br>'
                         + VERDICT[grade], "cf-card cf-gradecard")
                with b:
                    card(targets_table(rows), "cf-card cf-targets")
                if o.guide:
                    guide(1 if grade in "CD" else 3)
                    if grade in "CD":
                        guide(2)
                card("<b>What happened.</b> " + what_happened(day, st.session_state.get("wo_prev_" + key),
                                                                 "cost_cooling" if any(t.metric == "cost_cooling" for t in o.targets) else "pue"), "cf-card cf-what")
                if grade in "AB":
                    card(f"<b>Why it worked.</b> {o.lesson}<br><span class='cf-mono'>The idea: {o.teaches}</span>", "cf-note")
                else:
                    with st.expander("Hint"):
                        st.write(o.hint)
                c = st.columns([1, 1, 1, 3])

                def again():
                    st.session_state["wo_prev_" + key] = dict(day.metrics, short_MW=float(np.max(day.series["shortfall"])) / 1e6)
                    st.session_state["wo_last_" + key] = [dict(p) for p in plans]
                    st.session_state["wo_try_" + key] = tries + 1
                    plans.clear()
                c[0].button("Try again", type="primary" if grade in "CD" else "secondary", width="stretch", on_click=again)
                nxt = ORDERS[(ORDERS.index(WORK_ORDERS[key]) + 1) % len(ORDERS)]
                c[1].button("New numbers", width="stretch", on_click=new_numbers, key="nn1",
                            help="Same problem with different numbers. There are three sets.")
                c[2].button(f"Next: {nxt.title}", width="stretch", on_click=go, args=("Work orders",), kwargs=dict(wo_key=nxt.key))
                day_dashboard(day, "wo" + key)
                T.tour("result", T.RESULT, FORCE)

# ---------------------------------------------------------------- CONSOLE (free play)
elif view == "Console":
    st.markdown("### Console")
    st.caption("Free play. Any site, any workload, any plant. No targets and no rating: just try things and see what happens.")
    c = st.columns([1.2, 1.1, 1.9, 1.3])
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
        g[2].metric("Share of Carnot", f"{100 * cyc.second_law_eff:.0f} %")
        g[3].metric("Cooling", f"{Q_kW:,.0f} kW")
        g[4].metric("Power in", f"{W_kW:,.0f} kW")
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
               f"checks run as {N_TESTS} automated tests.")
    P = proof_data()
    H("1 · The cycle against a textbook")
    st.write("Çengel and Boles, Example 11-1: ideal R-134a cycle, 0.14 to 0.8 MPa, 0.05 kg/s.")
    names = {"Q_L_kW": "Cooling, Q_L [kW]", "W_kW": "Compressor work, W [kW]", "Q_H_kW": "Heat rejected, Q_H [kW]", "COP": "COP"}
    st.dataframe(pd.DataFrame(P["tb"]).assign(quantity=lambda d: d["quantity"].map(names)).rename(columns={"error_pct": "difference [%]"}).style.format(precision=3),
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
