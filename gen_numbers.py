"""gen_numbers.py - turns report/numbers.json into LaTeX macros (report/numbers.tex)."""
import json
N = json.load(open("report/numbers.json"))
L = []
def m(name, v, fmt="{:.2f}"):
    s = fmt.format(v) if not isinstance(v, str) else v
    if s.startswith("-"):
        s = "\\textminus{}" + s[1:]
    L.append(f"\\newcommand{{\\{name}}}{{{s}}}")
# baseline (LA hot design day)
m("Bpue", N["B_pue"], "{:.3f}"); m("Bcop", N["B_cop"], "{:.1f}"); m("Bcopmin", N["B_copmin"], "{:.1f}")
m("Bcopmax", N["B_copmax"], "{:.1f}"); m("Bcarmin", N["B_carmin"], "{:.1f}"); m("Beffii", 100 * N["B_eff2"], "{:.0f}")
m("BEcool", N["B_Ecool"], "{:.1f}"); m("BEcomp", N["B_Ecomp"], "{:.1f}"); m("BEit", N["B_Eit"], "{:.0f}")
m("Bcost", N["B_cost"], "{:,.0f}"); m("Bcosttot", N["B_costtot"], "{:,.0f}"); m("Bwater", N["B_water"], "{:.0f}")
m("Bwue", N["B_wue"], "{:.2f}"); m("Bcompshare", N["B_compshare"], "{:.0f}"); m("Bitmin", N["B_itmin"], "{:.1f}")
m("Bitmax", N["B_itmax"], "{:.1f}"); m("Bpuemin", N["B_puemin"], "{:.3f}"); m("Bpuemax", N["B_puemax"], "{:.3f}")
m("BTcmin", N["B_Tcondmin"], "{:.1f}"); m("BTcmax", N["B_Tcondmax"], "{:.1f}"); m("Bchmax", N["B_chmax"], "{:d}")
# cycle at 15:00
for k in ("Te", "Tc", "T2"):
    m("C" + k.replace("2", "two"), N["C_" + k], "{:.1f}")
for k in ("Pe", "Pc"):
    m("C" + k, N["C_" + k], "{:.0f}")
for k in ("h1", "h2", "h3", "qe", "w", "qc"):
    m("C" + k.replace("1", "one").replace("2", "two").replace("3", "three"), N["C_" + k], "{:.1f}")
m("Ccop", N["C_cop"], "{:.2f}"); m("Ccar", N["C_car"], "{:.2f}")
# validation
tb = N["V_tb"]
m("TBql", tb["Q_L_kW"]["model"], "{:.3f}"); m("TBw", tb["W_kW"]["model"], "{:.3f}"); m("TBqh", tb["Q_H_kW"]["model"], "{:.3f}")
m("TBcop", tb["COP"]["model"], "{:.3f}"); m("TBerr", max(r["error_pct"] for r in tb.values()), "{:.2f}")
m("Vahri", N["V_ahri"], "{:.3f}"); m("Vahricop", N["V_ahricop"], "{:.2f}"); m("Vahricar", N["V_ahricar"], "{:.2f}")
m("Vlawn", N["V_lawn"], "{:d}"); m("Vebtank", N["V_eb_tank"], "{:.3f}")
ts = N["TS"]
m("TSone", ts["120"], "{:.2f}"); m("TStwo", ts["60"], "{:.2f}"); m("TSthree", ts["30"], "{:.3f}"); m("TSfive", ts["7.5"], "{:.3f}")
te = N["TSerr"]
m("TEone", te["120"], "{:.1f}"); m("TEtwo", 1000 * te["60"], "{:.1f}"); m("TEthree", 1000 * te["30"], "{:.2f}")
m("TEfour", 1000 * te["15"], "{:.2f}"); m("TEfive", 1000 * te["7.5"], "{:.2f}"); m("TSorder", N["TS_order"], "{:.1f}")
# chiller machine model
c = N["CAL"]
m("CalEta", c["eta_peak"], "{:.3f}"); m("CalN", c["choke_exp"], "{:.2f}"); m("CalLoss", 100 * c["fixed_loss"], "{:.1f}"); m("CalRms", 100 * c["rms"], "{:.0f}")
mv = N["MV"]
m("MVfull", mv[0]["model"], "{:.3f}"); m("MViplv", mv[1]["model"], "{:.3f}"); m("MVbest", mv[2]["ref"], "{:.3f}")
m("MVhi", mv[3]["model"], "{:.2f}"); m("MVhidiff", abs(mv[3]["diff_pct"]), "{:.0f}"); m("MVlo", mv[4]["model"], "{:.3f}"); m("MVlodiff", abs(mv[4]["diff_pct"]), "{:.0f}")
m("MVsens", mv[5]["model"], "{:.1f}"); m("MVrefsens", N["ref_sens"], "{:.1f}"); m("MVheld", N["MV_held"], "{:.0f}")
m("MViplvcop", 3.51685 / mv[1]["model"], "{:.1f}"); m("MViplvmargin", abs(mv[1]["diff_pct"]), "{:.0f}")
for key, n in (("AHRI full load", "A"), ("design day", "D"), ("low lift, full load", "L")):
    e = N["EX"][key]
    m("Ex" + n + "eff", 100 * e["eff"], "{:.0f}"); m("Ex" + n + "comp", e["compressor"], "{:.0f}"); m("Ex" + n + "cond", e["condenser"], "{:.0f}")
    m("Ex" + n + "valve", e["valve"], "{:.0f}"); m("Ex" + n + "evap", e["evaporator"], "{:.0f}"); m("Ex" + n + "eta", e["eta"], "{:.2f}"); m("Ex" + n + "x", e["x"], "{:.2f}")
m("AudN", N["AUD_n"], "{:d}"); m("NegErr", N["NEG"]["without_pump_heat_err_pct"], "{:.1f}")
m("StThree", N["ST3"], "{:.1f}"); m("StFour", N["ST4"], "{:.1f}")
m("Beffcyc", 100 * N["B_eff2cyc"], "{:.0f}"); m("Bplr", 100 * N["B_plr"], "{:.0f}"); m("Bevap", N["B_evap"], "{:.0f}"); m("Bblow", N["B_blow"], "{:.0f}")
m("Bdrift", N["B_drift"], "{:.1f}"); m("Bpumpheat", N["B_pumpheat"], "{:.1f}"); m("Bevapratio", N["B_evapratio"], "{:.2f}")
m("Ceta", N["C_eta"], "{:.2f}"); m("Cplr", 100 * N["C_plr"], "{:.0f}"); m("Cnon", N["C_non"], "{:d}"); m("Ccope", N["C_cope"], "{:.1f}")
m("Cae", N["C_ae"], "{:.1f}"); m("Cac", N["C_ac"], "{:.1f}"); m("Carej", N["C_arej"], "{:.1f}"); m("Cmref", N["C_mref"], "{:.0f}")
m("Vahrieta", N["V_ahri_eta"], "{:.2f}")
W = N["W"]
for k in ("P_evap_kPa", "P_cond_kPa"):
    m("W" + k.split("_")[1], W[k], "{:.0f}")
for k in ("h1", "s1", "h2s", "h2", "h3", "h4", "q_evap", "w_comp", "q_cond"):
    name = "W" + k.replace("_", "").replace("1", "one").replace("2", "two").replace("3", "three").replace("4", "four")
    m(name, W[k], "{:.4f}" if k == "s1" else "{:.2f}")
m("WTtwo", W["T2_C"], "{:.1f}"); m("Wcop", W["cop"], "{:.2f}"); m("Wcar", W["cop_carnot"], "{:.2f}")
# I1
for k in ("la7", "la19", "ph7", "ph19"):
    m("Ia" + k.replace("7", "seven").replace("19", "nineteen") + "cop", N[f"I1_{k}_cop"], "{:.1f}")
    m("Ia" + k.replace("7", "seven").replace("19", "nineteen") + "pue", N[f"I1_{k}_pue"], "{:.3f}")
m("Iafc", N["I1_la19_fc"], "{:.1f}"); m("Iacostseven", N["I1_la7_cost"], "{:,.0f}"); m("Iacostnineteen", N["I1_la19_cost"], "{:,.0f}")
m("Iaslope", N["I1_slope"], "{:.0f}")
m("Iasave", 100 * (1 - N["I1_la19_cost"] / N["I1_la7_cost"]), "{:.0f}")
# I2/I3
I2 = N["I2"]
names = {"la_typical": "LAt", "la_hot": "LAh", "phoenix": "PHX", "chicago_s": "CHIs", "chicago_w": "CHIw", "denver": "DEN"}
for c, n in names.items():
    m("Pt" + n, I2[c]["tower"]["pue"], "{:.3f}"); m("Pd" + n, I2[c]["dry"]["pue"], "{:.3f}")
    m("Wt" + n, I2[c]["tower"]["wue_L_per_kWh"], "{:.2f}")
m("PHXdrypct", 100 * (I2["phoenix"]["dry"]["pue"] - I2["phoenix"]["tower"]["pue"]) / (I2["phoenix"]["tower"]["pue"] - 1), "{:.0f}")
m("PHXwater", I2["phoenix"]["tower"]["water_m3"], "{:.0f}")
m("PHXevapratio", I2["phoenix"]["tower"]["evaporation_m3"] * 998 * 2.43e6 / (I2["phoenix"]["tower"]["E_rej_MWh"] * 3.6e9), "{:.2f}")
m("CHIwfc", I2["chicago_w"]["tower"]["free_cooling_hours"], "{:.0f}")
# I4/I5
I4 = N["I4"]
for f_, n in (("R134a", "A"), ("R1234ze(E)", "Z"), ("R717", "N"), ("R290", "P")):
    m("Rk" + n, I4[f_]["kw_ton"], "{:.3f}"); m("Rpe" + n, I4[f_]["P_e"], "{:.0f}"); m("Rpc" + n, I4[f_]["P_c"], "{:.0f}")
    m("Rt" + n, I4[f_]["T2"], "{:.0f}"); m("Rpue" + n, I4[f_]["pue"], "{:.3f}")
m("Esixtwo", N["I5_ph62"], "{:.1f}"); m("Eninety", N["I5_ph90"], "{:.1f}"); m("Ecut", N["I5_cut"], "{:.0f}")
# I6
I6 = N["I6"]
m("OutTmax", I6["3 chillers"]["T_inlet_max"], "{:.1f}"); m("OutMin", I6["3 chillers"]["minutes_over_limit"], "{:.0f}")
m("OutLost", I6["3 chillers"]["compute_lost_MWh"], "{:.1f}"); m("OutLostpct", I6["3 chillers"]["compute_lost_pct"], "{:.1f}")
m("OutPriceMin", I6["3 chillers + price-driven storage"]["minutes_over_limit"], "{:.0f}")
m("OutPriceLost", I6["3 chillers + price-driven storage"]["compute_lost_MWh"], "{:.1f}")
m("OutPricePct", I6["3 chillers + price-driven storage"]["compute_lost_pct"], "{:.1f}")
m("OutWarmPue", I6["3 chillers, 17 °C water"]["pue"], "{:.3f}")
# I7
I7 = N["I7"]
m("StR", I7["retail"]["0"], "{:,.0f}"); m("StRforty", I7["retail"]["40"], "{:,.0f}")
m("StRpct", 100 * (1 - I7["retail"]["40"] / I7["retail"]["0"]), "{:.1f}")
m("StWpct", 100 * (1 - I7["wholesale"]["40"] / I7["wholesale"]["0"]), "{:.1f}")
m("StW", I7["wholesale"]["0"], "{:,.0f}"); m("StWforty", I7["wholesale"]["40"], "{:,.0f}")
m("StVol", N["I7_vol40"], "{:,.0f}"); m("StSoc", 100 * N["I7_soc"], "{:.0f}"); m("Steb", N["I7_eb"], "{:.3f}")
# I8
z = N["I8_zero"]
m("LqLA", z["la_typical"], "{:.0f}"); m("LqPHX", z["phoenix"], "{:.0f}"); m("LqCHI", z["chicago_s"], "{:.0f}")
m("Lqpue", N["I8_pue30"]["phoenix"], "{:.3f}"); m("Lqwue", N["I8_wue30"]["phoenix"], "{:.2f}")
m("LqairPHX", N["I8_air"]["phoenix"], "{:.3f}")
m("LqcutPHX", 100 * (N["I8_air"]["phoenix"] - N["I8_pue30"]["phoenix"]) / (N["I8_air"]["phoenix"] - 1), "{:.0f}")
open("report/numbers.tex", "w").write("\n".join(L) + "\n")
print(len(L), "macros")
