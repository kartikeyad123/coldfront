"""
plant.py - The chilled-water plant at one instant (all steady-flow devices).

Heat path:  servers -> air -> cooling coils (CRAH) -> chilled water loop
            -> [free-cooling heat exchanger] -> chillers' evaporators
            -> refrigeration cycle -> condensers -> condenser water
            -> cooling tower or dry cooler -> outdoors

Given how much heat the chilled-water loop must remove right now, this module
works out how the load is shared between free cooling, the storage tank and
the chillers, solves the refrigeration cycle, and adds up every electrical
load (compressors, pumps, fans), the heat rejected and the water evaporated.
"""

import math
from dataclasses import dataclass, field

from . import chiller as ch_mod
from .chiller import operate, MIN_PLR, ETA_PEAK
from .heat_rejection import (CP_WATER, RHO_WATER, REJECTION, free_cooling_fraction)
from . import tower

C2K = 273.15

# Every device, and whether it is solved as steady-state steady-flow (SSSF) or
# as a transient control volume with a storage term (used by the app and report).
DEVICES = {
    "compressor":  ("SSSF", "w = h2 - h1, adiabatic, isentropic efficiency from the compressor map"),
    "condenser":   ("SSSF", "q_H = h2 - h3, heat to condenser water, fixed UA"),
    "valve":       ("SSSF", "h4 = h3, throttling"),
    "evaporator":  ("SSSF", "q_L = h1 - h4, heat from chilled water, fixed UA"),
    "pumps":       ("SSSF", "W = m dP / (rho eta); the work ends up as heat in the water"),
    "free-cooling exchanger": ("SSSF", "Q = m cp dT, tower water pre-cools the return water"),
    "cooling tower / dry cooler": ("SSSF", "Q_rej = m cp dT; water: make-up = evaporation + drift + blowdown"),
    "data hall":   ("transient", "C dT/dt = Q_IT + W_fans - Q_cool  (energy stored in air, racks, structure)"),
    "storage tank": ("transient", "dm_cold/dt = m_charge - m_discharge  (mass of cold water stored)"),
}

@dataclass
class PlantSettings:
    """Everything the operator or designer can change (SI units unless noted)."""
    # chilled water and chillers
    fluid: str = "R134a"
    T_chws_C: float = 10.0          # chilled-water supply set point, C
    dT_chw: float = 6.0             # K, return minus supply temperature
    n_chillers: int = 4             # chillers available (online)
    chiller_cap_MW: float = 3.0     # cooling capacity of each chiller
    eta_rated: float = ETA_PEAK     # compressor peak isentropic efficiency (best-efficiency point)
    motor_eff: float = 0.96         # motor and variable-speed drive efficiency
    superheat: float = 1.0          # K at compressor inlet (flooded evaporator)
    subcool: float = 2.0            # K at condenser outlet
    n_installed: int = 4            # chillers the plant was built with (sizes towers and pumps)
    T_ecw_min_C: float = 13.0       # C, coldest condenser water the chillers accept (55 F)
    min_lift: float = 12.0          # K, smallest condensing-minus-evaporating lift allowed
    min_plr: float = MIN_PLR        # lowest stable load fraction of one chiller
    # heat rejection
    rejection: str = "tower"        # 'tower' or 'dry'
    dT_cw: float = 5.0              # K, condenser-water temperature rise
    free_cooling: bool = True       # waterside economizer
    hx_approach: float = 2.0        # K, free-cooling plate heat exchanger
    # data hall
    rack_cooling: str = "air"       # 'air' (CRAH coils) or 'liquid' (direct-to-chip cold plates)
    liquid_limit_C: float = 40.0    # coolant supply limit for liquid cooling (ASHRAE class W40)
    air_approach: float = 8.0       # K, server inlet air above chilled-water supply
    cdu_approach: float = 4.0       # K, coolant to the cold plates above facility water (CDU)
    hall_capacitance_MJ_K: float = 40.0   # thermal mass of air, racks and structure
    control_time_s: float = 300.0   # how fast the coils pull the hall back to target
    T_inlet_limit_C: float = 27.0   # ASHRAE recommended upper limit for server inlet air
    # auxiliaries
    dP_chw_kPa: float = 250.0       # chilled-water pump head at design flow
    dP_cw_kPa: float = 200.0        # condenser-water pump head at design flow
    pump_eff: float = 0.80          # pump hydraulic efficiency
    pump_motor_eff: float = 0.94    # pump motor and drive
    static_head_frac: float = 0.3   # part of the head that does not fall with flow (control set point)
    crah_fan_frac: float = 0.02     # air-handler fan power as a fraction of IT power (air cooling)
    liquid_aux_frac: float = 0.006  # CDU pumps + residual air fans, fraction of IT (liquid cooling)
    overhead_frac: float = 0.06     # UPS and electrical losses, lighting
    # chilled-water storage tank (optional transient system)
    tank: bool = False
    tank_MWh: float = 20.0          # thermal storage capacity (cooling)
    tank_rate_MW: float = 3.0       # max charge / discharge rate
    tank_soc0: float = 0.5          # first-guess state of charge at midnight (0-1)
    tank_cyclic: bool = True        # repeat the day until the tank ends where it started
    price_charge: float = 90.0      # $/MWh: charge at or below this price
    price_discharge: float = 140.0  # $/MWh: discharge at or above this price
    charge_plr_max: float = 0.90    # while charging, load the chillers no further than this (stay off the choke side)

    @property
    def approach_rack(self):
        """K between facility water supply and what the IT equipment receives."""
        return self.air_approach if self.rack_cooling == "air" else self.cdu_approach

    @property
    def T_limit_C(self):
        """Service limit on what the IT equipment receives: 27 C inlet air
        (ASHRAE recommended envelope) or the liquid-cooling class limit."""
        return self.T_inlet_limit_C if self.rack_cooling == "air" else self.liquid_limit_C

    @property
    def T_throttle(self):
        """GPUs start throttling 5 K above the service limit."""
        return self.T_limit_C + 5.0

    @property
    def rack_aux_frac(self):
        return self.crah_fan_frac if self.rack_cooling == "air" else self.liquid_aux_frac

    @property
    def T_chws(self):
        return self.T_chws_C + C2K

    @property
    def T_chwr(self):
        return self.T_chws + self.dT_chw

    @property
    def capacity(self):
        return self.n_chillers * self.chiller_cap_MW * 1e6

    @property
    def tank_volume_m3(self):
        return self.tank_MWh * 3.6e9 / (RHO_WATER * CP_WATER * self.dT_chw)


    @property
    def Q_design(self):
        """Installed cooling capacity (W): sizes pumps and towers."""
        return self.n_installed * self.chiller_cap_MW * 1e6

    @property
    def tank_mass(self):
        """kg of water in the storage tank."""
        return self.tank_MWh * 3.6e9 / (CP_WATER * self.dT_chw)


def pump(s: PlantSettings, m, m_design, dP_design_kPa):
    """Variable-speed pump (SSSF). Head = static part + friction part that
    falls with flow squared. Returns (electrical W, shaft W). The shaft work is
    dissipated by friction in the loop, so it ends up as heat in the water."""
    if m <= 0:
        return 0.0, 0.0
    dP = dP_design_kPa * 1e3 * (s.static_head_frac + (1 - s.static_head_frac) * (m / m_design) ** 2)
    shaft = m * dP / (RHO_WATER * s.pump_eff)
    return shaft / s.pump_motor_eff, shaft


def chiller_plant(s: PlantSettings, Q_chillers, T_ecw, n_avail=None):
    """Stage the chillers for a load (W): try every allowed number of running
    machines and keep the one that draws the least electricity."""
    cap = s.chiller_cap_MW * 1e6
    n_avail = s.n_chillers if n_avail is None else n_avail
    T_ecw = max(T_ecw, s.T_ecw_min_C + C2K)
    kw = dict(eta_peak=s.eta_rated, motor_eff=s.motor_eff, superheat=s.superheat, subcool=s.subcool,
              min_lift=s.min_lift)
    if Q_chillers <= 1.0 or n_avail <= 0:
        o = operate(s.fluid, s.T_chws, s.dT_chw, T_ecw, s.dT_cw, 1.0, **kw)
        return dict(n_on=0, plr=0.0, op=o, cycle=o["cycle"], W_comp=0.0, W_shaft=0.0, W_fixed=0.0,
                    m_ref=0.0, Q_cond=0.0, eta=o["eta"])
    best = None
    n_min = min(n_avail, max(1, math.ceil(Q_chillers / cap - 1e-9)))
    for n in range(n_min, n_avail + 1):
        plr = round(Q_chillers / (n * cap), 3)
        run = max(plr, s.min_plr)            # below the minimum load the machine cycles on and off
        o = operate(s.fluid, s.T_chws, s.dT_chw, T_ecw, s.dT_cw, run, **kw)
        W = Q_chillers * o["w_elec"]
        if best is None or W < best["W_comp"] - 1e-6:
            c = o["cycle"]
            m_ref = Q_chillers / c.q_evap
            best = dict(n_on=n, plr=plr, op=o, cycle=c, W_comp=W, W_shaft=m_ref * c.w_comp,
                        W_fixed=Q_chillers * o["w_fixed"], m_ref=m_ref, Q_cond=m_ref * c.q_cond, eta=o["eta"])
    return best


def plant_step(s: PlantSettings, Q_demand, T_db, T_wb, tank_cmd=0.0, tank_soc=0.0,
               T_dew=None, P_atm=101325.0, n_avail=None, tank_limits=None):
    """Solve the plant for one instant (every device here is SSSF).

    Q_demand : heat (W) the cooling coils take out of the hall right now
    tank_cmd : +1 charge the tank, -1 discharge it, 0 idle (operator rule)
    n_avail  : chillers available right now (None = all in the settings)
    """
    n_avail = s.n_chillers if n_avail is None else n_avail
    capacity = n_avail * s.chiller_cap_MW * 1e6
    m_chw_design = s.Q_design / (CP_WATER * 6.0)
    Q_rej_design = 1.17 * s.Q_design
    m_cw_design = Q_rej_design / (CP_WATER * 5.0)

    # 0. Heat-rejection equipment: how cold can it make the water?
    LG = 1.0     # tower cells are staged with the load, so each runs at its design water/air ratio
    if s.rejection == "tower":
        approach_rej = tower.yorkcalc_approach(T_wb - C2K, s.dT_cw, LG)
        T_sink = T_wb + approach_rej
    else:
        approach_rej = REJECTION["dry"]["approach"]
        T_sink = T_db + approach_rej

    # 1. Chilled-water pump heat joins the load (two passes settle the flow)
    rate = s.tank_rate_MW * 1e6 if s.tank else 0.0
    dis_max, chg_max = tank_limits if tank_limits else (rate, rate)   # what the tank can give / take this step
    P_chw = P_chw_shaft = 0.0
    for _ in range(4):
        Q_loop = Q_demand + P_chw_shaft
        # 2. Free cooling takes the first share (it is nearly free)
        f_fc = free_cooling_fraction(T_sink, s.T_chws, s.T_chwr, s.hx_approach) if s.free_cooling else 0.0
        Q_fc = f_fc * Q_loop
        remaining = Q_loop - Q_fc
        # 3. Storage tank: discharge on command, or as backup if the chillers are short
        Q_dis = Q_chg = 0.0
        if s.tank and tank_cmd < 0 and tank_soc > 0:
            Q_dis = min(rate, remaining, dis_max)
        elif s.tank and remaining > capacity and tank_soc > 0:
            Q_dis = min(rate, remaining - capacity, dis_max)
        remaining -= Q_dis
        # 4. Chillers carry the rest, up to their capacity
        Q_ch = min(remaining, capacity)
        shortfall = remaining - Q_ch
        if s.tank and tank_cmd > 0 and tank_soc < 1:
            Q_chg = max(0.0, min(rate, s.charge_plr_max * capacity - Q_ch, chg_max))
        m_chw = (Q_loop + Q_chg) / (CP_WATER * s.dT_chw)
        P_chw, P_chw_shaft = pump(s, m_chw, m_chw_design, s.dP_chw_kPa)
    Q_ch_total = Q_ch + Q_chg
    ch = chiller_plant(s, Q_ch_total, T_sink, n_avail)

    # 5. Condenser-water loop: condenser heat + free-cooling heat + its own pump heat
    Q_rej = ch["Q_cond"] + Q_fc
    P_cw = P_cw_shaft = 0.0
    for _ in range(5):
        m_cw = (Q_rej + P_cw_shaft) / (CP_WATER * s.dT_cw)
        P_cw, P_cw_shaft = pump(s, m_cw, m_cw_design, s.dP_cw_kPa)
    Q_rej += P_cw_shaft

    # 6. Fans and water
    if s.rejection == "tower":
        P_fans = REJECTION["tower"]["fan_kw_per_kw"] * Q_rej
        w = tower.water_balance(Q_rej, m_cw, T_db, T_dew if T_dew is not None else T_wb, P_atm, s.dT_cw, LG)
    else:
        P_fans = REJECTION["dry"]["fan_kw_per_kw"] * Q_rej
        w = dict(evaporation=0.0, drift=0.0, blowdown=0.0, makeup=0.0)

    o = ch["op"]
    return dict(
        T_sink=T_sink, approach_rej=approach_rej, LG=LG, f_fc=f_fc, Q_fc=Q_fc, Q_dis=Q_dis, Q_chg=Q_chg,
        Q_ch=Q_ch, Q_loop=Q_loop, Q_delivered=Q_demand - shortfall, shortfall=shortfall,
        n_on=ch["n_on"], n_avail=n_avail, plr=ch["plr"], eta=ch["eta"], cycle=ch["cycle"], x=o["x"],
        approach_evap=o["approach_evap"], approach_cond=o["approach_cond"],
        m_ref=ch["m_ref"], W_comp=ch["W_comp"], W_shaft=ch["W_shaft"], W_fixed=ch["W_fixed"],
        Q_cond=ch["Q_cond"], Q_rej=Q_rej,
        m_chw=m_chw, m_cw=m_cw, P_chw=P_chw, P_cw=P_cw, P_chw_shaft=P_chw_shaft, P_cw_shaft=P_cw_shaft,
        P_fans=P_fans, water=w["makeup"], evaporation=w["evaporation"], drift=w["drift"], blowdown=w["blowdown"],
    )
