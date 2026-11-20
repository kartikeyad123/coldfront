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
    start: dict = field(default_factory=dict)       # how the plant is set when the shift begins
    events: tuple = ()
    targets: tuple = ()
    teaches: str = ""
    hint: str = ""
    lesson: str = ""                                # shown after the shift: the physics behind a good answer
    guide: tuple = ()                               # tutorial steps (work order 01 only)

    @property
    def pauses(self):
        return [e.t for e in self.events if e.pause]


INLET = Target("T_inlet_max", 27.0, "Peak server inlet", "°C")
COMPUTE = Target("compute_lost_pct", 0.0, "Compute lost", "%", nd=2)

ORDERS = [
    WorkOrder(
        "first_shift", "01", "First Shift", "AI lab, Los Angeles",
        "A normal day. Keep every server inlet at or below 27 °C and bring the day's PUE down to 1.18.",
        "la_typical", "inference",
        targets=(INLET, COMPUTE, Target("pue", 1.18, "Daily PUE", "", "efficiency", 1.17, 3)),
        teaches="The lift: warmer chilled water means less compressor work.",
        hint="Colder water is not safer, only more expensive. Raise the chilled-water supply and watch the chiller COP.",
        lesson="Raising the chilled-water temperature raises the evaporating temperature. The lift (condensing minus "
               "evaporating temperature) shrinks, and the COP is bounded by T_L / (T_H - T_L), so the compressors "
               "do less work for the same cooling. The limit is the 27 °C server inlet.",
        guide=("Press <b>Start shift</b>. The day runs with the settings as they are.",
               "Read the result. The servers were safe, but the PUE missed its target.",
               "Open <b>Chilled water</b> and raise the supply temperature to about 14 °C. Run the shift again.",
               "Click a chiller in the drawing to see its cycle: evaporating temperature, lift and COP.")),
    WorkOrder(
        "heatwave", "02", "Heatwave", "Hyperscaler, Phoenix campus",
        "A 43 °C day, and the forecast is about to get worse. Keep inlets at or below 27 °C, lose no compute, "
        "and hold the day's PUE at 1.20 or better.",
        "phoenix", "inference", locks=dict(rejection="tower"),
        events=(Event(11.0, "heat", 4.0, 19.0, "Heatwave: +4 °C until 19:00",
                      "The afternoon will be 4 °C hotter than forecast. The tower's water gets warmer, so the "
                      "condensing temperature and the lift go up."),),
        targets=(INLET, COMPUTE, Target("pue", 1.20, "Daily PUE", "", "efficiency", 1.185, 3)),
        teaches="Hot side of the lift: wet-bulb temperature sets the condensing temperature.",
        hint="You cannot cool the desert. You can shrink the lift from the other side.",
        lesson="A cooling tower works against the wet-bulb temperature. When the outdoor air gets hotter the "
               "condensing temperature rises. The operator's lever is the cold side: warmer chilled water keeps "
               "the lift, and the compressor work, down."),
    WorkOrder(
        "chiller_down", "03", "Chiller Down at 1:30 a.m.", "AI lab, Los Angeles",
        "A 4.5 MW training run starts at 02:00. Get through the night with no time above 27 °C and no GPU throttling.",
        "la_typical", "training",
        events=(Event(1.5, "trip", 1, 24.0, "Chiller 4 has tripped",
                      "Three chillers are left: 9 MW of cooling. In 30 minutes the training run takes the hall to "
                      "11.5 MW. Find 2.5 MW of cooling from somewhere else."),),
        targets=(Target("minutes_over_limit", 0.0, "Time above 27 °C", "min", nd=0), COMPUTE,
                 Target("pue", 1.21, "Daily PUE", "", "efficiency", 1.17, 3)),
        teaches="Capacity and free cooling: the night air can carry part of the load.",
        hint="The night is cool. Free cooling starts when the tower water is colder than the return water.",
        lesson="With one chiller gone the plant is 2.5 MW short. Raising the chilled-water temperature to about "
               "17 °C makes the return water warmer than the tower water at night, so the free-cooling exchanger "
               "carries the difference. A storage tank only helps if it was kept charged as a reserve."),
    WorkOrder(
        "price_spike", "04", "Price Spike", "Grid-aware startup, Los Angeles",
        "The plant has a 40 MWh chilled-water tank, nearly empty. Keep the day's cooling bill at $4,250 or less.",
        "la_typical", "inference",
        locks=dict(tank=True, tank_MWh=40.0, tank_rate_MW=5.0, tank_soc0=0.05), start=dict(price_charge=60.0),
        events=(Event(12.0, "notice", 0.0, 16.0, "Grid alert: prices triple from 16:00 to 21:00",
                      "The grid operator has called a shortage for this evening. Power is cheap for four more "
                      "hours. Cold water made now can be spent then."),
                Event(16.0, "price", 3.0, 21.0, "Price spike", "Prices are three times normal until 21:00.", pause=False)),
        targets=(INLET, COMPUTE, Target("cost_cooling", 4250.0, "Cooling bill", "$", "efficiency", 3900.0, 0)),
        teaches="The storage tank as a transient system: charge when cheap, discharge when dear.",
        hint="The tank only charges when the price is at or below its charge threshold. Look at the price right now.",
        lesson="The tank is a control volume whose cold-water mass changes with time. Charging before 16:00 moves "
               "compressor work to cheap hours; the chillers then idle through the spike. Charging pushes the "
               "chillers toward full load, so the rule stops at 90 % load to stay on the efficient side of the map."),
    WorkOrder(
        "not_a_drop", "05", "Not a Drop", "Sovereign AI cloud, Phoenix",
        "The city has capped your water permit at zero. Run the 43 °C day on dry coolers, keep inlets at or "
        "below 27 °C, lose no compute, and hold PUE at 1.36 or better.",
        "phoenix", "inference", locks=dict(rejection="dry"),
        events=(Event(14.0, "load", 1.0, 20.0, "Customer launch: +1 MW until 20:00",
                      "A customer has launched a model. The hall draws 1 MW more through the hottest hours."),),
        targets=(Target("wue_L_per_kWh", 0.0, "Water use", "L/kWh", nd=2), INLET, COMPUTE,
                 Target("pue", 1.36, "Daily PUE", "", "efficiency", 1.345, 3)),
        teaches="Water against energy: a dry cooler works against the dry-bulb temperature.",
        hint="The dry cooler sets a high condensing temperature. Everything you can do is on the cold side and in the water flow.",
        lesson="Without evaporation the heat sink is the 43 °C air plus 10 K, so the lift is large and the COP is "
               "low. Warmer chilled water and a larger water temperature difference (less pumping) recover part of it."),
    WorkOrder(
        "blackwell", "06", "Blackwell Retrofit", "Neocloud, Phoenix",
        "The hall now holds liquid-cooled GPU racks (about 130 kW each). Keep the coolant to the GPUs within "
        "40 °C, lose no compute, use no more than 1 MWh of compressor electricity and reach a PUE of 1.10.",
        "phoenix", "inference", locks=dict(rack_cooling="liquid", rejection="tower"),
        events=(Event(13.0, "trip", 2, 24.0, "Two chillers have tripped",
                      "A power-quality fault has taken two chillers offline at the hottest hour. Six megawatts "
                      "of chiller capacity are left for an 8 MW hall."),),
        targets=(Target("T_inlet_max", 40.0, "Peak coolant to GPUs", "°C"), COMPUTE,
                 Target("E_comp_MWh", 1.0, "Compressor electricity", "MWh", "efficiency", 0.1, 2),
                 Target("pue", 1.10, "Daily PUE", "", "efficiency", 1.09, 3)),
        teaches="Liquid cooling: warm facility water removes the refrigeration cycle.",
        hint="Cold plates accept coolant up to 40 °C. How warm can the facility water be?",
        lesson="GPU cold plates accept warm coolant, so the facility water can be warmer than the tower water even "
               "on a 43 °C day. Free cooling then carries the whole load, the compressors stop, and losing two "
               "chillers no longer matters."),
]
WORK_ORDERS = {w.key: w for w in ORDERS}
CONTRACTS = WORK_ORDERS      # older name


def run_order(order: WorkOrder, plans, until=24.0, dt=30.0):
    """Run a work order. plans[0] is used from midnight; plans[k] takes over at
    the k-th event. Locked settings are enforced on every plan."""
    plans = [replace(p, **order.locks, tank_cyclic=False) for p in plans]
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
