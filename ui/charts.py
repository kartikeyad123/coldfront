"""
charts.py - Plotly figures in the app's dark theme. Visualization only.
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import CoolProp.CoolProp as CP

CYAN, MAG, AMBER, RED, GREEN, GREY, TXT = "#6FA8DC", "#D9A441", "#C77B4A", "#E06A50", "#8FB39A", "#8A929C", "#E6E8EB"
WARM_C = MAG
C2K = 273.15


def _style(fig, h=360, title=None):
    fig.update_layout(
        height=h, template="plotly_dark", paper_bgcolor="#151A21", plot_bgcolor="#151A21",
        font=dict(family="IBM Plex Mono, monospace", size=11, color=TXT),
        margin=dict(l=50, r=20, t=40 if title else 20, b=78),
        title=dict(text=title, font=dict(family="Inter, sans-serif", size=14, color=TXT), x=0.01),
        legend=dict(orientation="h", y=-0.18, yanchor="top", x=0, font=dict(size=10)),
        hovermode="x unified")
    fig.update_xaxes(gridcolor="#2A313B", zeroline=False)
    fig.update_yaxes(gridcolor="#2A313B", zeroline=False)
    return fig


def _hours(fig):
    fig.update_xaxes(tickvals=list(range(0, 25, 3)), ticktext=[f"{h:02d}:00" for h in range(0, 25, 3)])


def power_chart(day):
    x = day.series
    t = x["hour"]
    fig = go.Figure()
    for k, name, c in (("Q_it", "IT (servers)", "#3A4350"), ("W_comp", "Compressors", MAG),
                       ("P_aux", "Pumps + fans", AMBER), ("P_over", "Electrical losses", GREY)):
        y = (x["P_chw"] + x["P_cw"] + x["P_fans"] + x["P_crah"]) if k == "P_aux" else x[k]
        fig.add_trace(go.Scatter(x=t, y=y / 1e6, name=name, stackgroup="p", line=dict(width=0.5, color=c)))
    fig.update_yaxes(title="power [MW]")
    _hours(fig)
    return _style(fig, title="Where the electricity goes")


def temperature_chart(day):
    x, s = day.series, day.settings
    t = x["hour"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=x["T_db"], name="outdoor dry-bulb", line=dict(color=AMBER, width=1.5)))
    fig.add_trace(go.Scatter(x=t, y=x["T_wb"], name="outdoor wet-bulb", line=dict(color=AMBER, dash="dot", width=1.5)))
    fig.add_trace(go.Scatter(x=t, y=x["T_inlet"], name="coolant to GPUs" if s.rack_cooling == "liquid" else "server inlet",
                             line=dict(color=CYAN, width=2.5)))
    fig.add_trace(go.Scatter(x=t, y=x["T_cond"], name="condensing T", line=dict(color=MAG, width=1)))
    fig.add_hline(y=s.T_limit_C, line=dict(color=RED, dash="dash", width=1),
                  annotation_text=f"{s.T_limit_C:g} °C limit", annotation_font_color=RED)
    fig.update_yaxes(title="temperature [°C]")
    _hours(fig)
    return _style(fig, title="Temperatures")


def sources_chart(day):
    x = day.series
    t = x["hour"]
    fig = go.Figure()
    for k, name, c in (("Q_fc", "free cooling", CYAN), ("Q_dis", "storage tank", GREEN),
                       ("Q_ch", "chillers", MAG), ("shortfall", "unmet", RED)):
        fig.add_trace(go.Scatter(x=t, y=x[k] / 1e6, name=name, stackgroup="c", line=dict(width=0.5, color=c)))
    fig.add_trace(go.Scatter(x=t, y=x["Q_it"] / 1e6, name="IT heat", line=dict(color="#FFFFFF", width=1.2, dash="dot")))
    fig.update_yaxes(title="cooling [MW]")
    _hours(fig)
    return _style(fig, title="Who carries the heat")


def money_chart(day):
    x, s = day.series, day.settings
    t = x["hour"]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=t, y=x["price"], name="grid price [$/MWh]", line=dict(color=AMBER, shape="hv")), secondary_y=False)
    fig.add_trace(go.Scatter(x=t, y=x["P_cool"] / 1e6 * x["price"], name="cooling cost rate [$/h]",
                             line=dict(color=MAG)), secondary_y=False)
    if s.tank:
        fig.add_trace(go.Scatter(x=t, y=100 * x["soc"], name="tank charge [%]", line=dict(color=GREEN, width=2)),
                      secondary_y=True)
    else:
        fig.add_trace(go.Scatter(x=t, y=x["pue"], name="PUE", line=dict(color=CYAN, width=2)), secondary_y=True)
    fig.update_yaxes(title_text="$/MWh  ·  $/h", secondary_y=False)
    fig.update_yaxes(title_text="tank [%]" if s.tank else "PUE", secondary_y=True, showgrid=False)
    _hours(fig)
    return _style(fig, title="Price, cost and " + ("storage" if s.tank else "PUE"))


# ---------------------------------------------------------------- cycle diagrams
def _dome(fluid, prop_x, prop_y):
    Tc = CP.PropsSI("Tcrit", fluid)
    Tt = max(CP.PropsSI("Tmin", fluid), 230.0)
    T = np.linspace(Tt, Tc - 0.05, 120)
    xl = [CP.PropsSI(prop_x, "T", Ti, "Q", 0, fluid) for Ti in T]
    xv = [CP.PropsSI(prop_x, "T", Ti, "Q", 1, fluid) for Ti in T]
    yl = [CP.PropsSI(prop_y, "T", Ti, "Q", 0, fluid) for Ti in T]
    yv = [CP.PropsSI(prop_y, "T", Ti, "Q", 1, fluid) for Ti in T]
    return xl + xv[::-1], yl + yv[::-1]


def _cycle_path(cyc, kind):
    """Points along the cycle for plotting, with the real curved paths in the
    condenser (desuperheat, condense, subcool) and evaporator."""
    f = cyc.fluid
    h1, h2, h3, h4 = cyc.h
    s1, s2, s3, s4 = cyc.s
    P_e, P_c = cyc.P_evap, cyc.P_cond
    # condenser: 2 -> 3 at P_c
    hs = np.linspace(h2, h3, 40)
    Ts_c = [CP.PropsSI("T", "P", P_c, "H", h, f) for h in hs]
    ss_c = [CP.PropsSI("S", "P", P_c, "H", h, f) for h in hs]
    # evaporator: 4 -> 1 at P_e
    he = np.linspace(h4, h1, 30)
    Ts_e = [CP.PropsSI("T", "P", P_e, "H", h, f) for h in he]
    ss_e = [CP.PropsSI("S", "P", P_e, "H", h, f) for h in he]
    if kind == "ph":
        x = [h1, h2] + list(hs) + [h4] + list(he)
        y = [P_e, P_c] + [P_c] * len(hs) + [P_e] + [P_e] * len(he)
        return np.array(x) / 1e3, np.array(y) / 1e3
    T1, T2 = cyc.T[0], cyc.T[1]
    x = [s1, s2] + ss_c + [s4] + ss_e
    y = [T1, T2] + Ts_c + [cyc.T[3]] + Ts_e
    return np.array(x) / 1e3, np.array(y) - C2K


def ph_diagram(cyc):
    dx, dy = _dome(cyc.fluid, "H", "P")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.array(dx) / 1e3, y=np.array(dy) / 1e3, name="saturation dome",
                             line=dict(color=GREY, width=1.2)))
    x, y = _cycle_path(cyc, "ph")
    fig.add_trace(go.Scatter(x=x, y=y, name="cycle", line=dict(color=CYAN, width=3)))
    pts_x = np.array(cyc.h) / 1e3
    pts_y = np.array([cyc.P_evap, cyc.P_cond, cyc.P_cond, cyc.P_evap]) / 1e3
    fig.add_trace(go.Scatter(x=pts_x, y=pts_y, mode="markers+text", text=["1", "2", "3", "4"],
                             textposition=["bottom right", "top right", "top left", "bottom left"],
                             marker=dict(size=10, color=MAG), textfont=dict(size=14, color="#FFFFFF"),
                             showlegend=False))
    fig.update_yaxes(type="log", title="pressure P [kPa]")
    fig.update_xaxes(title="specific enthalpy h [kJ/kg]")
    return _style(fig, h=360, title="P–h diagram")


def ts_diagram(cyc):
    dx, dy = _dome(cyc.fluid, "S", "T")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.array(dx) / 1e3, y=np.array(dy) - C2K, name="saturation dome",
                             line=dict(color=GREY, width=1.2)))
    x, y = _cycle_path(cyc, "ts")
    fig.add_trace(go.Scatter(x=x, y=y, name="cycle", line=dict(color=MAG, width=3)))
    fig.add_trace(go.Scatter(x=np.array(cyc.s) / 1e3, y=np.array(cyc.T) - C2K, mode="markers+text",
                             text=["1", "2", "3", "4"], textposition=["bottom right", "top right", "top left", "bottom left"],
                             marker=dict(size=10, color=CYAN), textfont=dict(size=14, color="#FFFFFF"),
                             showlegend=False))
    fig.update_yaxes(title="temperature T [°C]")
    fig.update_xaxes(title="specific entropy s [kJ/(kg·K)]")
    return _style(fig, h=360, title="T–s diagram")


def ab_chart(day_a, day_b, key, label, scale=1.0):
    fig = go.Figure()
    for d, name, c in ((day_a, "A", CYAN), (day_b, "B", MAG)):
        fig.add_trace(go.Scatter(x=d.series["hour"], y=d.series[key] * scale, name=f"Plan {name}",
                                 line=dict(color=c, width=2)))
    fig.update_yaxes(title=label)
    _hours(fig)
    return _style(fig, h=280, title=label)


# ---------------------------------------------------------------- animated cycle through the day
def cycle_day_animation(day, kind="ph", every_h=1.0):
    """The refrigeration cycle on the P-h or T-s diagram, animated through the
    day: the four state points move as the lift and the load change."""
    from coldfront.chiller import solve_cycle
    x, s = day.series, day.settings
    dt_h = x["hour"][1] - x["hour"][0]
    step = max(1, int(round(every_h / dt_h)))
    idx = [k for k in range(0, len(x["hour"]), step) if x["n_on"][k] > 0]
    if not idx:
        return None
    px, py = ("H", "P") if kind == "ph" else ("S", "T")
    dx, dy = _dome(s.fluid, px, py)
    dome_x = np.array(dx) / 1e3
    dome_y = np.array(dy) / 1e3 if kind == "ph" else np.array(dy) - C2K

    def traces(k):
        c = solve_cycle(s.fluid, x["T_evap"][k] + C2K, x["T_cond"][k] + C2K, float(x["eta"][k]), s.superheat, s.subcool)
        cx, cy = _cycle_path(c, kind)
        if kind == "ph":
            ptx, pty = np.array(c.h) / 1e3, np.array([c.P_evap, c.P_cond, c.P_cond, c.P_evap]) / 1e3
        else:
            ptx, pty = np.array(c.s) / 1e3, np.array(c.T) - C2K
        return [go.Scatter(x=cx, y=cy, mode="lines", line=dict(color=WARM_C, width=2.5), name="cycle"),
                go.Scatter(x=ptx, y=pty, mode="markers+text", text=["1", "2", "3", "4"],
                           textposition=["bottom right", "top right", "top left", "bottom left"],
                           marker=dict(size=9, color=TXT), textfont=dict(size=13, color=TXT), showlegend=False)]

    lab = lambda k: f"{int(x['hour'][k]):02d}:{int(round((x['hour'][k] % 1) * 60)):02d}"
    k0 = idx[len(idx) // 2]
    fig = go.Figure(
        data=[go.Scatter(x=dome_x, y=dome_y, mode="lines", line=dict(color=GREY, width=1), name="saturation dome")] + traces(k0),
        frames=[go.Frame(data=traces(k), traces=[1, 2], name=lab(k)) for k in idx])
    if kind == "ph":
        fig.update_yaxes(type="log", title="pressure P [kPa]", range=[np.log10(150), np.log10(3000)])
        fig.update_xaxes(title="specific enthalpy h [kJ/kg]", range=[180, 470])
    else:
        fig.update_yaxes(title="temperature T [°C]", range=[-15, 70])
        fig.update_xaxes(title="specific entropy s [kJ/(kg·K)]", range=[1.0, 1.85])
    _style(fig, h=400, title=("P–h" if kind == "ph" else "T–s") + " diagram through the day")
    fig.update_layout(
        hovermode=False, margin=dict(l=50, r=20, t=40, b=110), showlegend=False,
        updatemenus=[dict(type="buttons", x=0.0, y=-0.32, xanchor="left", showactive=False, bgcolor="#151A21",
                          font=dict(color=TXT), buttons=[
                              dict(label="Play", method="animate", args=[None, dict(frame=dict(duration=350, redraw=False), fromcurrent=True, transition=dict(duration=250))]),
                              dict(label="Pause", method="animate", args=[[None], dict(frame=dict(duration=0), mode="immediate")])])],
        sliders=[dict(x=0.2, len=0.8, y=-0.22, currentvalue=dict(prefix="time ", font=dict(size=11)), pad=dict(t=0),
                      active=len(idx) // 2,
                      steps=[dict(method="animate", label=lab(k), args=[[lab(k)], dict(mode="immediate", frame=dict(duration=0, redraw=False), transition=dict(duration=0))]) for k in idx])])
    return fig


def margin_chart(day):
    """Margin to the service limit through the day (positive = safe)."""
    x = day.series
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x["hour"], y=x["T_limit"] - x["T_inlet"], name="margin to limit [K]", line=dict(color=CYAN, width=2)))
    fig.add_hline(y=0, line=dict(color=RED, width=1, dash="dash"))
    fig.update_yaxes(title="margin to limit [K]")
    _hours(fig)
    return _style(fig, h=280, title="Safety margin")
