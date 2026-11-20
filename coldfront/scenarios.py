"""
scenarios.py - 24-hour conditions: outdoor weather, AI workload, electricity price.

WEATHER. The hot "design days" are built from ASHRAE climatic design data
(2009 Handbook - Fundamentals, cooling 0.4 % dry-bulb with mean coincident
wet-bulb): the afternoon peak dry-bulb and its wet-bulb match the published
values; the dew point is held constant over the day; the daily swing is an
assumed typical value. The two "typical" days are representative only.

    Station (ASHRAE)            0.4 % DB / MCWB [F]    [C]           Elevation
    Los Angeles Intl            83.7 / 64.3            28.7 / 17.9   325 ft
    Phoenix Sky Harbor          110.2 / 70.0           43.4 / 21.1   1106 ft
    Chicago O'Hare              91.9 / 74.6            33.3 / 23.7   673 ft
    Denver Intl                 94.3 / 60.3            34.6 / 15.7   5430 ft

PRICES. Two representative price shapes ($/MWh):
    retail    : large-commercial time-of-use energy charge with the 4-9 p.m.
                summer on-peak window used by Southern California Edison (TOU-8)
    wholesale : California (CAISO) 2025 wholesale shape - cheap midday solar,
                evening peak around $50-60/MWh
"""

import math
from dataclasses import dataclass
import CoolProp.CoolProp as CP

C2K = 273.15


def pressure_at_elevation(z_ft):
    """Standard-atmosphere barometric pressure (Pa) at elevation z (ft)."""
    z = z_ft * 0.3048
    return 101325.0 * (1 - 2.25577e-5 * z) ** 5.25588


@dataclass(frozen=True)
class Climate:
    key: str
    label: str
    T_peak: float      # C, afternoon peak dry-bulb (15:00)
    swing: float       # K, daily max - min
    T_dew_C: float     # C, dew point (constant over the day)
    P_atm: float       # Pa
    source: str = ""

    def dry_bulb(self, hour):
        """Dry-bulb (K): peak at 15:00, minimum at 03:00."""
        return self.T_peak - 0.5 * self.swing * (1 - math.cos(2 * math.pi * (hour - 15) / 24)) + C2K

    def dew_point(self, hour):
        return self.T_dew_C + C2K


def design_day(key, label, db_C, mcwb_C, swing, elev_ft):
    """Hot design day from ASHRAE 0.4 % DB / MCWB: the dew point is chosen so the
    wet-bulb at the 15:00 peak equals the published coincident wet-bulb."""
    P = pressure_at_elevation(elev_ft)
    T_dp = CP.HAPropsSI("Tdp", "T", db_C + C2K, "Twb", mcwb_C + C2K, "P", P) - C2K
    return Climate(key, label, db_C, swing, T_dp, P, "ASHRAE 0.4 % design")


def typical_day(key, label, T_mean, swing, T_dew_C, elev_ft):
    return Climate(key, label, T_mean + 0.5 * swing, swing, T_dew_C, pressure_at_elevation(elev_ft),
                   "representative")


CLIMATES = {
    "la_typical": typical_day("la_typical", "Los Angeles, typical day", 18.0, 7.0, 10.0, 325),
    "la_hot": design_day("la_hot", "Los Angeles, hot day", 28.7, 17.9, 7.0, 325),
    "phoenix": design_day("phoenix", "Phoenix, hot day", 43.4, 21.1, 12.0, 1106),
    "chicago_s": design_day("chicago_s", "Chicago, hot humid day", 33.3, 23.7, 9.0, 673),
    "chicago_w": typical_day("chicago_w", "Chicago, winter day", -4.0, 6.0, -9.0, 673),
    "denver": design_day("denver", "Denver, hot day (altitude)", 34.6, 15.7, 15.0, 5430),
}


@dataclass(frozen=True)
class Workload:
    key: str
    label: str
    base_MW: float
    description: str

    def it_load(self, hour):
        """IT (server) power in MW at a given hour."""
        if self.key == "inference":
            return self.base_MW * (1.0 + 0.15 * math.cos(2 * math.pi * (hour - 20) / 24))
        if self.key == "training":
            spike = 1.0 if 2.0 <= hour < 6.0 else 0.0
            ramp = 0.0
            if 1.5 <= hour < 2.0:
                ramp = (hour - 1.5) / 0.5
            elif 6.0 <= hour < 6.5:
                ramp = 1.0 - (hour - 6.0) / 0.5
            return self.base_MW + 4.5 * max(spike, ramp)
        if self.key == "launch":
            return self.base_MW * (1.0 + 0.45 / (1.0 + math.exp(-(hour - 13.0) * 1.5)))
        return self.base_MW


WORKLOADS = {
    "inference": Workload("inference", "Inference traffic", 8.0,
                          "Chatbot traffic: quiet overnight, busiest in the evening (about 60 GPU racks)."),
    "training": Workload("training", "3 a.m. training run", 7.0,
                         "Steady 7 MW plus a 4.5 MW training burst from 02:00 to 06:00."),
    "launch": Workload("launch", "Launch day", 7.5,
                       "A model launch: load climbs about 45 % from midday."),
}


@dataclass(frozen=True)
class Tariff:
    key: str
    label: str
    blocks: tuple       # ((start_hour, end_hour, $/MWh), ...)

    def price(self, hour):
        h = hour % 24
        for a, b, p in self.blocks:
            if a <= h < b:
                return p
        return self.blocks[-1][2]


TARIFFS = {
    "retail": Tariff("retail", "Retail time-of-use (4-9 p.m. peak)",
                     ((0, 8, 85.0), (8, 16, 95.0), (16, 21, 150.0), (21, 24, 95.0))),
    "wholesale": Tariff("wholesale", "Wholesale, California 2025 shape",
                        ((0, 6, 40.0), (6, 9, 48.0), (9, 16, 15.0), (16, 21, 55.0), (21, 24, 45.0))),
}


# ---------------------------------------------------------------------------
# Events: fixed, repeatable disturbances used by the work orders (missions)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Event:
    t: float            # hour the event starts
    kind: str           # 'trip' | 'heat' | 'humid' | 'price' | 'load' | 'notice' (no physical effect)
    value: float        # chillers lost | K added | K added to dew point | price multiplier | MW added
    until: float = 24.0 # hour it ends
    title: str = ""
    text: str = ""
    pause: bool = True  # the work order pauses here so the operator can react


def disturbance(events, hour):
    """Net effect of all active events at a given hour."""
    d = dict(n_lost=0, dT_db=0.0, dT_dew=0.0, price_mult=1.0, load_add=0.0)
    for e in events:
        if not (e.t <= hour < e.until):
            continue
        ramp = min(1.0, (hour - e.t) / 0.5)          # weather arrives over half an hour
        if e.kind == "trip":
            d["n_lost"] += int(e.value)
        elif e.kind == "heat":
            d["dT_db"] += e.value * ramp
        elif e.kind == "humid":
            d["dT_dew"] += e.value * ramp
        elif e.kind == "price":
            d["price_mult"] *= e.value
        elif e.kind == "load":
            d["load_add"] += e.value
    return d
