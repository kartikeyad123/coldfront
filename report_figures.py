"""
report_figures.py - Runs every investigation in the report, draws every figure
(vector PDF at print size) and writes report/numbers.tex so no number in the
report is typed by hand.      Run:  python report_figures.py
"""

import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from coldfront.plant import PlantSettings, C2K
from coldfront.day import simulate_day
from coldfront.chiller import solve_cycle, REFRIGERANTS
from coldfront.scenarios import CLIMATES
from coldfront import checks
from ui.charts import _dome   # saturation dome helper (plotting only)

os.makedirs("report/fig", exist_ok=True)
plt.rcParams.update({
    "font.family": "Liberation Serif", "mathtext.fontset": "stix", "font.size": 9,
    "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 7.5,
    "lines.linewidth": 0.8, "axes.linewidth": 0.5, "xtick.direction": "out", "ytick.direction": "out",
    "axes.unicode_minus": True, "legend.frameon": False, "pdf.fonttype": 42})
K, B, R, GY = "k", (0.10, 0.30, 0.62), (0.70, 0.15, 0.10), (0.55, 0.55, 0.55)
HRS = list(range(0, 25, 4))
N = {}          # numbers for the report


def save(f, name):
    f.savefig(f"report/fig/{name}.pdf")
    plt.close(f)


def panel(ax, text, y=0.96):
    ax.text(0.03, y, text, transform=ax.transAxes, va="top", ha="left", fontsize=8,
            bbox=dict(facecolor="white", edgecolor="none", pad=0.6))


def room(ax, frac=0.2):
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + frac * (hi - lo))


def hours(ax):
    ax.set_xticks(HRS)
    ax.set_xticklabels([f"{h:02d}" for h in HRS])
    ax.set_xlim(0, 24)
    ax.set_xlabel(r"time of day [h]")


def day(**kw):
    clim = kw.pop("climate", "la_typical")
    work = kw.pop("workload", "inference")
    tariff = kw.pop("tariff", "retail")
    return simulate_day(PlantSettings(**kw), clim, work, tariff_key=tariff)


# ============================================================ baseline day
base = day(climate="la_hot")
x, m = base.series, base.metrics
f, ax = plt.subplots(2, 2, figsize=(6.5, 4.4))
a = ax[0, 0]
a.plot(x["hour"], x["T_db"], color=GY, label="outdoor dry-bulb")
a.plot(x["hour"], x["T_wb"], color=GY, ls="--", label="outdoor wet-bulb")
a.plot(x["hour"], x["T_cond"], color=R, label="condensing")
a.plot(x["hour"], x["T_evap"], color=B, label="evaporating")
a.plot(x["hour"], x["T_inlet"], color=K, lw=1.3, label="server inlet")
a.set_ylabel(r"$T$ [°C]"); hours(a); room(a, 0.75)
a.legend(ncol=2, loc="upper left", bbox_to_anchor=(0, 0.88), fontsize=6.8)
panel(a, "(a)  temperatures")
a = ax[0, 1]
a.stackplot(x["hour"], x["W_comp"] / 1e6, (x["P_chw"] + x["P_cw"]) / 1e6, (x["P_fans"] + x["P_crah"]) / 1e6,
            colors=[B, GY, (0.8, 0.8, 0.8)], labels=["compressors", "pumps", "fans"])
a.set_ylabel(r"cooling power [MW]"); hours(a); room(a, 0.45)
a.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, 0.87))
panel(a, "(b)  cooling electricity")
a = ax[1, 0]
a.plot(x["hour"], x["cop"], color=K, label="chiller COP")
a.plot(x["hour"], x["cop_carnot"], color=GY, ls="--", label="Carnot COP")
a.set_ylabel("COP"); hours(a); a.set_ylim(0, 1.45 * np.nanmax(x["cop_carnot"]))
a.legend(loc="upper right", bbox_to_anchor=(1, 0.85))
panel(a, "(c)  chiller COP vs. Carnot limit")
a = ax[1, 1]
a.plot(x["hour"], x["pue"], color=K)
a.set_ylabel("PUE"); hours(a); room(a, 0.35)
a2 = a.twinx(); a2.step(x["hour"], x["price"], color=B, where="post", lw=0.8)
a2.set_ylabel(r"price [\$/MWh]", color=B); a2.tick_params(axis="y", colors=B); a2.set_ylim(0, 220)
panel(a, "(d)  PUE (black), electricity price (blue)")
f.tight_layout(pad=0.4, h_pad=0.8, w_pad=1.0)
save(f, "Fig2_baseline")
N.update(B_pue=m["pue"], B_cop=m["cop_mean"], B_Ecool=m["E_cool_MWh"], B_Ecomp=m["E_comp_MWh"],
         B_Eit=m["E_it_MWh"], B_cost=m["cost_cooling"], B_costtot=m["cost_total"], B_water=m["water_m3"],
         B_wue=m["wue_L_per_kWh"], B_chmax=m["chillers_max"], B_Tin=m["T_inlet_max"],
         B_copmin=float(np.nanmin(x["cop"])), B_copmax=float(np.nanmax(x["cop"])),
         B_carmin=float(np.nanmin(x["cop_carnot"])), B_eff2=float(np.nanmean(x["cop"] / x["cop_carnot"])),
         B_eff2cyc=m["eff2_mean"], B_plr=m["plr_mean"], B_evap=m["evaporation_m3"], B_blow=m["blowdown_m3"],
         B_drift=m["drift_m3"], B_pumpheat=m["E_pump_heat_MWh"], B_Erej=m["E_rej_MWh"],
         B_evapratio=m["evaporation_m3"] * 998 * 2.43e6 / (m["E_rej_MWh"] * 3.6e9),
         B_Tcondmin=float(x["T_cond"].min()), B_Tcondmax=float(x["T_cond"].max()),
         B_compshare=100 * m["E_comp_MWh"] / m["E_cool_MWh"], B_itmin=float(x["Q_it"].min() / 1e6),
         B_itmax=float(x["Q_it"].max() / 1e6), B_puemin=float(x["pue"].min()), B_puemax=float(x["pue"].max()))

# ============================================================ cycle diagrams at 15:00
k15 = int(15 * 3600 / 30)
cyc = solve_cycle("R134a", x["T_evap"][k15] + C2K, x["T_cond"][k15] + C2K, float(x["eta"][k15]), 1.0, 2.0)
f, ax = plt.subplots(1, 2, figsize=(6.5, 2.7))
dx, dy = _dome("R134a", "H", "P")
ax[0].plot(np.array(dx) / 1e3, np.array(dy) / 1e3, color=GY, lw=0.7)
from ui.charts import _cycle_path
hx, py = _cycle_path(cyc, "ph")
ax[0].plot(hx, py, color=K, lw=1.2)
for i, (hh, pp) in enumerate(zip(np.array(cyc.h) / 1e3, np.array([cyc.P_evap, cyc.P_cond, cyc.P_cond, cyc.P_evap]) / 1e3)):
    ax[0].plot(hh, pp, "o", color=B, ms=3.5)
    ax[0].annotate(str(i + 1), (hh, pp), xytext=([6, 6, -10, -10][i], [-10, 4, 4, -10][i]), textcoords="offset points", fontsize=8)
ax[0].set(yscale="log", xlabel=r"$h$ [kJ/kg]", ylabel=r"$P$ [kPa]", xlim=(180, 460), ylim=(150, 3000))
panel(ax[0], "(a)  P–h diagram")
dx, dy = _dome("R134a", "S", "T")
ax[1].plot(np.array(dx) / 1e3, np.array(dy) - C2K, color=GY, lw=0.7)
sx, ty = _cycle_path(cyc, "ts")
ax[1].plot(sx, ty, color=K, lw=1.2)
for i, (ss, tt) in enumerate(zip(np.array(cyc.s) / 1e3, np.array(cyc.T) - C2K)):
    ax[1].plot(ss, tt, "o", color=B, ms=3.5)
    ax[1].annotate(str(i + 1), (ss, tt), xytext=([5, 5, -10, -10][i], [-10, 4, 4, -10][i]), textcoords="offset points", fontsize=8)
ax[1].set(xlabel=r"$s$ [kJ/(kg K)]", ylabel=r"$T$ [°C]", xlim=(0.95, 1.85), ylim=(-25, 90))
panel(ax[1], "(b)  T–s diagram")
f.tight_layout(pad=0.4, w_pad=1.5)
save(f, "Fig3_cycle")
N.update(C_Te=cyc.T_evap - C2K, C_Tc=cyc.T_cond - C2K, C_Pe=cyc.P_evap / 1e3, C_Pc=cyc.P_cond / 1e3,
         C_h1=cyc.h[0] / 1e3, C_h2=cyc.h[1] / 1e3, C_h3=cyc.h[2] / 1e3, C_T2=cyc.T[1] - C2K,
         C_qe=cyc.q_evap / 1e3, C_w=cyc.w_comp / 1e3, C_qc=cyc.q_cond / 1e3, C_cop=cyc.cop, C_car=cyc.cop_carnot,
         C_eta=float(x["eta"][k15]), C_plr=float(x["plr"][k15]), C_non=int(x["n_on"][k15]), C_cope=float(x["cop"][k15]),
         C_ae=float(x["approach_evap"][k15]), C_ac=float(x["approach_cond"][k15]), C_arej=float(x["approach_rej"][k15]),
         C_mref=float(x["m_ref"][k15]), C_x=float(x["x_map"][k15]))

# ============================================================ validation
rows, _ = checks.textbook_benchmark()
ar = checks.ahri_rating()
law = checks.cycle_law_checks()
ts = checks.timestep_study()
N.update(V_tb={r["quantity"]: r for r in rows}, V_ahri=ar["kw_per_ton"], V_ahricop=ar["cop_electrical"],
         V_ahricar=ar["cop_carnot"], V_law=law["worst_first_law_err"], V_lawn=law["cases"],
         V_viol=len(law["violations"]))
eb = {}
for c in CLIMATES:
    mm = simulate_day(PlantSettings(), c, "inference").metrics
    eb[c] = mm["energy_balance_err_pct"]
mm = simulate_day(PlantSettings(n_chillers=3, tank=True, tank_soc0=1.0), "la_typical", "training").metrics
N.update(V_eb_max=max(eb.values()), V_eb_tank=mm["energy_balance_err_pct"])
we = checks.worked_example()
N["W"] = we
f, ax = plt.subplots(1, 2, figsize=(6.5, 2.5))
q = ["Q_L_kW", "W_kW", "Q_H_kW", "COP"]
lab = [r"$\dot Q_L$ [kW]", r"$\dot W$ [kW]", r"$\dot Q_H$ [kW]", "COP"]
xx = np.arange(4)
ax[0].bar(xx - 0.18, [N["V_tb"][k]["textbook"] for k in q], 0.36, color=GY, label="textbook")
ax[0].bar(xx + 0.18, [N["V_tb"][k]["model"] for k in q], 0.36, color=K, label="this model")
ax[0].set_xticks(xx); ax[0].set_xticklabels(lab); room(ax[0], 0.35)
ax[0].legend(loc="upper right")
panel(ax[0], "(a)  Çengel Example 11-1")
ax[1].loglog([r["dt"] for r in ts[:-1]], [max(r["err"], 1e-6) for r in ts[:-1]], "o-", color=K, ms=3.5)
ax[1].set(xlabel=r"time step $\Delta t$ [s]", ylabel="error in compute lost [MWh]")
ax[1].set_xticks([120, 60, 30, 15, 7.5]); ax[1].set_xticklabels(["120", "60", "30", "15", "7.5"])
ax[1].minorticks_off(); ax[1].invert_xaxis(); ax[1].set_ylim(1e-5, 50)
ax[1].axvline(30, color=GY, ls=":", lw=0.6); ax[1].text(29, 8, "step used", fontsize=7, color=GY)
panel(ax[1], "(b)  time-step convergence")
f.tight_layout(pad=0.4, w_pad=1.5)
save(f, "Fig4_validation")
N.update(TS={r["dt"]: r["T_inlet_max"] for r in ts}, TSerr={r["dt"]: r["err"] for r in ts},
         TS_order=float(np.log2(ts[1]["err"] / ts[3]["err"]) / 2))

# ---- the chiller as a machine: map, reference curves, published data, lost work
cal = checks.calibrate_compressor_map()
mv = checks.map_validation()
f, ax = plt.subplots(1, 2, figsize=(6.5, 2.9))
pl = np.linspace(0.2, 1.0, 33)
for ecwt, col in ((85.0, R), (75.0, K), (65.0, B)):
    ax[0].plot(100 * pl, [checks.rate(44.0, ecwt, float(q))["kw_per_ton"] for q in pl], color=col,
               label=f"model, {ecwt:.0f} °F")
    ax[0].plot(100 * pl, [checks.reference_kw_per_ton(44.0, ecwt, float(q)) for q in pl], color=col, ls=":", lw=0.7)
ax[0].plot([], [], color=GY, ls=":", lw=0.7, label="90.1 reference curve")
ax[0].plot([100 * q for q, _, _ in checks.PUBLISHED_VSD], [k for _, _, k in checks.PUBLISHED_VSD], "s", color="w",
           mec=K, ms=5, label="published VSD chiller")
ax[0].set(xlabel="load [% of rated]", ylabel="electricity [kW/ton]", ylim=(0.1, 1.05))
ax[0].legend(loc="upper left", bbox_to_anchor=(0, 0.9), fontsize=6.8, ncol=2)
panel(ax[0], "(a)  kW/ton at 44 °F chilled water")
ex_cases = [("AHRI full load\n29.4 °C, 100 %", dict(T_chws_C=6.67, T_ecw_C=29.44, plr=1.0)),
            ("design day\n21 °C, 70 %", dict(T_chws_C=10.0, T_ecw_C=21.0, plr=0.7)),
            ("low lift, full load\n15 °C, 100 %", dict(T_chws_C=10.0, T_ecw_C=15.0, plr=1.0))]
EX = {}
bottom = np.zeros(3)
parts = [("reversible work", GY), ("compressor", K), ("condenser", B), ("valve", (0.75, 0.75, 0.75)), ("evaporator", R)]
vals = {k: [] for k, _ in parts}
for lab, kw in ex_cases:
    a_ = checks.exergy_audit(**kw)
    EX[lab.split("\n")[0]] = dict(eff=a_["second_law_eff"], closure=a_["closure"], eta=a_["op"]["eta"], x=a_["op"]["x"],
                                  cop=a_["op"]["cycle"].cop, **{k: 100 * v / a_["W"] for k, v in a_["lost_work"].items()})
    vals["reversible work"].append(100 * a_["W_rev"] / a_["W"])
    for k in ("compressor", "condenser", "valve", "evaporator"):
        vals[k].append(100 * a_["lost_work"][k] / a_["W"])
for k, col in parts:
    ax[1].bar(range(3), vals[k], 0.55, bottom=bottom, color=col, label=k)
    bottom += np.array(vals[k])
ax[1].set_xticks(range(3)); ax[1].set_xticklabels([l for l, _ in ex_cases], fontsize=7)
ax[1].set(ylabel="share of compressor work [%]", ylim=(0, 165))
ax[1].legend(loc="upper left", bbox_to_anchor=(0, 0.9), fontsize=6.8, ncol=2)
panel(ax[1], "(b)  where the work goes (Gouy–Stodola)")
f.tight_layout(pad=0.4, w_pad=1.5)
save(f, "Fig4b_chiller")
audit_rows, _ = checks.step_audit()
neg = checks.negative_control()
mt = simulate_day(PlantSettings(n_chillers=3, tank=True, tank_soc0=1.0), "la_typical", "training").metrics
N.update(CAL=cal, MV=[{k: v for k, v in r.items()} for r in mv["rows"]], MV_held=mv["held_rms_pct"],
         IPLV=mv["iplv"]["iplv"], IPLVrows=mv["iplv"]["rows"], EX=EX,
         AUD_max=max(r["rel_err"] for r in audit_rows), AUD_n=len(audit_rows), NEG=neg,
         V_tankmass=mt["tank_mass_err_pct"], V_ahri_eta=ar["op"]["eta"],
         ref_sens=100 * (1 - (checks.reference_kw_per_ton(54, 75, .75) / checks.reference_kw_per_ton(44, 75, .75)) ** 0.1))
# staging: 8 MW on the baseline conditions with 3 or 4 machines
from coldfront.chiller import operate
st3 = operate("R134a", 283.15, 6.0, 294.15, 5.0, 8.0 / 9.0); st4 = operate("R134a", 283.15, 6.0, 294.15, 5.0, 8.0 / 12.0)
N.update(ST3=st3["cop_elec"], ST4=st4["cop_elec"], ST3x=st3["x"], ST4x=st4["x"], ST3eta=st3["eta"], ST4eta=st4["eta"])

# ============================================================ I1 set point
sps = np.arange(6, 20.5, 1.0)
I1 = {}
f, ax = plt.subplots(1, 2, figsize=(6.5, 2.6))
for clim, col, lab in (("la_typical", K, "Los Angeles, typical"), ("phoenix", R, "Phoenix, hot day")):
    res = [day(climate=clim, T_chws_C=float(t)).metrics for t in sps]
    I1[clim] = res
    ax[0].plot(sps, [r["cop_mean"] for r in res], "o-", ms=3, color=col, label=lab)
    ax[1].plot(sps, [r["pue"] for r in res], "o-", ms=3, color=col, label=lab)
ax[0].set(xlabel=r"chilled-water supply $T_\mathrm{chws}$ [°C]", ylabel="daily chiller COP"); room(ax[0], 0.25)
ax[0].legend(loc="upper left", bbox_to_anchor=(0, 0.86))
panel(ax[0], "(a)  chiller COP")
ax[1].set(xlabel=r"chilled-water supply $T_\mathrm{chws}$ [°C]", ylabel="daily PUE"); room(ax[1], 0.25)
ax[1].axvline(19, color=GY, ls=":", lw=0.6)
ax[1].text(18.8, ax[1].get_ylim()[1] * 0.995, "27 °C inlet\nlimit reached", ha="right", va="top", fontsize=7, color=GY)
panel(ax[1], "(b)  PUE")
f.tight_layout(pad=0.4, w_pad=1.5)
save(f, "Fig5_setpoint")
la7, la19 = I1["la_typical"][1], I1["la_typical"][13]   # 7 C and 19 C
ph7, ph19 = I1["phoenix"][1], I1["phoenix"][13]
N.update(I1_la7_cop=la7["cop_mean"], I1_la19_cop=la19["cop_mean"], I1_la7_pue=la7["pue"], I1_la19_pue=la19["pue"],
         I1_ph7_cop=ph7["cop_mean"], I1_ph19_cop=ph19["cop_mean"], I1_ph7_pue=ph7["pue"], I1_ph19_pue=ph19["pue"],
         I1_la19_fc=la19["free_cooling_hours"], I1_la7_cost=la7["cost_cooling"], I1_la19_cost=la19["cost_cooling"],
         I1_slope=100 * (I1["la_typical"][5]["cop_mean"] / I1["la_typical"][4]["cop_mean"] - 1))

# ============================================================ I2 climates + I3 water vs energy
sites = list(CLIMATES)
I2 = {c: {"tower": day(climate=c).metrics, "dry": day(climate=c, rejection="dry").metrics} for c in sites}
f, ax = plt.subplots(1, 2, figsize=(6.5, 2.8))
xx = np.arange(len(sites))
short = {"la_typical": "LA\ntypical", "la_hot": "LA\nhot", "phoenix": "Phoenix\nhot", "chicago_s": "Chicago\nhot",
         "chicago_w": "Chicago\nwinter", "denver": "Denver\nhot"}
ax[0].bar(xx - 0.18, [I2[c]["tower"]["pue"] for c in sites], 0.36, color=K, label="cooling tower")
ax[0].bar(xx + 0.18, [I2[c]["dry"]["pue"] for c in sites], 0.36, color=GY, label="dry cooler")
ax[0].set_xticks(xx); ax[0].set_xticklabels([short[c] for c in sites], fontsize=7)
ax[0].set_ylabel("daily PUE"); ax[0].set_ylim(1.0, 1.6)
ax[0].legend(loc="upper left", bbox_to_anchor=(0, 0.88))
panel(ax[0], "(a)  PUE by site and heat rejection")
for c in sites:
    t, d_ = I2[c]["tower"], I2[c]["dry"]
    ax[1].plot([d_["wue_L_per_kWh"], t["wue_L_per_kWh"]], [d_["pue"], t["pue"]], color=GY, lw=0.6)
    ax[1].plot(t["wue_L_per_kWh"], t["pue"], "o", color=K, ms=3.5)
    ax[1].plot(d_["wue_L_per_kWh"], d_["pue"], "s", color=B, ms=3.5)
order = sorted(sites, key=lambda c: I2[c]["tower"]["pue"])
ys = np.linspace(1.06, 1.36, len(order))
for c, yl in zip(order, ys):
    t = I2[c]["tower"]
    ax[1].annotate(short[c].replace("\n", " "), (t["wue_L_per_kWh"], t["pue"]), xytext=(2.55, yl), textcoords="data",
                   fontsize=6.5, va="center", arrowprops=dict(arrowstyle="-", color=GY, lw=0.4, shrinkA=1, shrinkB=2))
ax[1].set(xlabel=r"water use WUE [L/kWh$_\mathrm{IT}$]", ylabel="daily PUE", xlim=(-0.2, 3.7), ylim=(1.0, 1.6))
panel(ax[1], "(b)  water vs. energy (●tower, ■ dry)")
f.tight_layout(pad=0.4, w_pad=1.5)
save(f, "Fig6_sites")
N.update(I2={c: {k: {q: I2[c][k][q] for q in ("pue", "wue_L_per_kWh", "cop_mean", "E_comp_MWh", "free_cooling_hours", "water_m3", "evaporation_m3", "E_rej_MWh")} for k in I2[c]} for c in sites})

# ============================================================ I4 refrigerants + I5 compressor efficiency
T_e = np.linspace(2, 16, 15)
f, ax = plt.subplots(1, 2, figsize=(6.5, 2.6))
I4 = {}
styles = {"R134a": (K, "-"), "R1234ze(E)": (B, "--"), "R717": (R, "-."), "R290": (GY, ":")}
for fl in REFRIGERANTS:
    cops = [solve_cycle(fl, t + C2K, 36 + C2K, 0.83, 1, 2).cop * 0.96 for t in T_e]
    ax[0].plot(T_e, cops, color=styles[fl][0], ls=styles[fl][1], label=fl.replace("(E)", ""))
    s_ = PlantSettings(fluid=fl); r_ = checks.ahri_rating(s_)
    c_ = r_["cycle"]
    I4[fl] = dict(kw_ton=r_["kw_per_ton"], cop=r_["cop_electrical"], P_e=c_.P_evap / 1e3, P_c=c_.P_cond / 1e3,
                  T2=c_.T[1] - C2K, vol=None, pue=day(fluid=fl).metrics["pue"])
ax[0].set(xlabel=r"evaporating temperature [°C]", ylabel="electrical COP"); room(ax[0], 0.3)
ax[0].legend(loc="upper left", bbox_to_anchor=(0, 0.86), ncol=2)
panel(ax[0], "(a)  refrigerants, 36 °C condensing")
etas = np.arange(0.62, 0.905, 0.04)
for clim, col in (("la_typical", K), ("phoenix", R)):
    ax[1].plot(etas, [day(climate=clim, eta_rated=float(e)).metrics["E_comp_MWh"] for e in etas], "o-", ms=3, color=col,
               label=CLIMATES[clim].label)
ax[1].set(xlabel=r"compressor isentropic efficiency $\eta_c$", ylabel="compressor electricity [MWh/day]"); room(ax[1], 0.3)
ax[1].legend(loc="upper right", bbox_to_anchor=(1, 0.86))
panel(ax[1], "(b)  compressor efficiency")
f.tight_layout(pad=0.4, w_pad=1.5)
save(f, "Fig7_refrigerant_eta")
e62 = day(climate="phoenix", eta_rated=0.62).metrics["E_comp_MWh"]; e90 = day(climate="phoenix", eta_rated=0.90).metrics["E_comp_MWh"]
N.update(I4=I4, I5_ph62=e62, I5_ph90=e90, I5_cut=100 * (1 - e90 / e62))

# ============================================================ I6 chiller outage + training spike
cases = [("4 chillers", dict(), K, "-"), ("3 chillers", dict(n_chillers=3), R, "-"),
         ("3 chillers + storage reserve", dict(n_chillers=3, tank=True, price_charge=100.0, price_discharge=200.0), B, "--"),
         ("3 chillers + price-driven storage", dict(n_chillers=3, tank=True), (0.45, 0.6, 0.85), ":"),
         ("3 chillers, 17 °C water", dict(n_chillers=3, T_chws_C=17.0), GY, "-.")]
I6 = {}
f, ax = plt.subplots(1, 2, figsize=(6.5, 3.0))
for lab, kw, col, lsty in cases:
    d_ = day(workload="training", **kw)
    I6[lab] = d_.metrics
    ax[0].plot(d_.series["hour"], d_.series["T_inlet"], color=col, ls=lsty, label=lab)
    if lab == "3 chillers":
        ax[1].plot(d_.series["hour"], d_.series["Q_it_req"] / 1e6, color=GY, lw=0.6, label="IT demand")
        ax[1].plot(d_.series["hour"], d_.series["Q_it"] / 1e6, color=R, label="IT delivered (3 chillers)")
        ax[1].plot(d_.series["hour"], (d_.series["Q_ch"]) / 1e6, color=K, ls="--", label="chiller cooling")
ax[0].axhline(27, color=R, ls=":", lw=0.6)
ax[0].set(ylabel=r"server inlet [°C]", xlim=(0, 10)); ax[0].set_xlabel("time of day [h]"); room(ax[0], 0.2)
f.legend(*ax[0].get_legend_handles_labels(), loc="lower center", ncol=3, fontsize=6.8, bbox_to_anchor=(0.5, 0.0))
panel(ax[0], "(a)  hall temperature, 00:00–10:00")
ax[1].set(ylabel="power [MW]", xlim=(0, 10)); ax[1].set_xlabel("time of day [h]"); room(ax[1], 0.45)
ax[1].legend(loc="upper left", bbox_to_anchor=(0, 0.87), fontsize=6.8)
panel(ax[1], "(b)  GPUs throttle when cooling runs short")
f.tight_layout(pad=0.4, w_pad=1.5, rect=(0, 0.1, 1, 1))
save(f, "Fig8_outage")
N.update(I6={k: {q: v[q] for q in ("T_inlet_max", "minutes_over_limit", "compute_lost_pct", "compute_lost_MWh", "pue")} for k, v in I6.items()})

# ============================================================ I7 storage + tariffs
I7 = {}
for tf in ("retail", "wholesale"):
    I7[tf] = {}
    for cap in (0, 10, 20, 40, 60):
        kw = dict(tariff=tf)
        if cap:
            kw.update(tank=True, tank_MWh=float(cap), tank_rate_MW=5.0)
            if tf == "wholesale":
                kw.update(price_charge=20.0, price_discharge=50.0)
        I7[tf][cap] = day(**kw).metrics["cost_cooling"]
d_t = day(tank=True, tank_MWh=40.0, tank_rate_MW=5.0)
d_0 = day()
f, ax = plt.subplots(1, 2, figsize=(6.5, 2.6))
a = ax[0]
a.axvspan(16, 21, color=(0.93, 0.93, 0.93), lw=0)
a.text(18.5, 1.42, "on-peak", ha="center", fontsize=7, color=GY)
a.plot(d_0.series["hour"], d_0.series["W_comp"] / 1e6, color=GY, ls="--", label="compressors, no tank")
a.plot(d_t.series["hour"], d_t.series["W_comp"] / 1e6, color=K, label="compressors, with tank")
a.set_ylabel("compressor power [MW]"); a.set_ylim(0, 1.6); hours(a)
a2 = a.twinx(); a2.plot(d_t.series["hour"], 100 * d_t.series["soc"], color=B)
a2.set_ylabel("tank charge [%]", color=B); a2.tick_params(axis="y", colors=B); a2.set_ylim(0, 160)
a.legend(loc="upper left", bbox_to_anchor=(0, 0.88), fontsize=6.8)
panel(a, "(a)  40 MWh tank, retail price")
a = ax[1]
caps = [0, 10, 20, 40, 60]
for tf, col in (("retail", K), ("wholesale", R)):
    a.plot(caps, [100 * (1 - I7[tf][c] / I7[tf][0]) for c in caps], "o-", ms=3, color=col,
           label="retail TOU" if tf == "retail" else "wholesale (CAISO shape)")
a.set(xlabel="tank capacity [MWh of cooling]", ylabel="cooling-bill saving [%]"); room(a, 0.4)
a.legend(loc="upper left", bbox_to_anchor=(0, 0.86))
panel(a, "(b)  value of storage")
f.tight_layout(pad=0.4, w_pad=1.5)
save(f, "Fig9_storage")
N.update(I7=I7, I7_vol40=PlantSettings(tank_MWh=40.0).tank_volume_m3,
         I7_soc=float(d_t.series["soc"][0]), I7_eb=d_t.metrics["energy_balance_err_pct"])

# ============================================================ I8 liquid cooling
I8 = {}
f, ax = plt.subplots(1, 2, figsize=(6.5, 2.6))
sws = np.arange(14, 36.5, 2.0)
for clim, col in (("la_typical", K), ("phoenix", R), ("chicago_s", B)):
    res = [day(climate=clim, rack_cooling="liquid", T_chws_C=float(t), dT_chw=8.0).metrics for t in sws]
    I8[clim] = {float(t): r for t, r in zip(sws, res)}
    ax[0].plot(sws, [r["E_comp_MWh"] for r in res], "o-", ms=3, color=col, label=CLIMATES[clim].label)
    ax[1].plot(sws, [r["pue"] for r in res], "o-", ms=3, color=col, label=CLIMATES[clim].label)
ax[0].set(xlabel=r"facility water supply [°C]", ylabel="compressor electricity [MWh/day]"); room(ax[0], 0.35)
ax[0].legend(loc="upper right", bbox_to_anchor=(1, 0.86))
panel(ax[0], "(a)  direct-to-chip liquid cooling")
air = {c: day(climate=c).metrics["pue"] for c in ("la_typical", "phoenix", "chicago_s")}
ax[1].set(xlabel=r"facility water supply [°C]", ylabel="daily PUE"); room(ax[1], 0.35)
panel(ax[1], "(b)  PUE (air-cooled baseline 1.20–1.24)")
f.tight_layout(pad=0.4, w_pad=1.5)
save(f, "Fig10_liquid")
def first_zero(clim):
    for t, r in I8[clim].items():
        if r["E_comp_MWh"] < 0.01:
            return t
    return float("nan")
N.update(I8_air=air, I8_zero={c: first_zero(c) for c in I8},
         I8_pue30={c: I8[c][30.0]["pue"] for c in I8}, I8_wue30={c: I8[c][30.0]["wue_L_per_kWh"] for c in I8})

json.dump(N, open("report/numbers.json", "w"), indent=1, default=float)
print("done")
