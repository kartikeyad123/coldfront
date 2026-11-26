"""
ask.py - "Ask the plant": plain-language answers about the day on screen.

There is no AI model here. A question is reduced to concepts (with synonyms and
tolerance for typos), matched to one of a fixed list of topics, and the answer
is written from the numbers of the run on screen. If no topic matches well,
the closest topics are offered instead of a guess.
"""
import difflib
import re

import numpy as np

from .explain import stats

# phrases that should be read as one word
PHRASES = [("water temperature rise", "deltat"), ("temperature rise", "deltat"), ("free cooling", "freecooling"), ("free-cooling", "freecooling"), ("wet bulb", "wetbulb"), ("wet-bulb", "wetbulb"),
           ("dry bulb", "drybulb"), ("dry cooler", "drycooler"), ("dry coolers", "drycooler"), ("cooling tower", "tower"),
           ("data center", "datacenter"), ("data centre", "datacenter"), ("data hall", "hall"), ("set point", "setpoint"),
           ("second law", "secondlaw"), ("first law", "firstlaw"), ("steady state", "sssf"), ("steady flow", "sssf"),
           ("control volume", "transient"), ("heat exchanger", "exchanger"), ("liquid cooling", "liquidcooling"),
           ("liquid cooled", "liquidcooling"), ("liquid-cooled", "liquidcooling"), ("direct to chip", "liquidcooling"),
           ("power usage effectiveness", "pue"), ("coefficient of performance", "cop"), ("how much", "howmuch"),
           ("how many", "howmuch"), ("part load", "partload"), ("go up", "rise"), ("went up", "rise"), ("go down", "fall"),
           ("went down", "fall"), ("too hot", "overheat"), ("too warm", "overheat"), ("heat up", "overheat"),
           ("chilled water", "chilledwater"), ("water temperature", "chilledwater"), ("supply temperature", "chilledwater"),
           ("temperature rise", "deltat"), ("delta t", "deltat"), ("warms up", "deltat"), ("make up", "makeup"),
           ("time step", "timestep"), ("mass flow", "flow"), ("cold plate", "liquidcooling"), ("cold plates", "liquidcooling"), ("best possible", "carnot"),
           ("get a c", "grade"), ("got a c", "grade"), ("get a d", "grade"), ("got a d", "grade"), ("get a b", "grade"), ("got a b", "grade"),
           ("get an a", "grade"), ("got an a", "grade"), ("an a", "grade"), ("this place", "datacenter"), ("get out", "where"), ("gets out", "where"), ("leave the", "where the")]

# concept -> the words that mean it
SYN = {
    "pue": ["pue", "effectiveness", "overhead"],
    "cop": ["cop", "coefficient"],
    "efficiency": ["efficiency", "efficient", "inefficient", "wasteful", "waste", "wasting", "performance"],
    "lift": ["lift", "gap", "uphill"],
    "freecooling": ["freecooling", "economizer", "economiser", "exchanger", "free"],
    "tower": ["tower", "evaporative", "evaporation", "evaporate", "plume"],
    "drycooler": ["drycooler", "dry", "radiator", "aircooled"],
    "water": ["water", "wue", "makeup", "blowdown", "drift", "permit", "thirsty", "litres", "liters", "gallons", "gallon", "drought"],
    "chiller": ["chiller", "chillers", "machine"],
    "cycle": ["cycle", "refrigeration", "compressor", "condenser", "evaporator", "valve", "expansion", "vapor", "vapour", "fridge", "refrigerator", "loop"],
    "refrigerant": ["refrigerant", "r134a", "134a", "r1234ze", "1234ze", "ammonia", "propane", "gwp", "fluid", "freon", "gas"],
    "tank": ["tank", "storage", "store", "stored", "battery", "charge", "charging", "discharge", "discharging"],
    "pump": ["pump", "pumps", "pumping", "flow", "circulate"],
    "overheat": ["overheat", "overheating", "hot", "hotter", "limit", "inlet", "27", "temperature", "warm", "cook", "safe", "unsafe", "danger"],
    "hall": ["hall", "server", "servers", "rack", "racks", "room", "gpu", "gpus", "computers", "chips"],
    "throttle": ["throttle", "throttling", "throttled", "compute", "lost", "slow", "slowed", "shutdown", "shut"],
    "short": ["short", "shortfall", "unmet", "capacity", "enough", "insufficient", "tripped", "trip", "failed", "failure", "offline", "broke"],
    "bill": ["bill", "cost", "costs", "money", "dollars", "expensive", "cheap", "cheaper", "spend", "pay", "budget", "$"],
    "price": ["price", "prices", "tariff", "rate", "peak", "spike", "wholesale", "retail", "cheapest", "dearest"],
    "workload": ["workload", "load", "training", "inference", "launch", "demand", "traffic"],
    "weather": ["weather", "outside", "outdoor", "climate", "wetbulb", "drybulb", "humid", "humidity", "heatwave", "desert", "phoenix", "chicago", "denver", "angeles", "ambient", "night", "summer", "winter"],
    "liquidcooling": ["liquidcooling", "liquid", "coldplate", "blackwell", "direct"],
    "chilledwater": ["chilledwater", "setpoint", "supply", "colder", "warmer", "17"],
    "deltat": ["deltat", "range"],
    "improve": ["improve", "better", "best", "fix", "reduce", "cut", "save", "saving", "optimize", "optimise", "change", "try", "should", "recommend", "advice", "tip", "tips", "help", "differently", "suggest", "suggestion", "next", "win", "pass", "solve"],
    "grade": ["grade", "graded", "score", "scored", "mark", "target", "targets", "rating", "stars"],
    "entropy": ["wastes", "wasted", "entropy", "secondlaw", "irreversible", "irreversibility", "exergy", "sgen", "generation", "generated", "loss", "losses", "lost work"],
    "carnot": ["carnot", "ideal", "theoretical", "maximum", "reversible"],
    "sssf": ["sssf", "steady", "transient", "unsteady"],
    "trust": ["accurate", "accuracy", "real", "realistic", "trust", "validated", "validation", "proof", "check", "checks", "wrong", "correct", "believe", "tested", "tests", "error", "balance", "numbers", "right", "true", "firstlaw", "coolprop", "model", "simulation", "timestep", "euler"],
    "power": ["power", "electricity", "energy", "kwh", "mwh", "watts", "megawatts", "consumption", "consume", "consumes", "use", "uses", "used"],
    "heat": ["heat", "hot", "warmth", "reject", "rejected", "rejection"],
    "where": ["where", "path", "goes", "go", "going", "end", "ends"],
    "datacenter": ["datacenter", "ai", "nvidia", "center", "centre", "facility"],
    "who": ["who", "made", "built", "author", "kartikeya", "created", "creator", "project", "coldfront"],
    "why": ["why", "cause", "caused", "reason", "because", "rise", "high", "higher", "low", "lower", "drop", "dropped", "bad", "worse", "explain"],
    "what": ["what", "mean", "means", "meaning", "define", "definition"],
    "running": ["running", "run", "stage", "staging", "standby", "idle", "howmuch", "number"],
}
WORD2C = {}
for _c, _ws in SYN.items():
    for _w in _ws:
        WORD2C.setdefault(_w, set()).add(_c)
VOCAB = sorted(w for w in WORD2C if len(w) >= 3)
STOP = set("the they them then than that this with what when where which will would could should have has had does did were was are "
           "and for from into about your you our out not but can how who why its his her their there here some more most much many "
           "very just like make made get got going been being also only over under than too tell show give need want know think "
           "thing things stuff deal really please thanks hello".split())


def concepts(q):
    """The set of concepts a question mentions."""
    t = " " + q.lower().replace("’", "'") + " "
    for a, b in PHRASES:
        t = re.sub(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", b, t)
    t = t.replace("$", " $ ")
    out = set()
    for w in re.findall(r"[a-z0-9$]+", t):
        cands = [w]
        if len(w) > 4:
            cands += [w[:-1]] if w.endswith("s") else []
            cands += [w[:-3], w[:-3] + "e"] if w.endswith("ing") else []
            cands += [w[:-2], w[:-1]] if w.endswith("ed") else []
        hit = next((c for c in cands if c in WORD2C), None)
        if hit is None and len(w) >= 4 and w not in STOP and not w.isdigit():
            close = difflib.get_close_matches(w, VOCAB, 1, 0.8 if len(w) > 4 else 0.85)
            hit = close[0] if close else None
        if hit:
            out |= WORD2C[hit]
    return out


# ------------------------------------------------------------------ answers
def _hhmm(h):
    return f"{int(h):02d}:{int(round(h % 1 * 60)) % 60:02d}"


def _advice(day, S):
    s, tips = day.settings, []
    air = s.rack_cooling == "air"
    room = s.T_limit_C - s.approach_rack - s.T_chws_C
    if S["over"] > 0:
        tips.append(f"<b>First fix the shortfall</b> (worst {S['short']:.1f} MW). Warmer supply water lets free cooling carry part of the load on a cool "
                    "night; a storage tank or another chiller adds capacity.")
    if room > 2 and S["cop"] == S["cop"]:
        tips.append(f"<b>Warm the chilled water.</b> It is {s.T_chws_C:g} °C now and the racks could take about {s.T_chws_C + room - 2:g} °C "
                    f"({'water + 8 K' if air else 'water + 4 K'} must stay under {s.T_limit_C:g} °C). Smaller lift, higher COP.")
    if s.dT_chw < 8:
        tips.append(f"<b>Raise the water temperature rise</b> from {s.dT_chw:g} °C. Less flow for the same heat, so the pumps ({S['E_pump']:.1f} MWh today) use less.")
    if s.rejection == "dry":
        tips.append("<b>A cooling tower</b> would reject heat toward the wet-bulb temperature instead of the air temperature, at the price of water.")
    if not s.tank:
        tips.append("<b>A storage tank</b> can make cold water when power is cheap and use it when power is dear. It moves the bill more than the PUE.")
    if air and S["E_comp"] > 5:
        tips.append("<b>Liquid cooling</b> accepts water up to 36 °C, warm enough for the chillers to stop on most days.")
    return tips[:3] or ["This plant is already close to the best it can do on this day."]


def _lead(first, rest):
    return first + (" " + " ".join(rest) if rest else "")


def a_pue(day, S, c):
    share = lambda k: 100 * day.metrics[k] / max(day.metrics["E_total_MWh"], 1e-9)
    return (f"<b>PUE is total power divided by computer power.</b> 1.00 would be perfect. Today it is <b>{S['pue']:.3f}</b>: for every 100 W of "
            f"computing, {100 * (S['pue'] - 1):.0f} W more went to everything else. Compressors took {share('E_comp_MWh'):.1f} % of all the "
            f"electricity; pumps, fans and other overhead the rest. "
            + ("To lower it: " + " ".join(_advice(day, S)[:2]) if ("improve" in c or "why" in c) else "Ask “how do I lower the PUE” for ideas."))


def a_cop(day, S, c):
    if S["cop"] != S["cop"]:
        return "<b>The chillers never ran today</b>, so there is no COP: free cooling carried the whole load."
    return (f"<b>COP is cooling delivered per unit of compressor electricity.</b> Today the chillers averaged <b>{S['cop']:.1f}</b>, about "
            f"{100 * day.metrics['eff2_mean']:.0f} % of the Carnot limit T_L / (T_H − T_L). It is set mostly by the lift, {S['lift']:.0f} K today "
            f"(evaporating at {S['T_evap']:.0f} °C, condensing at {S['T_cond']:.0f} °C). A smaller lift gives a higher COP.")


def a_lift(day, S, c):
    if S["lift"] != S["lift"]:
        return "<b>Lift is the temperature gap the chiller must push heat across.</b> The chillers did not run today, so there was none."
    return (f"<b>Lift is the gap between the condensing and evaporating temperatures.</b> The chiller pushes heat “uphill” across it. Today it "
            f"averaged <b>{S['lift']:.0f} K</b> ({S['T_evap']:.0f} → {S['T_cond']:.0f} °C). Warmer chilled water raises the bottom; cooler "
            "outdoor conditions or a cooling tower lower the top. Either way the compressor does less work.")


def a_fc(day, S, c):
    s = day.settings
    if not s.free_cooling:
        return "<b>Free cooling is switched off</b> in this plant. Turn it on under Heat rejection."
    x = day.series
    on = x["f_fc"] > 0.01
    when = f" It ran from about {_hhmm(x['hour'][on][0])} to {_hhmm(x['hour'][on][-1])}." if on.any() else ""
    return (f"<b>Free cooling cools the return water with tower water directly, with no compressor.</b> It only works when the tower water plus "
            f"{s.hx_approach:g} K is colder than the return water ({s.T_chws_C + s.dT_chw:g} °C here). Today it did the work of "
            f"<b>{S['fc_h']:.1f} full hours</b>.{when} Warmer chilled water or a colder night gives it more to do.")


def a_tower(day, S, c):
    if day.settings.rejection != "tower":
        return a_dry(day, S, c)
    return (f"<b>The cooling tower gives the plant's heat to the outside air by evaporating a little water.</b> That lets it cool water toward the "
            f"wet-bulb temperature, which is lower than the air temperature. Today it sent water back at {S['sink']:.0f} °C on average and used "
            f"{S['water']:,.0f} m³ of make-up water.")


def a_dry(day, S, c):
    if day.settings.rejection != "dry":
        return ("<b>A dry cooler is a fan-driven radiator.</b> It uses no water but can only get within about 10 K of the air temperature, so the "
                "chillers work across a bigger lift. This plant uses a cooling tower. Switch under Heat rejection to compare.")
    return (f"<b>The dry cooler is a fan-driven radiator: no water, but it can only get within 10 K of the air temperature.</b> Today it sent water "
            f"back at {S['sink']:.0f} °C on average, so the lift was {S['lift']:.0f} K and the COP {S['cop']:.1f}.")


def a_water(day, S, c):
    m = day.metrics
    if S["water"] < 1:
        return "<b>This plant used no water today.</b> Dry coolers reject heat to the air directly. The cost is a bigger lift and more electricity."
    return (f"<b>The tower used {S['water']:,.0f} m³ of water today</b> ({m['wue_L_per_kWh']:.2f} L per kWh of computing). {m['evaporation_m3']:,.0f} m³ "
            f"evaporated, which is how the heat leaves; {m['blowdown_m3']:,.0f} m³ was drained to stop minerals building up; drift was "
            f"{m['drift_m3']:.1f} m³. To use less: free cooling does not reduce it much, a dry cooler removes it entirely.")


def a_chiller(day, S, c):
    x = day.series
    return (f"<b>A chiller is a refrigeration cycle that moves heat from the chilled water to the condenser water.</b> Today {int(np.max(x['n_on']))} "
            f"of {day.settings.n_chillers} ran at most, {S['n_on']:.1f} on average"
            + (f", at {100 * day.metrics['plr_mean']:.0f} % load each" if S["cop"] == S["cop"] else "")
            + ". The plant runs as few as it can while keeping each compressor near its best-efficiency point."
            + ("" if S["cop"] == S["cop"] else " Today they stayed off: free cooling carried the load."))


def a_cycle(day, S, c):
    return ("<b>Four devices in a loop.</b> The <b>compressor</b> squeezes cold vapor: it gets hot and high-pressure. The <b>condenser</b> lets that "
            "vapor give its heat to the condenser water and turn to liquid. The <b>expansion valve</b> drops the pressure, so the liquid turns "
            "cold and partly boils. The <b>evaporator</b> lets it finish boiling by taking heat from the chilled water. Then round again. "
            "Open <b>Chiller lab</b> to see it move, with pressure, temperature and liquid or vapor at each point.")


def a_refrigerant(day, S, c):
    from coldfront.chiller import REFRIGERANTS
    return (f"<b>This plant uses {REFRIGERANTS[day.settings.fluid]}.</b> The refrigerant is the fluid that boils cold in the evaporator and "
            "condenses hot in the condenser. In this model the four choices differ by only a few percent in efficiency; they differ a lot in "
            "global-warming potential (R-134a 1430, R-1234ze 1, ammonia 0, propane 3).")


def a_tank(day, S, c):
    s = day.settings
    if not s.tank:
        return ("<b>There is no storage tank in this plant.</b> A tank holds cold water: the chillers fill it when electricity is cheap and the "
                "hall uses it when electricity is dear, or when a chiller fails. Turn it on under Storage tank.")
    return (f"<b>The tank is a store of cold water</b> ({s.tank_MWh:g} MWh, about {s.tank_volume_m3:,.0f} m³). It charges when the price is at or "
            f"below ${s.price_charge:g}/MWh and discharges at or above ${s.price_discharge:g}/MWh. Today it delivered <b>{S['E_dis']:.1f} MWh</b> "
            "of cooling. It is a transient control volume: its cold-water mass changes through the day.")


def a_pump(day, S, c):
    return (f"<b>The pumps move the water round the two loops.</b> Today they used {S['E_pump']:.2f} MWh, with an average chilled-water flow of "
            f"{S['flow']:.0f} kg/s. Pump power grows roughly with the cube of the flow, and all of it ends up as heat in the water. A larger "
            f"water temperature rise (now {day.settings.dT_chw:g} °C) carries the same heat with less flow.")


def a_overheat(day, S, c):
    s, x = day.settings, day.series
    k = int(np.argmax(x["T_inlet"]))
    if S["over"] <= 0:
        return (f"<b>The servers stayed safe.</b> The hottest moment was {S['peak']:.1f} °C at {_hhmm(x['hour'][k])}, against a limit of "
                f"{s.T_limit_C:g} °C. The racks receive the supply water ({s.T_chws_C:g} °C) plus {s.approach_rack:g} K.")
    k = int(np.argmax(x["shortfall"]))
    return (f"<b>The hall overheated because the plant could not remove the heat fast enough.</b> At {_hhmm(x['hour'][k])} it was "
            f"{S['short']:.1f} MW short, the racks reached {S['peak']:.1f} °C (limit {s.T_limit_C:g} °C) and stayed over for {S['over']:.0f} "
            f"minutes. " + _advice(day, S)[0])


def a_throttle(day, S, c):
    if S["lost"] <= 0:
        return "<b>No compute was lost today.</b> GPUs only slow down if the hall gets 5 K above its limit."
    return (f"<b>The GPUs gave up {S['lost']:.1f} % of the day's compute</b> to protect themselves. Above the limit plus 5 K they cut power by 8 % per "
            "kelvin, and 12 to 15 K above that they shut down. This is an assumed operating rule, not a physical law. The cure is more cooling "
            "at the moment of the shortfall.")


def a_short(day, S, c):
    if S["short"] < 0.05:
        return (f"<b>Cooling never fell short today.</b> The chillers can deliver {day.settings.n_chillers * day.settings.chiller_cap_MW:g} MW and the "
                f"peak heat load was {S['peak_it']:.1f} MW.")
    return a_overheat(day, S, c)


def a_bill(day, S, c):
    m = day.metrics
    return (f"<b>The cooling bill was ${S['bill']:,.0f} today</b> (the whole site: ${m['cost_total']:,.0f}). Every 30 seconds the model multiplies "
            "the plant's power by the price at that hour and adds it up. Two things lower it: use less energy (warmer water, smaller lift) or "
            "use it at cheaper hours (a storage tank charged at night).")


def a_price(day, S, c):
    p = day.series["price"]
    return (f"<b>Electricity cost between ${float(np.min(p)):.0f} and ${float(np.max(p)):.0f} per MWh today.</b> The price matters because a storage "
            "tank can make cold water in the cheap hours and spend it in the dear ones.")


def a_workload(day, S, c):
    x = day.series
    k = int(np.argmax(x["Q_it_req"]))
    return (f"<b>The workload is the heat the servers give off, hour by hour.</b> Almost every watt a GPU draws becomes heat. Today it ranged from "
            f"{float(np.min(x['Q_it_req'])) / 1e6:.1f} to {S['peak_it']:.1f} MW, peaking at {_hhmm(x['hour'][k])}. More load means more heat for "
            "the chilled water to carry, so the chillers, pumps and tower all work harder.")


def a_weather(day, S, c):
    x = day.series
    return (f"<b>The weather sets how hard it is to get rid of the heat.</b> Today the air went from {float(np.min(x['T_db'])):.0f} to "
            f"{float(np.max(x['T_db'])):.0f} °C and the wet-bulb from {float(np.min(x['T_wb'])):.0f} to {float(np.max(x['T_wb'])):.0f} °C. A cooling "
            "tower works against the wet-bulb temperature, a dry cooler against the air temperature. Hotter outside means a bigger lift.")


def a_liquid(day, S, c):
    on = day.settings.rack_cooling == "liquid"
    return ("<b>Liquid cooling pipes coolant straight to cold plates on the GPUs.</b> They accept coolant up to 40 °C, so the facility water can be "
            "about 30 °C instead of 10 °C. That is warmer than the tower water even on a 43 °C day, so free cooling can carry the whole load and "
            "the chillers switch off. " + ("This hall is liquid-cooled." if on else "This hall is air-cooled; switch under Chilled water."))


def a_chw(day, S, c):
    s = day.settings
    return (f"<b>The chilled-water supply is {s.T_chws_C:g} °C.</b> The racks receive it plus {s.approach_rack:g} K, so the limit of {s.T_limit_C:g} °C "
            f"allows up to about {s.T_limit_C - s.approach_rack:g} °C. Colder water is not safer, only more expensive: it lowers the evaporating "
            "temperature, which increases the lift and the compressor work.")


def a_dt(day, S, c):
    return (f"<b>The rise is how much the water warms up in the hall</b> ({day.settings.dT_chw:g} °C here). The same heat can be carried by a lot of "
            "water warming a little or a little water warming a lot: Q = ṁ c_p ΔT. A larger rise needs less flow, so less pump power, and "
            "warmer return water also helps free cooling.")


def a_improve(day, S, c):
    return "<b>Three things to try on this plant, biggest first.</b><br>" + "<br>".join(f"{i + 1}. {t}" for i, t in enumerate(_advice(day, S)))


def a_grade(day, S, c):
    return ("<b>Each attempt at a work order earns a grade from its margins.</b> A: every target met and the efficiency target beaten by the amount "
            "in the “For an A” column. B: every target met. C: servers safe but an efficiency target missed. D: a safety limit crossed. "
            "The Console has no targets and no grade.")


def a_entropy(day, S, c):
    return ("<b>Entropy generated measures what each device wastes.</b> Click a chiller in the drawing: the panel shows S_gen for the compressor, "
            "condenser, valve and evaporator at this instant. Lost work is T₀ × S_gen, and the Proof page checks that the compressor work "
            "equals the reversible minimum plus those losses.")


def a_carnot(day, S, c):
    if S["cop"] != S["cop"]:
        return "<b>The Carnot COP is the best any refrigerator could do: T_L / (T_H − T_L).</b> The chillers did not run today."
    return (f"<b>The Carnot COP is the best any refrigerator could do between two temperatures: T_L / (T_H − T_L).</b> Today the real cycle reached "
            f"about {100 * day.metrics['eff2_mean']:.0f} % of it. The gap is friction in the compressor, throttling in the valve and the "
            "temperature differences in the two heat exchangers.")


def a_sssf(day, S, c):
    return ("<b>Most devices are solved as steady-state steady-flow (SSSF):</b> compressor, condenser, valve, evaporator, pumps, tower and the "
            "free-cooling exchanger are re-solved at every time step. <b>Two are transient control volumes</b> that store something: the data "
            "hall stores energy (its temperature changes) and the tank stores cold water (its mass changes).")


def a_trust(day, S, c):
    m = day.metrics
    return (f"<b>The model is checked on the Proof page.</b> The cycle matches a textbook example within 0.06 %, the chiller sits inside the ASHRAE "
            f"90.1 efficiency limits, and today's energy balance closed to {abs(m['energy_balance_err_pct']):.0e} %. One check does not pass and "
            "is left visible: the model gains more from warmer water than the 1 to 2 % per °F rule of thumb, so those savings are an upper bound.")


def a_power(day, S, c):
    m = day.metrics
    tot = max(m["E_total_MWh"], 1e-9)
    return (f"<b>Where the electricity went today</b> ({tot:.0f} MWh in all): computers {100 * m['E_it_MWh'] / tot:.0f} %, compressors "
            f"{100 * m['E_comp_MWh'] / tot:.1f} %, pumps {100 * S['E_pump'] / tot:.1f} %, tower or cooler fans {100 * S['E_fan'] / tot:.1f} %, and "
            "the rest in hall fans and electrical losses.")


def a_heat(day, S, c):
    m = day.metrics
    return (f"<b>Follow the heat.</b> The servers made {m['E_it_MWh']:.0f} MWh of heat. The chilled water carried it out of the hall. Free cooling "
            f"and the chillers moved it to the condenser water, the compressors added {m['E_shaft_MWh']:.0f} MWh of work on the way, and the "
            f"{'tower' if day.settings.rejection == 'tower' else 'dry cooler'} gave {m['E_rej_MWh']:.0f} MWh to the outside air. Press "
            "<b>Heat collection loop</b> and <b>Heat rejection loop</b> above the drawing to see the two halves.")


def a_datacenter(day, S, c):
    return ("<b>An AI data center is a building full of GPUs.</b> Nearly every watt they draw turns into heat, so an 8 MW hall is an 8 MW heater "
            "that must be cooled all day. Most of that cooling is done by chillers, which are refrigeration cycles. COLDFRONT lets you run that "
            "cooling plant.")


def a_who(day, S, c):
    return ("<b>COLDFRONT was built by Kartikeya Daiya</b> as a final project for AME 310 (Engineering Thermodynamics I) at USC. The physics is a "
            "vapor-compression cycle with CoolProp refrigerant properties. This helper is not an AI: it matches your question to a topic and "
            "answers from the numbers of the run on screen.")


# topic: (title shown as a suggestion, answer function, {concept: weight})
TOPICS = {
    "pue": ("What is PUE and why is it this high?", a_pue, dict(pue=4)),
    "cop": ("What is the COP?", a_cop, dict(cop=4)),
    "lift": ("What is lift?", a_lift, dict(lift=4)),
    "fc": ("What is free cooling and when does it work?", a_fc, dict(freecooling=4)),
    "tower": ("What does the cooling tower do?", a_tower, dict(tower=4)),
    "dry": ("What is a dry cooler?", a_dry, dict(drycooler=5)),
    "water": ("Why does the plant use water?", a_water, dict(water=3)),
    "chiller": ("What does a chiller do, and how many are running?", a_chiller, dict(chiller=3, running=1)),
    "cycle": ("How does the refrigeration cycle work?", a_cycle, dict(cycle=4)),
    "refrigerant": ("Which refrigerant is this, and does it matter?", a_refrigerant, dict(refrigerant=4)),
    "tank": ("What does the storage tank do?", a_tank, dict(tank=4)),
    "pump": ("What do the pumps do?", a_pump, dict(pump=4)),
    "overheat": ("Why did the servers get hot?", a_overheat, dict(overheat=3, hall=1)),
    "throttle": ("Why was compute lost?", a_throttle, dict(throttle=5)),
    "short": ("Is there enough cooling capacity?", a_short, dict(short=4)),
    "bill": ("Why is the bill what it is?", a_bill, dict(bill=4)),
    "price": ("How does the electricity price matter?", a_price, dict(price=3, bill=2)),
    "workload": ("What happens when the workload goes up?", a_workload, dict(workload=3)),
    "weather": ("How does the weather change things?", a_weather, dict(weather=3.5)),
    "liquid": ("What is liquid cooling?", a_liquid, dict(liquidcooling=4)),
    "chw": ("How cold should the chilled water be?", a_chw, dict(chilledwater=4)),
    "dt": ("What is the water temperature rise?", a_dt, dict(deltat=4)),
    "improve": ("What should I change?", a_improve, dict(improve=2)),
    "grade": ("How are grades decided?", a_grade, dict(grade=3)),
    "entropy": ("Where is entropy generated?", a_entropy, dict(entropy=5)),
    "carnot": ("What is the Carnot limit?", a_carnot, dict(carnot=5)),
    "sssf": ("Which parts are steady flow and which are transient?", a_sssf, dict(sssf=4)),
    "trust": ("How do I know the numbers are right?", a_trust, dict(trust=3)),
    "power": ("Where does the electricity go?", a_power, dict(power=2, where=1, running=1)),
    "heat": ("Where does the heat go?", a_heat, dict(heat=2, where=2.5)),
    "datacenter": ("What is an AI data center?", a_datacenter, dict(datacenter=3)),
    "who": ("Who made this?", a_who, dict(who=3)),
}
SUGGEST = ["improve", "pue", "heat", "fc", "overheat", "bill"]


def rank(q):
    """Topics ordered by how well they match the question: [(score, key), ...]."""
    c = concepts(q)
    out = []
    for key, (_, _, w) in TOPICS.items():
        sc = sum(v for k, v in w.items() if k in c)
        out.append((sc, key))
    out.sort(key=lambda t: -t[0])
    return out, c


def answer(q, day):
    """Return dict(text, topic, sure, alternatives). `alternatives` are topic
    keys to offer when the match is weak."""
    r, c = rank(q)
    (s1, k1), (s2, k2) = r[0], r[1]
    alts = [k for s, k in r[1:4] if s > 0]
    if s1 < 2:
        return dict(text=None, topic=None, sure=False, alternatives=[k for _, k in r[:3] if _ > 0] or SUGGEST[:3])
    # a general "what should I change" loses to any specific topic that was named
    if k1 == "improve" and s2 >= 3:
        k1 = k2
    S = stats(day)
    return dict(text=TOPICS[k1][1](day, S, c), topic=k1, sure=s1 >= 3 and s1 > s2, alternatives=alts)
