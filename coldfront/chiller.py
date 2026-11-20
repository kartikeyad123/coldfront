"""
chiller.py - Vapor-compression refrigeration cycle (the chiller).

State points (standard vapor-compression cycle):
  1  compressor inlet   : superheated vapor at the evaporating pressure
  2  compressor outlet  : from the isentropic efficiency
  3  condenser outlet   : subcooled liquid at the condensing pressure
  4  evaporator inlet   : after the expansion valve, h4 = h3 (throttling)

Each component is a steady-flow device with q - w = h_out - h_in.
Refrigerant properties come from CoolProp. Units: SI (Pa, K, J/kg, J/(kg K)).
"""

from dataclasses import dataclass
from functools import lru_cache
import math
import CoolProp.CoolProp as CP

REFRIGERANTS = {
    "R134a": "R-134a (common today)",
    "R1234ze(E)": "R-1234ze(E) (low-GWP replacement)",
    "R717": "R-717 ammonia (industrial, natural)",
    "R290": "R-290 propane (natural)",
}

_STATES = {}


def _state(fluid):
    """Cached CoolProp AbstractState (much faster than PropsSI)."""
    if fluid not in _STATES:
        _STATES[fluid] = CP.AbstractState("HEOS", fluid)
    return _STATES[fluid]


@dataclass(frozen=True)
class CycleResult:
    fluid: str
    T_evap: float      # K, saturated evaporating temperature
    T_cond: float      # K, saturated condensing temperature
    P_evap: float      # Pa
    P_cond: float      # Pa
    h: tuple           # J/kg, (h1, h2, h3, h4)
    s: tuple           # J/(kg K), (s1, s2, s3, s4)
    T: tuple           # K, (T1, T2, T3, T4)
    q_evap: float      # J/kg, refrigeration effect  h1 - h4
    w_comp: float      # J/kg, compressor work       h2 - h1
    q_cond: float      # J/kg, heat rejected         h2 - h3
    cop: float         # q_evap / w_comp
    cop_carnot: float  # T_evap / (T_cond - T_evap)
    h2s: float = 0.0   # J/kg, compressor outlet enthalpy if isentropic
    v1: float = 0.0    # m^3/kg, specific volume at the compressor inlet

    @property
    def second_law_eff(self):
        return self.cop / self.cop_carnot


def solve_cycle(fluid, T_evap, T_cond, eta_s, superheat=5.0, subcool=3.0):
    """Solve one refrigeration cycle per unit mass of refrigerant.
    Rounds the inputs slightly so repeated calls during a day simulation
    hit the cache (0.01 K and 0.001 efficiency resolution)."""
    return _solve_cycle(fluid, round(T_evap, 2), round(T_cond, 2), round(eta_s, 3),
                        round(superheat, 2), round(subcool, 2))


@lru_cache(maxsize=200_000)
def _solve_cycle(fluid, T_evap, T_cond, eta_s, superheat, subcool):
    st = _state(fluid)
    # Saturation pressures
    st.update(CP.QT_INPUTS, 1.0, T_evap)
    P_e = st.p()
    st.update(CP.QT_INPUTS, 0.0, T_cond)
    P_c = st.p()

    # 1: compressor inlet (superheated vapor, or saturated if superheat = 0)
    if superheat > 0:
        T1 = T_evap + superheat
        st.update(CP.PT_INPUTS, P_e, T1)
    else:
        st.update(CP.PQ_INPUTS, P_e, 1.0)
        T1 = st.T()
    h1, s1, v1 = st.hmass(), st.smass(), 1.0 / st.rhomass()

    # 2: compressor outlet, from the isentropic efficiency
    st.update(CP.PSmass_INPUTS, P_c, s1)
    h2s = st.hmass()
    h2 = h1 + (h2s - h1) / eta_s
    st.update(CP.HmassP_INPUTS, h2, P_c)
    T2, s2 = st.T(), st.smass()

    # 3: condenser outlet (subcooled liquid, or saturated if subcool = 0)
    if subcool > 0:
        T3 = T_cond - subcool
        st.update(CP.PT_INPUTS, P_c, T3)
    else:
        st.update(CP.PQ_INPUTS, P_c, 0.0)
        T3 = st.T()
    h3, s3 = st.hmass(), st.smass()

    # 4: after the expansion valve (isenthalpic)
    h4 = h3
    st.update(CP.HmassP_INPUTS, h4, P_e)
    T4, s4 = st.T(), st.smass()

    q_e, w_c, q_c = h1 - h4, h2 - h1, h2 - h3
    return CycleResult(fluid, T_evap, T_cond, P_e, P_c, (h1, h2, h3, h4), (s1, s2, s3, s4),
                       (T1, T2, T3, T4), q_e, w_c, q_c, q_e / w_c,
                       T_evap / (T_cond - T_evap), h2s, v1)


def cycle_at_pressures(fluid, P_low, P_high, eta_s=1.0):
    """Ideal textbook cycle defined by its two pressures: saturated vapor
    into the compressor, saturated liquid out of the condenser.
    Used to reproduce textbook examples for validation."""
    st = _state(fluid)
    st.update(CP.PQ_INPUTS, P_low, 1.0)
    T_e = st.T()
    st.update(CP.PQ_INPUTS, P_high, 0.0)
    T_c = st.T()
    return _solve_cycle(fluid, T_e, T_c, eta_s, 0.0, 0.0)


# ---------------------------------------------------------------------------
# The chiller as a machine: heat exchangers of fixed size + a compressor map
# ---------------------------------------------------------------------------
# Calibrated in checks.calibrate_compressor_map() against seven points of the
# ASHRAE 90.1-2022 Appendix J "Path B" centrifugal reference curves along the
# AHRI 550/590 rating paths. Three numbers:
ETA_PEAK = 0.831      # peak isentropic efficiency of the compressor
CHOKE_EXP = 3.56      # how fast efficiency falls when flow is too high for the speed
FIXED_LOSS = 0.052    # drive, bearing and control losses, fraction of rated power
_MAP = dict(choke_exp=CHOKE_EXP)   # indirection so the calibration can vary it
MIN_PLR = 0.15        # lowest stable load of a variable-speed centrifugal (10-15 %)

# AHRI 550/590 standard rating point = the design point of the machine
AHRI_CHWS_C, AHRI_ECWT_C = 6.67, 29.44      # 44 F leaving chilled, 85 F entering condenser water
AHRI_RANGE_E, AHRI_RANGE_C = 5.56, 5.2      # K, water temperature change at full load
# Heat-exchanger size, set by a 1 K approach at the plant design ranges (6 K and 5 K)
DESIGN_RANGE_E, DESIGN_RANGE_C, DESIGN_APPROACH = 6.0, 5.0, 1.0


def hx_approach(range_K, plr, design_range, design_approach=DESIGN_APPROACH):
    """Approach (K) of a fixed-size evaporator or condenser. The refrigerant is
    at one temperature (phase change), so effectiveness = 1 - exp(-NTU) and
        approach = range / (exp(NTU) - 1),   NTU = UA / (m cp) = UA range / Q.
    UA is fixed by the design point; at part load Q falls, NTU rises and the
    approach shrinks."""
    if plr <= 0 or range_K <= 0:
        return 0.0
    ntu0 = math.log((design_range + design_approach) / design_approach)
    ntu = ntu0 * (range_K / design_range) / plr
    return range_K / math.expm1(min(ntu, 50.0))


def compressor_efficiency(x, eta_peak=ETA_PEAK):
    """Isentropic efficiency of a variable-speed centrifugal compressor.

    x = (flow fraction) / sqrt(head fraction), both relative to the design
    point. From the fan laws, speed N follows sqrt(head) and the best-efficiency
    flow follows N, so x = 1 is the best-efficiency point at any lift.
      x <= 1 : speed and guide vanes turn the flow down, efficiency holds
      x  > 1 : the flow is too large for the speed the lift needs; the
               compressor must spin faster and waste the extra head, so the
               efficiency falls as x^-n   (n = 2 would be the pure fan law)."""
    if x <= 1.0:
        return eta_peak
    return max(eta_peak * x ** (-_MAP['choke_exp']), 0.2 * eta_peak)


@lru_cache(maxsize=64)
def design_point(fluid, superheat=1.0, subcool=2.0):
    """The machine's design point (AHRI rating, full load) for a refrigerant:
    isentropic head, suction volume per unit cooling and shaft work per unit cooling."""
    a_e = hx_approach(AHRI_RANGE_E, 1.0, DESIGN_RANGE_E)
    a_c = hx_approach(AHRI_RANGE_C, 1.0, DESIGN_RANGE_C)
    c = _solve_cycle(fluid, round(AHRI_CHWS_C - a_e + 273.15, 2),
                     round(AHRI_ECWT_C + AHRI_RANGE_C + a_c + 273.15, 2), 1.0, superheat, subcool)
    return dict(head=c.h2s - c.h[0], vol_per_cooling=c.v1 / c.q_evap, w_s_per_cooling=1.0 / c.cop)


def operate(fluid, T_chws, range_e, T_ecw, range_c, plr, eta_peak=ETA_PEAK, motor_eff=0.96,
            superheat=1.0, subcool=2.0, min_lift=0.0, fixed_loss=FIXED_LOSS):
    """One chiller at a given load fraction and water temperatures (K).

    Returns the cycle, the efficiency actually reached and the electrical
    power per unit of cooling (so electrical COP = 1 / w_elec).
    Inputs are rounded slightly (0.05 K, 0.5 % load) so a day simulation
    reuses earlier solutions."""
    return _operate(fluid, round(T_chws * 20) / 20, round(range_e, 2), round(T_ecw * 20) / 20,
                    round(range_c, 2), round(plr * 200) / 200, round(eta_peak, 3), round(motor_eff, 3),
                    round(superheat, 2), round(subcool, 2), round(min_lift, 2), fixed_loss)


@lru_cache(maxsize=400_000)
def _operate(fluid, T_chws, range_e, T_ecw, range_c, plr, eta_peak, motor_eff,
             superheat, subcool, min_lift, fixed_loss):
    a_e = hx_approach(range_e, plr, DESIGN_RANGE_E)
    a_c = hx_approach(range_c, plr, DESIGN_RANGE_C)
    T_evap = T_chws - a_e
    T_cond = max(T_ecw + range_c + a_c, T_evap + min_lift)
    d = design_point(fluid, round(superheat, 2), round(subcool, 2))
    c = solve_cycle(fluid, T_evap, T_cond, 1.0, superheat, subcool)       # head and volume flow
    psi = (c.h2s - c.h[0]) / d["head"]
    phi = plr * (c.v1 / c.q_evap) / d["vol_per_cooling"]
    x = phi / math.sqrt(max(psi, 1e-9))
    eta = compressor_efficiency(x, eta_peak)
    c = solve_cycle(fluid, T_evap, T_cond, eta, superheat, subcool)
    w_shaft = 1.0 / c.cop                                                 # J of shaft work per J of cooling
    w_rated = d["w_s_per_cooling"] / eta_peak / motor_eff                 # rated electrical, per J at full load
    w_fixed = fixed_loss * w_rated / max(plr, 1e-9)
    w_elec = w_shaft / motor_eff + w_fixed
    return dict(cycle=c, eta=eta, x=x, psi=psi, phi=phi, approach_evap=a_e, approach_cond=a_c,
                w_shaft=w_shaft, w_elec=w_elec, w_fixed=w_fixed, cop_elec=1.0 / w_elec)


def part_load_efficiency(eta_rated, plr):
    """Kept for the single-cycle laboratory (Chiller Room): no map, the user
    sets the efficiency directly."""
    return eta_rated
