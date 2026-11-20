"""Physics checks. Run with:  pytest -q"""
import math
import pytest

from coldfront import checks
from coldfront.chiller import hx_approach, compressor_efficiency, operate, ETA_PEAK, CHOKE_EXP, FIXED_LOSS
from coldfront.plant import PlantSettings, plant_step
from coldfront.day import simulate_day, simulate_plan
from coldfront.scenarios import Event
from coldfront import tower

K = 273.15


def test_textbook_example_matches_within_1pct():
    rows, _ = checks.textbook_benchmark()
    for r in rows:
        assert r["error_pct"] < 1.0, r


def test_first_and_second_law_on_operating_grid():
    out = checks.cycle_law_checks()
    assert out["worst_first_law_err"] < 1e-12
    assert out["violations"] == []


# ---- chiller as a machine --------------------------------------------------
def test_heat_exchanger_approach_shrinks_at_part_load():
    assert hx_approach(6.0, 1.0, 6.0) == pytest.approx(1.0)
    assert hx_approach(6.0, 0.5, 6.0) < 0.3


def test_compressor_map_peak_and_choke():
    assert compressor_efficiency(0.6) == pytest.approx(ETA_PEAK)
    assert compressor_efficiency(1.0) == pytest.approx(ETA_PEAK)
    assert compressor_efficiency(1.2) < 0.6 * ETA_PEAK + 0.2


def test_chiller_meets_ashrae_901_path_b():
    v = checks.map_validation()
    full, ip = v["rows"][0], v["rows"][1]
    assert full["model"] <= 0.585 and ip["model"] <= 0.380
    assert ip["model"] >= checks.BEST_IN_CLASS_IPLV      # not better than the best machine sold


def test_chiller_matches_published_vsd_points_within_15pct():
    for plr, ecwt, kw in checks.PUBLISHED_VSD:
        assert abs(checks.rate(44.0, ecwt, plr)["kw_per_ton"] / kw - 1) < 0.15


def test_calibration_is_reproducible():
    c = checks.calibrate_compressor_map()
    assert c["eta_peak"] == pytest.approx(ETA_PEAK, abs=0.005)
    assert c["choke_exp"] == pytest.approx(CHOKE_EXP, abs=0.05)
    assert c["fixed_loss"] == pytest.approx(FIXED_LOSS, abs=0.003)


def test_second_law_efficiency_falls_at_low_lift_full_load():
    hi = operate("R134a", 6.67 + K, 5.56, 29.4 + K, 5.2, 1.0)
    lo = operate("R134a", 6.67 + K, 5.56, 15.0 + K, 5.2, 1.0)
    e = lambda o: o["cycle"].cop / o["cycle"].cop_carnot
    assert e(lo) < e(hi)


def test_exergy_closure_and_entropy_generation():
    for plr in (0.3, 0.7, 1.0):
        for ecw in (15.0, 25.0, 35.0):
            a = checks.exergy_audit(T_ecw_C=ecw, plr=plr)
            assert a["closure"] < 1e-9
            assert min(a["S_gen"].values()) > 0
            assert 0 < a["second_law_eff"] < 1


# ---- plant and day ---------------------------------------------------------
def test_step_audit_closes():
    rows, _ = checks.step_audit()
    for r in rows:
        assert r["rel_err"] < 1e-6, r


def test_tower_approach_and_water_balance():
    assert tower.yorkcalc_approach(25.6, 5.6) == pytest.approx(3.9, abs=0.2)     # design point 78 F wb, 85/95 F
    assert tower.yorkcalc_approach(5.0, 5.0) > tower.yorkcalc_approach(20.0, 5.0)
    w = tower.water_balance(10e6, 478.0, 308.15, 290.15, 101325.0, 5.0)
    assert w["makeup"] == pytest.approx(w["evaporation"] + w["drift"] + w["blowdown"])
    assert 0.5 < w["evaporation"] * 2.43e6 / 10e6 < 2.5


@pytest.mark.parametrize("climate", ["la_typical", "phoenix", "chicago_w", "chicago_s", "denver"])
def test_day_energy_balance_closes(climate):
    m = simulate_day(PlantSettings(), climate, "inference").metrics
    assert m["energy_balance_err_pct"] < 0.01
    assert m["tower_mass_err_pct"] < 1e-9
    assert m["cop_carnot_violations"] == 0


def test_energy_balance_can_fail():
    n = checks.negative_control()
    assert n["correct_err_pct"] < 0.01 < 0.5 < n["without_pump_heat_err_pct"]


def test_storage_tank_energy_and_mass_balance_close():
    s = PlantSettings(n_chillers=3, tank=True, tank_soc0=1.0)
    m = simulate_day(s, "la_typical", "training").metrics
    assert m["energy_balance_err_pct"] < 0.05
    assert m["tank_mass_err_pct"] < 0.05


def test_higher_setpoint_improves_cop():
    lo = simulate_day(PlantSettings(T_chws_C=7), "la_typical", "inference").metrics
    hi = simulate_day(PlantSettings(T_chws_C=14), "la_typical", "inference").metrics
    assert hi["cop_mean"] > lo["cop_mean"] and hi["pue"] < lo["pue"]


def test_timestep_converges():
    rows = checks.timestep_study(dts=(60, 30, 15))
    assert abs(rows[-1]["T_inlet_max"] - rows[-2]["T_inlet_max"]) < 0.1


def test_events_are_repeatable_and_state_is_continuous():
    ev = (Event(2.0, "trip", 1, 8.0), Event(12.0, "heat", 5.0, 18.0), Event(16.0, "price", 2.0, 20.0))
    a = simulate_plan([PlantSettings()], [], "la_typical", "training", events=ev)
    b = simulate_plan([PlantSettings(), PlantSettings(T_chws_C=14)], [2.0], "la_typical", "training", events=ev)
    c = simulate_plan([PlantSettings()], [], "la_typical", "training", events=ev)
    assert a.metrics["pue"] == c.metrics["pue"]                       # same inputs, same answer
    k = int(2 * 3600 / 30)
    assert a.series["T_inlet"][k] == pytest.approx(b.series["T_inlet"][k])   # state carried across the break
    assert a.series["n_avail"][k + 10] == 3 and a.series["price"][int(17 * 120)] > a.series["price"][int(15 * 120)]
    assert b.metrics["energy_balance_err_pct"] < 0.01


def test_overloaded_plant_stays_finite():
    """A badly undersized plant must overheat the hall, not crash the model:
    the chilled-water flow is capped, so pump heat cannot run away."""
    from coldfront.contracts import ORDERS, run_order
    import numpy as np
    from coldfront.plant import PlantSettings, MAX_FLOW
    for o in ORDERS:
        bad = dict(o.start, n_chillers=1, dT_chw=4.0, rejection="dry", eta_rated=0.6)
        bad.update(o.locks)
        day = run_order(o, [PlantSettings(**bad)] * (len(o.pauses) + 1), 24.0)
        m = np.asarray(day.series["m_chw"])
        assert np.all(np.isfinite(m))
        assert np.all(np.isfinite(day.series["T_inlet"]))
        s = day.settings if hasattr(day, "settings") and day.settings else PlantSettings(**bad)
        assert m.max() <= MAX_FLOW * s.Q_design / (4186.0 * 4.0) * 1.01
