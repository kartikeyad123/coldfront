"""
contracts.py - Game mechanics. Each work order is a shift at a client's site:
fixed weather, workload and prices, some locked equipment, and a fixed,
repeatable timeline of events. The day pauses at each event so the operator can
react. Grades come only from engineering margins (how far each result is from
its limit), never from arbitrary points.
"""

from dataclasses import dataclass, field, replace

from .scenarios import Event
from .plant import PlantSettings
from .day import simulate_plan


@dataclass(frozen=True)
class Target:
    metric: str
    limit: float
    label: str
    unit: str
    kind: str = "safety"        # 'safety' (must hold) or 'efficiency'
    a_level: float = None       # efficiency targets: beat this for grade A
    nd: int = 1


@dataclass(frozen=True)
class WorkOrder:
    key: str
    number: str
    title: str
    client: str
    brief: str
    climate: str
    workload: str
    tariff: str = "retail"
    locks: dict = field(default_factory=dict)       # settings the operator cannot change
    limits: dict = field(default_factory=dict)      # settings with a narrower allowed range: key -> (low, high)
    start: dict = field(default_factory=dict)       # how the plant is set when the shift begins
    events: tuple = ()
    targets: tuple = ()
    teaches: str = ""
    hint: str = ""
    lesson: str = ""                                # shown after the shift: the physics behind a good answer
    guide: tuple = ()                               # tutorial steps (work order 01 only)
    lever: str = ""                                 # the control this problem is about
    passing: tuple = ()                             # reference play that just passes (grade B or better)
    solution: tuple = ()                            # reference play that earns an A: changes at each stage

    @property
    def pauses(self):
        return [e.t for e in self.events if e.pause]


INLET = Target("T_inlet_max", 27.0, "Peak server inlet", "°C")
COMPUTE = Target("compute_lost_pct", 0.0, "Compute lost", "%", nd=2)

# Tuned numbers for every problem set (written by tools/tune_orders.py from model runs).
# Each mission has three sets: same problem, different numbers.
from .order_numbers import NUMBERS   # noqa: E402
SETS = ("A", "B", "C")


def _eff(metric, label, unit, n, nd):
    return Target(metric, n["limit"], label, unit, "efficiency", n["a"], nd)


def _first_shift(i):
    climate, client = (("la_typical", "AI lab, Los Angeles"), ("la_hot", "AI lab, Los Angeles"),
                       ("chicago_s", "Trading firm, Chicago"))[i]
    n = NUMBERS["first_shift"][i]
    return WorkOrder(
        "first_shift", "01", "First Shift", client,
        f"A normal day. Keep every server inlet at or below 27 °C and bring the day's PUE down to {n['limit']:.3f}.",
        climate, "inference", locks=dict(rack_cooling="air"),
        targets=(INLET, COMPUTE, _eff("pue", "Daily PUE", "", n, 3)),
        teaches="The lift: warmer chilled water means less compressor work.",
        lever="Chilled-water temperature",
        hint="Colder water is not safer, only more expensive. Raise the chilled-water supply and watch the chiller COP.",
        lesson="Raising the chilled-water temperature raises the evaporating temperature. The lift (condensing minus "
               "evaporating temperature) shrinks, and the COP is bounded by T_L / (T_H - T_L), so the compressors "
               "do less work for the same cooling. The limit is the 27 °C server inlet: the racks receive the "
               "water plus 8 K.",
        passing=(dict(T_chws_C=14.0),), solution=(dict(T_chws_C=17.0),),
        guide=("Press <b>Start shift</b>. The day runs with the settings as they are.",
               "Read the result. The servers were safe, but the PUE missed its target.",
               "Open <b>Chilled water</b> and raise the supply temperature to about 17 °C. Run the shift again.",
               "Click a chiller in the drawing to see its cycle: evaporating temperature, lift and COP.") if i == 0 else ())


def _heatwave(i):
    hw, t0 = ((4.0, 11.0), (6.0, 10.0), (3.0, 12.0))[i]
    n = NUMBERS["heatwave"][i]
    return WorkOrder(
        "heatwave", "02", "Heatwave", "Hyperscaler, Phoenix campus",
        f"A 43 °C day, and a heatwave is coming. The city allows {n['permit']:.0f} m³ of water today; the cooling "
        f"tower alone would use about {n['tower_all']:.0f}. The client's air handlers need chilled water at 12 °C or "
        f"colder. Lose no compute and hold the day's PUE at {n['limit']:.3f} or better.",
        "phoenix", "inference", locks=dict(rack_cooling="air"), limits=dict(T_chws_C=(6.0, 12.0)),
        events=(Event(t0, "heat", hw, 19.0, f"Heatwave: +{hw:.0f} °C until 19:00",
                      f"The afternoon will be {hw:.0f} °C hotter than forecast. A dry cooler works against this air "
                      "temperature. A tower works against the wet-bulb temperature, which is far lower in the desert, "
                      "but it spends water."),),
        targets=(Target("water_m3", n["permit"], "Water used", "m³", nd=0), INLET, COMPUTE,
                 _eff("pue", "Daily PUE", "", n, 3)),
        teaches="Water against energy: spend the water in the hours where it saves the most work.",
        lever="Heat rejection, switched during the day",
        hint="You have water for about half a day of tower. The dry cooler costs least when the air is coolest.",
        lesson="A dry cooler rejects heat to the dry-bulb air; a tower rejects it toward the wet-bulb temperature by "
               "evaporating water. The gap between the two is largest in the hot afternoon, so that is where each "
               "cubic metre of water saves the most compressor work. Run dry at night, then switch to the tower "
               "for the heat. A larger water temperature rise trims the pumping power as well.",
        passing=(dict(rejection="dry"), dict(rejection="tower")),
        solution=(dict(rejection="dry", T_chws_C=12.0, dT_chw=10.0), dict(rejection="tower")))


def _chiller_down(i):
    climate, client, Tsol = (("la_typical", "AI lab, Los Angeles", 17.0), ("denver", "AI lab, Denver", 17.0),
                             ("la_hot", "AI lab, Los Angeles", 19.0))[i]
    n = NUMBERS["chiller_down"][i]
    return WorkOrder(
        "chiller_down", "03", "Chiller Down at 1:30 a.m.", client,
        "A 4.5 MW training run starts at 02:00. Get through the night with no time above 27 °C and no GPU throttling.",
        climate, "training", locks=dict(rack_cooling="air"),
        events=(Event(1.5, "trip", 1, 24.0, "Chiller 4 has tripped",
                      "Three chillers are left: 9 MW of cooling. In 30 minutes the training run takes the hall to "
                      "11.5 MW. Find 2.5 MW of cooling from somewhere else."),),
        targets=(Target("minutes_over_limit", 0.0, "Time above 27 °C", "min", nd=0), COMPUTE,
                 _eff("pue", "Daily PUE", "", n, 3)),
        teaches="Capacity and free cooling: the night air can carry part of the load.",
        lever="Free cooling, by warming the water at the right moment",
        hint="The night is cool. Free cooling starts when the tower water is colder than the return water.",
        lesson=f"With one chiller gone the plant is 2.5 MW short. Raising the chilled-water temperature to about "
               f"{Tsol:.0f} °C makes the return water warmer than the tower water at night, so the free-cooling "
               "exchanger carries the difference. Go too warm and the racks (water plus 8 K) pass 27 °C.",
        passing=({}, dict(T_chws_C=Tsol)), solution=({}, dict(T_chws_C=Tsol)))


def _price_spike(i):
    mult, tank = ((3.0, 40.0), (4.0, 30.0), (2.5, 50.0))[i]
    n = NUMBERS["price_spike"][i]
    return WorkOrder(
        "price_spike", "04", "Price Spike", "Grid-aware startup, Los Angeles",
        f"Power costs $85/MWh at night, $95 by day and $150 from 16:00 to 21:00. The plant has a {tank:.0f} MWh "
        f"chilled-water tank, nearly empty. The chilled-water settings are fixed. Keep the day's cooling bill at "
        f"${n['limit']:,.0f} or less.",
        "la_typical", "inference",
        locks=dict(tank=True, tank_MWh=tank, tank_rate_MW=5.0, tank_soc0=0.05, T_chws_C=10.0, dT_chw=6.0, rack_cooling="air"),
        start=dict(price_charge=60.0),
        events=(Event(12.0, "notice", 0.0, 16.0, f"Grid alert: prices ×{mult:g} from 16:00 to 21:00",
                      f"The grid operator has called a shortage for this evening: {mult:g} times the normal evening "
                      "price. Cold water already in the tank can be spent then."),
                Event(16.0, "price", mult, 21.0, "Price spike", f"Prices are {mult:g} times normal until 21:00.", pause=False)),
        targets=(INLET, COMPUTE, _eff("cost_cooling", "Cooling bill", "$", n, 0)),
        teaches="The storage tank as a transient system: charge when cheap, discharge when dear.",
        lever="Storage tank: when it charges",
        hint="The tank only charges when the price is at or below its charge threshold. When is power cheapest?",
        lesson="The tank is a control volume whose cold-water mass changes with time. It charges whenever the price "
               "is at or below the charge threshold. Set at $85, it fills overnight on the cheapest power and "
               "the chillers idle through the evening peak. Waiting for the noon alert still helps, but that water "
               "is made at $95, so the saving is smaller. Charging stops at 90 % chiller load to stay on the "
               "efficient side of the compressor map.",
        passing=({}, dict(price_charge=95.0)), solution=(dict(price_charge=85.0), {}))


def _not_a_drop(i):
    load, cap = ((1.0, 14.0), (1.5, 13.0), (0.5, 15.0))[i]
    n = NUMBERS["not_a_drop"][i]
    return WorkOrder(
        "not_a_drop", "05", "Not a Drop", "Sovereign AI cloud, Phoenix",
        f"The city has capped your water permit at zero, so the 43 °C day runs on dry coolers. The air handlers "
        f"need chilled water at {cap:.0f} °C or colder. Power costs $85/MWh at night and $95 by day. Keep inlets at "
        f"or below 27 °C, lose no compute, and hold PUE at {n['limit']:.3f} or better.",
        "phoenix", "inference", locks=dict(rejection="dry", tank_soc0=0.05, rack_cooling="air"), limits=dict(T_chws_C=(6.0, cap)),
        events=(Event(14.0, "load", load, 20.0, f"Customer launch: +{load:g} MW until 20:00",
                      f"A customer has launched a model. The hall draws {load:g} MW more through the hottest hours."),),
        targets=(Target("wue_L_per_kWh", 0.0, "Water use", "L/kWh", nd=2), INLET, COMPUTE,
                 _eff("pue", "Daily PUE", "", n, 3)),
        teaches="Make the cold when the lift is small: night air, less flow, stored cooling.",
        lever="Water temperature rise and a night-charged tank",
        hint="Desert nights are about 12 °C cooler than the afternoons. Cold water made at night takes less compressor work.",
        lesson="Without evaporation the heat sink is the outdoor air plus 10 K, so the afternoon lift is large and "
               "the COP is low. Three things add up: the warmest water the air handlers allow, a larger water "
               "temperature rise (less flow, so less pump work), and a tank that charges on cool night air "
               "(charge at $85) and discharges through the day (discharge at $95).",
        passing=(dict(T_chws_C=cap, dT_chw=10.0),),
        solution=(dict(T_chws_C=cap, dT_chw=10.0, tank=True, tank_MWh=60.0, tank_rate_MW=4.0, price_charge=85.0,
                       price_discharge=95.0),))


def _blackwell(i):
    climate, client = (("phoenix", "Neocloud, Phoenix"), ("la_hot", "Neocloud, Los Angeles"),
                       ("chicago_s", "Neocloud, Chicago"))[i]
    n = NUMBERS["blackwell"][i]
    return WorkOrder(
        "blackwell", "06", "Blackwell Retrofit", client,
        f"The hall now holds liquid-cooled GPU racks (about 130 kW each). Keep the coolant to the GPUs within "
        f"40 °C, lose no compute, use no more than 1 MWh of compressor electricity and reach a PUE of {n['limit']:.3f}.",
        climate, "inference", locks=dict(rack_cooling="liquid", rejection="tower"),
        events=(Event(13.0, "trip", 2, 24.0, "Two chillers have tripped",
                      "A power-quality fault has taken two chillers offline at the hottest hour. Six megawatts "
                      "of chiller capacity are left for an 8 MW hall."),),
        targets=(Target("T_inlet_max", 40.0, "Peak coolant to GPUs", "°C"), COMPUTE,
                 Target("E_comp_MWh", 1.0, "Compressor electricity", "MWh", "efficiency", 0.1, 2),
                 _eff("pue", "Daily PUE", "", n, 3)),
        teaches="Liquid cooling: warm facility water removes the refrigeration cycle.",
        lever="Facility water temperature, far above the air-cooled range",
        hint="Cold plates accept coolant up to 40 °C. How warm can the facility water be?",
        lesson="GPU cold plates accept warm coolant, so the facility water can be warmer than the tower water even "
               "on the hottest day. Free cooling then carries the whole load, the compressors stop, and losing two "
               "chillers no longer matters. The racks receive the water plus 4 K, so stay at or below 36 °C.",
        passing=(dict(T_chws_C=30.0),), solution=(dict(T_chws_C=30.0),))


_BUILD = dict(first_shift=_first_shift, heatwave=_heatwave, chiller_down=_chiller_down, price_spike=_price_spike,
              not_a_drop=_not_a_drop, blackwell=_blackwell)
VARIANTS = {k: [f(i) for i in range(3)] for k, f in _BUILD.items()}
ORDERS = [v[0] for v in VARIANTS.values()]
WORK_ORDERS = {w.key: w for w in ORDERS}
CONTRACTS = WORK_ORDERS      # older name


def get_order(key, variant=0):
    """Problem set `variant` (0, 1, 2) of a work order."""
    return VARIANTS[key][variant % 3]


def plans_for(order: WorkOrder, steps):
    """Turn a list of 'what the operator changes at each stage' into full plans."""
    cur = dict(PlantSettings().__dict__)
    cur.update(order.start)
    out = []
    for k in range(len(order.pauses) + 1):
        cur = dict(cur, **(steps[k] if k < len(steps) else {}))
        cur.update(order.locks)
        out.append(PlantSettings(**cur))
    return out


def run_order(order: WorkOrder, plans, until=24.0, dt=30.0):
    """Run a work order. plans[0] is used from midnight; plans[k] takes over at
    the k-th event. Locked settings are enforced on every plan."""
    plans = [replace(p, **order.locks, tank_cyclic=False) for p in plans]
    for k, (lo, hi) in order.limits.items():        # allowed range of a setting in this work order
        plans = [replace(p, **{k: min(hi, max(lo, getattr(p, k)))}) for p in plans]
    breaks = order.pauses[:len(plans) - 1]
    return simulate_plan(plans, breaks, order.climate, order.workload, dt, order.tariff, order.events, until)


def evaluate(order: WorkOrder, metrics: dict):
    """Returns (grade, rows). margin > 0 means inside the limit.
      A  every target met and every efficiency target beats its A level
      B  every target met
      C  the safety targets hold but an efficiency target is missed
      D  a safety target is missed"""
    rows, safe, eff, top = [], True, True, True
    for t in order.targets:
        v = metrics[t.metric]
        met = v <= t.limit + 1e-9
        if t.kind == "safety":
            safe &= met
        else:
            eff &= met
            top &= (t.a_level is None) or v <= t.a_level + 1e-9
        rows.append(dict(target=t.label, unit=t.unit, limit=t.limit, achieved=v, margin=t.limit - v, met=met,
                         kind=t.kind, a_level=t.a_level, nd=t.nd))
    grade = "D" if not safe else "C" if not eff else "A" if top else "B"
    return grade, rows
