"""
day.py - 24-hour operation of the data hall and its cooling plant.

Two quantities change with time and are integrated step by step:

  Data-hall temperature (lumped energy balance of air, racks and structure)
      C_hall dT/dt = Q_IT + Q_fans - Q_cooling
  Storage-tank state of charge (stratified chilled-water tank)
      E_tank dx/dt = Q_charge - Q_discharge

Everything else (free cooling, chillers, pumps, fans) is a steady-flow device
solved at each instant by plant.plant_step(). Time integration: forward Euler
with a fixed step (default 30 s); validation.py checks step convergence.
"""

from dataclasses import dataclass, replace
import numpy as np

from .plant import PlantSettings, plant_step, C2K
from .heat_rejection import wet_bulb, relative_humidity, RHO_WATER, CP_WATER
from .scenarios import CLIMATES, WORKLOADS, TARIFFS, disturbance


@dataclass
class DayResult:
    settings: PlantSettings
    climate_key: str
    workload_key: str
    t_h: np.ndarray          # hours
    series: dict             # every quantity vs time
    metrics: dict            # daily totals and scores


def tank_command(s: PlantSettings, price):
    """Operator rule: charge when power is cheap, discharge when it is dear."""
    if not s.tank:
        return 0.0
    if price <= s.price_charge:
        return 1.0
    if price >= s.price_discharge:
        return -1.0
    return 0.0


def throttle_factor(s: PlantSettings, T_inlet):
    """GPUs protect themselves: above the throttle temperature they cut power
    by 8 % per kelvin, down to a floor of 40 % of demand."""
    excess = T_inlet - (s.T_throttle + C2K)
    return 1.0 if excess <= 0 else max(0.4, 1.0 - 0.08 * excess)


def simulate_day(s: PlantSettings, climate_key="la_typical", workload_key="inference", dt=30.0,
                 tariff_key="retail", events=()):
    """Simulate one day with one set of settings. With a storage tank in cyclic
    mode, the day is repeated with the end-of-day charge as the next start until
    the tank finishes the day where it began (a repeating daily cycle), so no
    'free' stored cooling is borrowed from or left to another day."""
    res = simulate_plan([s], [], climate_key, workload_key, dt, tariff_key, events)
    if s.tank and s.tank_cyclic and not events:
        for _ in range(6):
            end = float(res.series["soc"][-1])
            if abs(end - res.series["soc"][0]) < 0.002:
                break
            res = simulate_plan([replace(s, tank_soc0=end)], [], climate_key, workload_key, dt, tariff_key, events)
            res.settings = s
    return res


def simulate_plan(plans, breaks, climate_key, workload_key, dt=30.0, tariff_key="retail", events=(),
                  until=24.0):
    """Simulate a day in segments. plans[i] is the PlantSettings used from
    breaks[i-1] to breaks[i] (hours); the hall temperature and the tank carry
    over continuously from one segment to the next. Used by the work orders,
    where the operator changes settings when an event happens.
    `until` stops the day early (to pause at an event)."""
    clim, work, tariff = CLIMATES[climate_key], WORKLOADS[workload_key], TARIFFS[tariff_key]
    edges = [0.0] + list(breaks) + [24.0]
    s0 = plans[0]
    n = int(round(min(until, 24.0) * 3600 / dt))
    T_in = s0.T_chws + s0.approach_rack          # hall starts settled at its target
    soc = s0.tank_soc0 if s0.tank else 0.0
    rows, wb_cache = [], {}
    for k in range(n + 1):
        t = k * dt
        hour = t / 3600.0
        seg = max(i for i in range(len(plans)) if hour >= edges[i] - 1e-9)
        s = plans[min(seg, len(plans) - 1)]
        C_hall = s.hall_capacitance_MJ_K * 1e6
        M_tank = s.tank_mass
        T_target = s.T_chws + s.approach_rack
        d = disturbance(events, hour)
        T_db = clim.dry_bulb(hour) + d["dT_db"]
        T_dp = min(clim.dew_point(hour) + d["dT_dew"], T_db)
        key = (round(T_db, 1), round(T_dp, 1))
        if key not in wb_cache:
            wb_cache[key] = (wet_bulb(T_db, T_dp, clim.P_atm), relative_humidity(T_db, T_dp, clim.P_atm))
        T_wb, rh = wb_cache[key]
        price = tariff.price(hour) * d["price_mult"]
        n_avail = max(0, s.n_chillers - d["n_lost"])

        Q_it_req = (work.it_load(hour) + d["load_add"]) * 1e6
        thr = throttle_factor(s, T_in)
        Q_it = Q_it_req * thr
        P_crah = s.rack_aux_frac * Q_it            # fan/pump work ends up as heat in the hall
        Q_heat = Q_it + P_crah

        # Cooling demand: remove the present heat and pull the hall back to target
        Q_demand = max(0.0, Q_heat + C_hall * (T_in - T_target) / s.control_time_s)
        cmd = tank_command(s, price)
        E_tank = s.tank_MWh * 3.6e9
        lim = (soc * E_tank / dt, (1.0 - soc) * E_tank / dt) if s.tank else None
        p = plant_step(s, Q_demand, T_db, T_wb, cmd, soc, T_dp, clim.P_atm, n_avail, lim)

        P_aux = p["P_chw"] + p["P_cw"] + p["P_fans"] + P_crah
        P_cool = p["W_comp"] + P_aux
        P_over = s.overhead_frac * Q_it
        P_total = Q_it + P_cool + P_over
        cyc = p["cycle"]
        on = p["W_comp"] > 0
        rows.append(dict(
            hour=hour, T_db=T_db - C2K, T_wb=T_wb - C2K, T_dew=T_dp - C2K, rh=rh, price=price,
            Q_it_req=Q_it_req, Q_it=Q_it, throttle=thr, T_inlet=T_in - C2K, soc=soc,
            m_cold=soc * M_tank if s.tank else 0.0, T_limit=s.T_limit_C,
            Q_demand=Q_demand, Q_loop=p["Q_loop"], Q_delivered=p["Q_delivered"], Q_fc=p["Q_fc"], Q_ch=p["Q_ch"],
            Q_dis=p["Q_dis"], Q_chg=p["Q_chg"], shortfall=p["shortfall"],
            n_on=p["n_on"], n_avail=n_avail, plr=p["plr"],
            cop=(p["Q_ch"] + p["Q_chg"]) / p["W_comp"] if on else np.nan,
            cop_cycle=cyc.cop if on else np.nan, cop_carnot=cyc.cop_carnot,
            eta=p["eta"] if on else np.nan, x_map=p["x"] if on else np.nan,
            T_evap=cyc.T_evap - C2K, T_cond=cyc.T_cond - C2K,
            approach_evap=p["approach_evap"], approach_cond=p["approach_cond"], approach_rej=p["approach_rej"],
            T_comp_out=cyc.T[1] - C2K, P_evap=cyc.P_evap, P_cond=cyc.P_cond,
            h1=cyc.h[0], h2=cyc.h[1], h3=cyc.h[2], h4=cyc.h[3],
            s1=cyc.s[0], s2=cyc.s[1], s3=cyc.s[2], s4=cyc.s[3], m_ref=p["m_ref"],
            W_comp=p["W_comp"], W_shaft=p["W_shaft"], W_fixed=p["W_fixed"], Q_cond=p["Q_cond"],
            P_chw=p["P_chw"], P_cw=p["P_cw"], P_chw_shaft=p["P_chw_shaft"], P_cw_shaft=p["P_cw_shaft"],
            P_fans=p["P_fans"], m_chw=p["m_chw"], m_cw=p["m_cw"],
            P_crah=P_crah, P_cool=P_cool, P_over=P_over, P_total=P_total,
            Q_rej=p["Q_rej"], water=p["water"], evaporation=p["evaporation"], drift=p["drift"],
            blowdown=p["blowdown"], f_fc=p["f_fc"], T_sink=p["T_sink"] - C2K,
            pue=P_total / Q_it, cost_rate=P_total / 1e6 * price,
        ))
        if k == n:
            break
        # Forward Euler update of the two transient control volumes
        T_in += dt * (Q_heat - p["Q_delivered"]) / C_hall                       # energy balance, hall
        if s.tank:                                                              # mass balance, cold layer
            m_dot = (p["Q_chg"] - p["Q_dis"]) / (CP_WATER * s.dT_chw)
            soc = min(1.0, max(0.0, soc + dt * m_dot / M_tank))

    series = {k: np.array([r[k] for r in rows]) for k in rows[0]}
    res = DayResult(s0, climate_key, workload_key, series["hour"], series,
                    day_metrics(s0, series, dt, s0.hall_capacitance_MJ_K * 1e6, s0.tank_MWh * 3.6e9))
    res.tariff_key = tariff_key
    res.events = tuple(events)
    res.plans = list(plans)
    res.breaks = list(breaks)
    return res


def _integral(y, dt):
    """Energy over the day (J) from a power series (W), trapezoidal rule."""
    return float(np.sum(0.5 * (y[1:] + y[:-1])) * dt)


def day_metrics(s, x, dt, C_hall, E_tank):
    J2MWh = 1 / 3.6e9
    E_it = _integral(x["Q_it"], dt)
    E_it_req = _integral(x["Q_it_req"], dt)
    E_comp = _integral(x["W_comp"], dt)
    E_aux = _integral(x["P_chw"] + x["P_cw"] + x["P_fans"] + x["P_crah"], dt)
    E_cool = E_comp + E_aux
    E_total = _integral(x["P_total"], dt)
    E_rej = _integral(x["Q_rej"], dt)
    E_ch = _integral(x["Q_ch"] + x["Q_chg"], dt)
    cost = float(np.sum(0.5 * (x["cost_rate"][1:] + x["cost_rate"][:-1])) * dt / 3600)
    cool_cost = float(np.sum(0.5 * ((x["P_cool"] / 1e6 * x["price"])[1:] + (x["P_cool"] / 1e6 * x["price"])[:-1])) * dt / 3600)
    water_m3 = _integral(x["water"], dt) / RHO_WATER

    # --- Conservation checks --------------------------------------------------
    # Energy, whole plant: everything that enters the water loops must leave to
    # the outdoors, except what is stored in the hall or the tank.
    #   in  : IT heat, hall fan heat, compressor shaft work, both pumps' shaft work
    #   out : heat rejected by the tower / dry cooler
    # (Motor, drive and tower-fan losses are dissipated to the plant-room air.)
    dE_hall = C_hall * (x["T_inlet"][-1] - x["T_inlet"][0])
    dE_tank = E_tank * (x["soc"][-1] - x["soc"][0]) if s.tank else 0.0
    heat_in = (E_it + _integral(x["P_crah"], dt) + _integral(x["W_shaft"], dt)
               + _integral(x["P_chw_shaft"], dt) + _integral(x["P_cw_shaft"], dt))
    balance_err = abs((heat_in - dE_hall + dE_tank) - E_rej) / heat_in * 100
    # Mass, storage tank: change in cold-water mass = integral of net charging flow
    m_net = _integral((x["Q_chg"] - x["Q_dis"]) / (CP_WATER * s.dT_chw), dt)
    dm_cold = x["m_cold"][-1] - x["m_cold"][0]
    tank_mass_err = abs(m_net - dm_cold) / s.tank_mass * 100 if s.tank else 0.0
    # Mass, cooling tower: make-up = evaporation + drift + blowdown
    mk, ev = _integral(x["water"], dt), _integral(x["evaporation"], dt)
    dr, bl = _integral(x["drift"], dt), _integral(x["blowdown"], dt)
    tower_mass_err = abs(mk - (ev + dr + bl)) / mk * 100 if mk > 0 else 0.0

    above = x["T_inlet"] > x["T_limit"] + 1e-9
    valid = ~np.isnan(x["cop"])
    return dict(
        E_it_MWh=E_it * J2MWh,
        E_cool_MWh=E_cool * J2MWh,
        E_comp_MWh=E_comp * J2MWh,
        E_aux_MWh=E_aux * J2MWh,
        E_total_MWh=E_total * J2MWh,
        pue=E_total / E_it,
        pue_peak=float(x["pue"].max()),
        cop_mean=float(E_ch / E_comp) if E_comp > 0 else float("nan"),
        T_inlet_max=float(x["T_inlet"].max()),
        minutes_over_limit=float(above.sum() * dt / 60),
        compute_lost_MWh=(E_it_req - E_it) * J2MWh,
        compute_lost_pct=100 * (E_it_req - E_it) / E_it_req,
        cost_total=cost,
        cost_cooling=cool_cost,
        water_m3=water_m3,
        wue_L_per_kWh=water_m3 * 1000 / (E_it / 3.6e6),
        free_cooling_hours=float(np.sum(x["f_fc"]) * dt / 3600),
        chillers_max=int(x["n_on"].max()),
        shortfall_minutes=float((x["shortfall"] > 1).sum() * dt / 60),
        cop_carnot_violations=int(np.sum(x["cop_cycle"][valid] >= x["cop_carnot"][valid])),
        energy_balance_err_pct=float(balance_err),
        tank_mass_err_pct=float(tank_mass_err), tower_mass_err_pct=float(tower_mass_err),
        evaporation_m3=ev / RHO_WATER, drift_m3=dr / RHO_WATER, blowdown_m3=bl / RHO_WATER,
        E_pump_heat_MWh=(_integral(x["P_chw_shaft"], dt) + _integral(x["P_cw_shaft"], dt)) * J2MWh,
        E_rej_MWh=E_rej * J2MWh, E_shaft_MWh=_integral(x["W_shaft"], dt) * J2MWh,
        margin_T=float(np.min(x["T_limit"] - x["T_inlet"])),
        plr_mean=float(np.nanmean(np.where(x["n_on"] > 0, x["plr"], np.nan))) if (x["n_on"] > 0).any() else float("nan"),
        eff2_mean=float(np.nanmean(x["cop_cycle"] / x["cop_carnot"])) if valid.any() else float("nan"),
    )
