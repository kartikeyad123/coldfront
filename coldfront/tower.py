"""
tower.py - Cooling-tower thermal performance and water balance (SSSF device).

Approach temperature (leaving water minus entering-air wet-bulb) comes from the
YorkCalc empirical correlation used by EnergyPlus (CoolingTower:VariableSpeed,
Engineering Reference, "Cooling Towers and Evaporative Fluid Coolers"). It is
a 27-term polynomial in wet-bulb temperature Twb [C], range Tr [K] and the
liquid-to-gas ratio LG, so the approach is an OUTPUT of the model: it grows
when the wet-bulb is low and shrinks when the range is small.

Water balance (mass conservation):   make-up = evaporation + drift + blowdown
  evaporation : air leaves saturated; m_air (w_out - w_in)   (psychrometrics)
  drift       : droplets carried out, a fixed fraction of the circulating flow
  blowdown    : keeps dissolved solids at COC cycles of concentration,
                blowdown = evaporation / (COC - 1) - drift
"""

from functools import lru_cache
import CoolProp.CoolProp as CP

_C = (-0.359741205, -0.055053608, 0.0023850432, 0.173926877, -0.0248473764, 0.00048430224,
      -0.005589849456, 0.0005770079712, -1.342427256e-05, 2.84765801111111, -0.121765149,
      0.0014599242, 1.680428651, -0.0166920786, -0.0007190532, -0.025485194448, 4.87491696e-05,
      2.719234152e-05, -0.06537662555556, -0.002278167, 0.0002500254, -0.0910565458,
      0.00318176316, 3.8621772e-05, -0.0034285382352, 8.56589904e-06, -1.516821552e-06)

TWB_RANGE = (-34.4, 26.7)     # C, validity of the correlation
RANGE_RANGE = (1.1, 22.2)     # K
APPROACH_MIN = 1.1            # K

DRIFT_FRACTION = 1e-4         # 0.01 % of circulating flow (drift eliminators fitted)
CYCLES_OF_CONCENTRATION = 4.0 # typical 3 to 5


def yorkcalc_approach(T_wb_C, range_K, LG=1.0):
    """Tower approach (K) = leaving water T - entering wet-bulb T."""
    Twb = min(max(T_wb_C, TWB_RANGE[0]), TWB_RANGE[1])
    Tr = min(max(range_K, RANGE_RANGE[0]), RANGE_RANGE[1])
    a, k = 0.0, 0
    for lg in (1.0, LG, LG * LG):
        for tr in (1.0, Tr, Tr * Tr):
            for tw in (1.0, Twb, Twb * Twb):
                a += _C[k] * tw * tr * lg
                k += 1
    return max(a, APPROACH_MIN)


@lru_cache(maxsize=50_000)
def _evap_per_joule(T_db, T_dew, P_atm, range_K, LG):
    """kg of water evaporated per joule rejected, for air entering at
    (T_db, T_dew) and leaving saturated. Energy balance on the air:
    h_out = h_in + Q / m_air, with m_air = m_water / LG and
    Q = m_water cp range, so h_out - h_in = LG cp range."""
    T_dew = min(T_dew, T_db)
    h_in = CP.HAPropsSI("H", "T", T_db, "Tdp", T_dew, "P", P_atm)
    w_in = CP.HAPropsSI("W", "T", T_db, "Tdp", T_dew, "P", P_atm)
    dh = LG * 4186.0 * range_K
    w_out = CP.HAPropsSI("W", "H", h_in + dh, "R", 1.0, "P", P_atm)
    return max(w_out - w_in, 0.0) / dh        # (kg_w/kg_air) / (J/kg_air)


def water_balance(Q_rej, m_cw, T_db, T_dew, P_atm, range_K, LG=1.0):
    """Tower water flows (kg/s) for a heat rejection Q_rej (W)."""
    if Q_rej <= 0:
        return dict(evaporation=0.0, drift=0.0, blowdown=0.0, makeup=0.0)
    evap = Q_rej * _evap_per_joule(round(T_db, 1), round(T_dew, 1), round(P_atm, -2), round(range_K, 2), LG)
    drift = DRIFT_FRACTION * m_cw
    blow = max(evap / (CYCLES_OF_CONCENTRATION - 1.0) - drift, 0.0)
    return dict(evaporation=evap, drift=drift, blowdown=blow, makeup=evap + drift + blow)
