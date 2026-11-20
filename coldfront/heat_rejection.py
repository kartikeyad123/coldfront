"""
heat_rejection.py - Getting the heat out of the building.

Two options:
  * Cooling tower: evaporates a little water, so the condenser water can be
    cooled toward the outdoor WET-BULB temperature. Low fan power, uses water.
  * Dry cooler: a fan-driven air-to-liquid radiator. Can only approach the
    outdoor DRY-BULB temperature. More fan power, no water.

Both are steady-flow devices: Q_rejected = m_dot * cp * (T_in - T_out).
"""

import CoolProp.CoolProp as CP

CP_WATER = 4186.0        # J/(kg K)
RHO_WATER = 998.0        # kg/m^3
H_FG = 2.43e6            # J/kg, latent heat of evaporation of water near 30 C

TOWER = dict(name="Cooling tower", approach=None, fan_kw_per_kw=0.008, uses_water=True)
DRY = dict(name="Dry cooler", approach=10.0, fan_kw_per_kw=0.030, uses_water=False)
REJECTION = {"tower": TOWER, "dry": DRY}


def wet_bulb(T_db, T_dew, P_atm=101325.0):
    """Wet-bulb temperature (K) from dry-bulb and dew point, via CoolProp's
    humid-air (psychrometric) routines."""
    T_dew = min(T_dew, T_db)
    return CP.HAPropsSI("Twb", "T", T_db, "Tdp", T_dew, "P", P_atm)


def relative_humidity(T_db, T_dew, P_atm=101325.0):
    T_dew = min(T_dew, T_db)
    return CP.HAPropsSI("R", "T", T_db, "Tdp", T_dew, "P", P_atm)


def sink_temperature(mode, T_db, T_wb):
    """Coldest temperature the heat-rejection equipment can deliver (K):
    outdoor wet-bulb (tower) or dry-bulb (dry cooler) plus its approach."""
    eq = REJECTION[mode]
    base = T_wb if mode == "tower" else T_db
    return base + eq["approach"]


def rejection_power(mode, Q_rejected):
    """Fan electrical power (W) to reject Q_rejected (W)."""
    return REJECTION[mode]["fan_kw_per_kw"] * Q_rejected


def water_evaporated(mode, Q_rejected, blowdown_ratio=0.25):
    """Make-up water (kg/s): evaporation Q/h_fg plus blowdown that removes
    the minerals left behind. Zero for a dry cooler."""
    if not REJECTION[mode]["uses_water"]:
        return 0.0
    return Q_rejected / H_FG * (1.0 + blowdown_ratio)


def free_cooling_fraction(T_sink, T_chws, T_chwr, hx_approach=2.0):
    """Waterside economizer in series with the chillers. The tower water
    (through a plate heat exchanger) pre-cools the warm return water. Returns
    the fraction of the cooling load it carries (0 = none, 1 = all)."""
    T_precool = T_sink + hx_approach
    if T_precool >= T_chwr:
        return 0.0
    return min(1.0, (T_chwr - T_precool) / (T_chwr - T_chws))
