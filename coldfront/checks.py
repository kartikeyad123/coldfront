"""
checks.py - Is the model right? Five independent checks.

1. Textbook benchmark: an ideal R-134a refrigeration cycle between 0.14 and
   0.8 MPa with 0.05 kg/s of refrigerant (Cengel & Boles, Example 11-1) has
   Q_L = 7.18 kW, W_in = 1.81 kW, Q_H = 8.99 kW and COP_R = 3.97.
2. First law for the cycle: q_cond = q_evap + w_comp.
3. Second law: every device generates entropy (S_gen >= 0), and the COP never
   reaches the Carnot COP.
4. Whole-day energy balance: heat rejected outdoors equals IT heat + fan heat +
   compressor work - energy stored in the hall - energy stored in the tank.
5. Time-step convergence of the day simulation.
"""

from dataclasses import replace

from .chiller import (cycle_at_pressures, solve_cycle, REFRIGERANTS, operate,
                      AHRI_RANGE_E, AHRI_RANGE_C)
from .plant import PlantSettings
from .day import simulate_day

TEXTBOOK = dict(fluid="R134a", P_low=0.14e6, P_high=0.8e6, m_dot=0.05,
                Q_L_kW=7.18, W_kW=1.81, Q_H_kW=8.99, COP=3.97,
                source="Cengel & Boles, Thermodynamics, Example 11-1")


def textbook_benchmark():
    c = cycle_at_pressures(TEXTBOOK["fluid"], TEXTBOOK["P_low"], TEXTBOOK["P_high"])
    m = TEXTBOOK["m_dot"]
    model = dict(Q_L_kW=m * c.q_evap / 1e3, W_kW=m * c.w_comp / 1e3,
                 Q_H_kW=m * c.q_cond / 1e3, COP=c.cop)
    rows = []
    for k in ("Q_L_kW", "W_kW", "Q_H_kW", "COP"):
        rows.append(dict(quantity=k, textbook=TEXTBOOK[k], model=model[k],
                         error_pct=100 * abs(model[k] - TEXTBOOK[k]) / TEXTBOOK[k]))
    return rows, c


def entropy_generation(cycle, m_ref, T_chw_mean, T_cw_mean):
    """Entropy generated (W/K) in each device of the cycle.
    Evaporator: refrigerant gains s, chilled water loses Q/T.
    Condenser: refrigerant loses s, condenser water gains Q/T."""
    s1, s2, s3, s4 = cycle.s
    h1, h2, h3, h4 = cycle.h
    Q_e, Q_c = m_ref * (h1 - h4), m_ref * (h2 - h3)
    return dict(
        compressor=m_ref * (s2 - s1),
        condenser=m_ref * (s3 - s2) + Q_c / T_cw_mean,
        valve=m_ref * (s4 - s3),
        evaporator=m_ref * (s1 - s4) - Q_e / T_chw_mean,
    )


def cycle_law_checks():
    """First- and second-law checks over a grid of operating points for every
    refrigerant. Returns the worst first-law error and any violations."""
    worst_first, violations, n = 0.0, [], 0
    for fluid in REFRIGERANTS:
        for T_e in (275.15, 280.15, 285.15):
            for T_c in (300.15, 310.15, 320.15):
                for eta in (0.6, 0.8, 1.0):
                    c = solve_cycle(fluid, T_e, T_c, eta)
                    n += 1
                    err = abs(c.q_cond - (c.q_evap + c.w_comp)) / c.q_cond
                    worst_first = max(worst_first, err)
                    sg = entropy_generation(c, 1.0, T_e + 4, T_c - 4)
                    tol = 1e-8 * abs(c.s[0])     # round-off level of the property solver
                    if min(sg.values()) < -tol:
                        violations.append((fluid, T_e, T_c, eta, "S_gen < 0"))
                    if c.cop >= c.cop_carnot:
                        violations.append((fluid, T_e, T_c, eta, "COP >= Carnot"))
    return dict(cases=n, worst_first_law_err=worst_first, violations=violations)


def timestep_study(climate="la_typical", workload="training", dts=(120, 60, 30, 15, 7.5, 3.75)):
    """Halve the step until the answer stops changing. The finest step is the
    reference; the error should fall in proportion to dt (forward Euler is
    first-order), so the observed order should be about 1."""
    s = PlantSettings(n_chillers=3)
    rows = []
    for dt in dts:
        m = simulate_day(s, climate, workload, dt=dt).metrics
        rows.append(dict(dt=dt, T_inlet_max=m["T_inlet_max"], pue=m["pue"],
                         compute_lost_pct=m["compute_lost_pct"], compute_lost_MWh=m["compute_lost_MWh"]))
    ref = rows[-1]["compute_lost_MWh"]
    for r in rows:
        r["err"] = abs(r["compute_lost_MWh"] - ref)
    return rows


# --------------------------------------------------------------------------
# 6. Real equipment: AHRI 550/590 ratings, ASHRAE 90.1 limits and reference curves
# --------------------------------------------------------------------------
KW_PER_TON = 3.51685   # kW of cooling in one ton of refrigeration
F2C = lambda f: (f - 32.0) / 1.8
C2F = lambda c: c * 1.8 + 32.0

# ASHRAE 90.1 Table 6.8.1-3, water-cooled centrifugal, >= 600 tons (kW/ton)
CODE = dict(path_A=dict(full=0.560, iplv=0.500), path_B=dict(full=0.585, iplv=0.380))
# AHRI 550/590 IPLV: (load fraction, entering condenser water F, weight); 44 F chilled water
IPLV_POINTS = ((1.00, 85.0, 0.01), (0.75, 75.0, 0.42), (0.50, 65.0, 0.45), (0.25, 65.0, 0.12))
# ASHRAE 90.1-2022 Appendix J reference curves, Path B centrifugal >= 600 tons (temperatures in F)
_EIRFT_B = (0.593414, -0.028948, 0.000224, 0.024197, -0.000126, 0.000027)
_EIRFPLR_B = (0.058583, 0.205486, 0.736345)
# Independent published performance of a variable-speed centrifugal chiller at 50 % load
# (Facilitiesnet, "Ignore peak load chiller efficiency"): kW/ton at 85 F and at 60 F condenser water
PUBLISHED_VSD = ((0.50, 85.0, 0.57), (0.50, 60.0, 0.25))
BEST_IN_CLASS_IPLV = KW_PER_TON / 11.4      # Carrier 19MV data-center chiller, IPLV COP 11.4


def reference_kw_per_ton(chws_F, ecwt_F, plr):
    """kW/ton of the 90.1 Appendix J Path B reference chiller."""
    a, b, c, d, e, f = _EIRFT_B
    ft = a + b * chws_F + c * chws_F ** 2 + d * ecwt_F + e * ecwt_F ** 2 + f * chws_F * ecwt_F
    p = _EIRFPLR_B
    return CODE["path_B"]["full"] * ft * (p[0] + p[1] * plr + p[2] * plr ** 2) / plr


def rate(chws_F, ecwt_F, plr, s: PlantSettings = None):
    """The model chiller on an AHRI-style test: constant water flows, so the
    water temperature ranges shrink with load. Returns the operate() dict
    plus kW/ton."""
    s = s or PlantSettings()
    o = dict(operate(s.fluid, F2C(chws_F) + 273.15, AHRI_RANGE_E * plr, F2C(ecwt_F) + 273.15,
                     AHRI_RANGE_C * plr, plr, s.eta_rated, s.motor_eff, s.superheat, s.subcool))
    o["kw_per_ton"] = KW_PER_TON * o["w_elec"]
    return o


def iplv(s: PlantSettings = None):
    rows, inv = [], 0.0
    for plr, ecwt, w in IPLV_POINTS:
        o = rate(44.0, ecwt, plr, s)
        rows.append(dict(load=plr, ecwt_F=ecwt, weight=w, model=o["kw_per_ton"],
                         reference=reference_kw_per_ton(44.0, ecwt, plr), eta=o["eta"], x=o["x"]))
        inv += w / o["kw_per_ton"]
    return dict(rows=rows, iplv=1.0 / inv, limit=CODE["path_B"]["iplv"], best=BEST_IN_CLASS_IPLV)


CALIBRATION_POINTS = ((44, 85, 1.0), (44, 75, 0.75), (44, 65, 0.5), (44, 65, 0.25),
                      (44, 65, 1.0), (44, 75, 1.0), (44, 95, 1.0))


def calibrate_compressor_map():
    """Least-squares fit of the three compressor-map numbers to seven points of
    the Path B reference curves (the four IPLV points and the full-load line).
    Returns the fitted values; chiller.py holds the rounded results."""
    import math
    from scipy.optimize import least_squares
    from . import chiller as ch
    keep = (ch._MAP["choke_exp"],)

    def resid(p):
        ch._MAP["choke_exp"] = p[1]
        ch._operate.cache_clear()
        out = []
        for chws, ecwt, plr in CALIBRATION_POINTS:
            o = ch.operate("R134a", F2C(chws) + 273.15, AHRI_RANGE_E * plr, F2C(ecwt) + 273.15,
                           AHRI_RANGE_C * plr, plr, eta_peak=p[0], fixed_loss=p[2])
            out.append(math.log(KW_PER_TON * o["w_elec"] / reference_kw_per_ton(chws, ecwt, plr)))
        return out

    sol = least_squares(resid, [0.80, 2.5, 0.03], bounds=([0.5, 0.0, 0.0], [0.95, 6.0, 0.2]), diff_step=1e-2)
    rms = (sum(r * r for r in resid(sol.x)) / len(CALIBRATION_POINTS)) ** 0.5
    ch._MAP["choke_exp"] = keep[0]
    ch._operate.cache_clear()
    return dict(eta_peak=float(sol.x[0]), choke_exp=float(sol.x[1]), fixed_loss=float(sol.x[2]), rms=float(rms))


def map_validation(s: PlantSettings = None):
    """Checks on points that were NOT used to calibrate the map."""
    s = s or PlantSettings()
    ip = iplv(s)
    full = rate(44.0, 85.0, 1.0, s)
    rows = [
        dict(check="Full load at AHRI conditions", source="ASHRAE 90.1 Path B limit", ref=CODE["path_B"]["full"],
             model=full["kw_per_ton"], rule="<="),
        dict(check="IPLV (AHRI 550/590 weighting)", source="ASHRAE 90.1 Path B limit", ref=ip["limit"],
             model=ip["iplv"], rule="<="),
        dict(check="IPLV, best in class", source="Carrier 19MV (IPLV COP 11.4)", ref=ip["best"],
             model=ip["iplv"], rule=">="),
    ]
    for plr, ecwt, kw in PUBLISHED_VSD:
        rows.append(dict(check=f"{plr:.0%} load, {ecwt:.0f} F condenser water", source="published VSD chiller data",
                         ref=kw, model=rate(44.0, ecwt, plr, s)["kw_per_ton"], rule="~"))
    for r in rows:
        r["diff_pct"] = 100 * (r["model"] / r["ref"] - 1)
        r["ok"] = (r["model"] <= r["ref"] * 1.001 if r["rule"] == "<=" else
                   r["model"] >= r["ref"] if r["rule"] == ">=" else abs(r["diff_pct"]) <= 15)
    # chilled-water sensitivity: LBNL data-center guide says 1-2 % per F
    a, b = rate(44.0, 75.0, 0.75, s)["kw_per_ton"], rate(54.0, 75.0, 0.75, s)["kw_per_ton"]
    sens = 100 * (1 - (b / a) ** (1 / 10))
    rows.append(dict(check="Gain per F of warmer chilled water", source="LBNL guide: 1 to 2 % per F", ref=1.5,
                     model=sens, rule="1-2", diff_pct=float("nan"), ok=1.0 <= sens <= 2.0))
    # held-out reference-curve points: other chilled-water temperatures along the IPLV path
    held = []
    for chws in (40, 48, 52, 56, 60):
        for plr, ecwt, _ in IPLV_POINTS:
            held.append(dict(chws_F=chws, ecwt_F=ecwt, load=plr, reference=reference_kw_per_ton(chws, ecwt, plr),
                             model=rate(chws, ecwt, plr, s)["kw_per_ton"]))
    rms = (sum((h["model"] / h["reference"] - 1) ** 2 for h in held) / len(held)) ** 0.5
    return dict(rows=rows, held=held, held_rms_pct=100 * rms, iplv=ip)


def ahri_rating(s: PlantSettings = None):
    """Electrical kW/ton of the model chiller at AHRI full-load rating conditions."""
    o = rate(44.0, 85.0, 1.0, s)
    c = o["cycle"]
    return dict(cop_cycle=c.cop, cop_electrical=o["cop_elec"], kw_per_ton=o["kw_per_ton"],
                cop_carnot=c.cop_carnot, cycle=c, limit=CODE["path_B"]["full"], op=o)


# --------------------------------------------------------------------------
# 7. Second law for the whole chiller: where does the work go?
# --------------------------------------------------------------------------
def exergy_audit(s: PlantSettings = None, T_chws_C=10.0, T_ecw_C=21.0, plr=0.7, Q=1.0e6):
    """Entropy generated in each device, using the actual water streams, and the
    Gouy-Stodola closure:   W_actual = W_reversible + T0 * sum(S_gen).

    W_reversible is the least work that could move the same heat between the
    same two water streams (their exergy change, dead state T0 = entering
    condenser water). The closure only holds if energy is conserved AND the
    entropies of the four state points are consistent around the cycle."""
    import math
    s = s or PlantSettings()
    Te_out, Tc_in = T_chws_C + 273.15, T_ecw_C + 273.15
    o = operate(s.fluid, Te_out, s.dT_chw, Tc_in, s.dT_cw, plr, s.eta_rated, s.motor_eff, s.superheat, s.subcool)
    c = o["cycle"]
    m = Q / c.q_evap
    Q_c = m * c.q_cond
    cp = 4186.0
    m_e, m_c = Q / (cp * s.dT_chw), Q_c / (cp * s.dT_cw)
    Te_in, Tc_out = Te_out + s.dT_chw, Tc_in + s.dT_cw
    s1, s2, s3, s4 = c.s
    sg = dict(
        compressor=m * (s2 - s1),
        condenser=m * (s3 - s2) + m_c * cp * math.log(Tc_out / Tc_in),
        valve=m * (s4 - s3),
        evaporator=m * (s1 - s4) + m_e * cp * math.log(Te_out / Te_in),
    )
    T0 = Tc_in
    W = m * c.w_comp
    W_rev = (m_e * cp * ((Te_out - Te_in) - T0 * math.log(Te_out / Te_in))
             + m_c * cp * ((Tc_out - Tc_in) - T0 * math.log(Tc_out / Tc_in)))
    lost = {k: T0 * v for k, v in sg.items()}
    closure = abs(W - (W_rev + sum(lost.values()))) / W
    return dict(S_gen=sg, lost_work=lost, W=W, W_rev=W_rev, T0=T0, closure=closure, op=o,
                second_law_eff=W_rev / W, m_ref=m, m_chw=m_e, m_cw=m_c)


# --------------------------------------------------------------------------
# 8. Conservation audit of one plant state, from primitive quantities
# --------------------------------------------------------------------------
def step_audit(s: PlantSettings = None, Q_demand=8.0e6, T_db_C=28.0, T_wb_C=18.0, T_dew_C=12.0):
    """Recompute every energy and mass flow of one plant state from flows,
    temperatures and enthalpies (not from the heat rates the solver stored),
    and compare. Rows: (balance, left side, right side, relative error)."""
    from .plant import plant_step
    s = s or PlantSettings()
    p = plant_step(s, Q_demand, T_db_C + 273.15, T_wb_C + 273.15, 0.0, 0.0, T_dew_C + 273.15)
    c, m, cp = p["cycle"], p["m_ref"], 4186.0
    h1, h2, h3, h4 = c.h
    rows = []

    def add(name, kind, lhs, rhs, unit):
        rows.append(dict(balance=name, kind=kind, lhs=lhs, rhs=rhs, unit=unit,
                         rel_err=abs(lhs - rhs) / max(abs(lhs), 1e-12)))
    add("Refrigerant cycle: q_H = q_L + w", "energy", m * (h2 - h3), m * (h1 - h4) + m * (h2 - h1), "W")
    add("Evaporator: water side = refrigerant side", "energy", p["Q_ch"] + p["Q_chg"], m * (h1 - h4), "W")
    add("Chilled-water loop: coil heat + pump heat = free cooling + chillers + tank + unmet", "energy",
        Q_demand + p["P_chw_shaft"], p["Q_fc"] + p["Q_ch"] + p["Q_dis"] + p["shortfall"], "W")
    add("Chilled water: m cp dT = loop load", "energy", p["m_chw"] * cp * s.dT_chw, p["Q_loop"] + p["Q_chg"], "W")
    add("Condenser-water loop: m cp dT = condenser + free cooling + pump heat", "energy",
        p["m_cw"] * cp * s.dT_cw, m * (h2 - h3) + p["Q_fc"] + p["P_cw_shaft"], "W")
    add("Plant: heat rejected = heat in + shaft work", "energy", p["Q_rej"],
        Q_demand - p["shortfall"] - p["Q_dis"] + p["Q_chg"] + p["W_shaft"] + p["P_chw_shaft"] + p["P_cw_shaft"], "W")
    add("Refrigerant: same mass flow through all four devices", "mass", m, (p["Q_ch"] + p["Q_chg"]) / c.q_evap, "kg/s")
    add("Tower water: make-up = evaporation + drift + blowdown", "mass", p["water"],
        p["evaporation"] + p["drift"] + p["blowdown"], "kg/s")
    from .tower import CYCLES_OF_CONCENTRATION as COC
    add("Tower salts: make-up = COC x (blowdown + drift)", "mass", p["water"], COC * (p["blowdown"] + p["drift"]), "kg/s")
    return rows, p


def negative_control(climate="la_typical"):
    """Proof that the daily energy balance CAN fail: repeat it while leaving the
    pump heat out of the ledger. The error should jump from round-off to about 1 %."""
    r = simulate_day(PlantSettings(), climate, "inference")
    m = r.metrics
    heat_in = m["E_rej_MWh"]
    without_pumps = abs(m["E_pump_heat_MWh"]) / heat_in * 100
    return dict(correct_err_pct=m["energy_balance_err_pct"], without_pump_heat_err_pct=without_pumps)


def worked_example(s: PlantSettings = None, T_evap_C=9.0, T_cond_C=30.0):
    """Step-by-step numbers for one cycle, laid out the way it is done by
    hand from property tables (used on the Proof page and in the guide)."""
    s = s or PlantSettings()
    eta = 0.80
    c = solve_cycle(s.fluid, T_evap_C + 273.15, T_cond_C + 273.15, eta, s.superheat, s.subcool)
    return dict(fluid=s.fluid, eta=eta, superheat=s.superheat, subcool=s.subcool,
                T_evap_C=T_evap_C, T_cond_C=T_cond_C, P_evap_kPa=c.P_evap / 1e3, P_cond_kPa=c.P_cond / 1e3,
                h1=c.h[0] / 1e3, s1=c.s[0] / 1e3, h2s=c.h2s / 1e3, h2=c.h[1] / 1e3, T2_C=c.T[1] - 273.15,
                h3=c.h[2] / 1e3, h4=c.h[3] / 1e3, q_evap=c.q_evap / 1e3, w_comp=c.w_comp / 1e3,
                q_cond=c.q_cond / 1e3, cop=c.cop, cop_carnot=c.cop_carnot)
