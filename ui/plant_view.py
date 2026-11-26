"""
plant_view.py - Animated plant schematic (SVG + JavaScript) rendered inside the
Streamlit page. Pure visualization: it plays back a day that the model has
already solved. No physics here, only the entropy bookkeeping needed to show
S_gen per device from quantities the model stored.

Click any piece of equipment to open its engineering panel: live numbers at the
current time, the governing equation and whether the device is solved as
steady-state steady-flow (SSSF) or as a transient control volume.
"""

import json
import numpy as np

CP_W = 4186.0


def frames_from_day(day, every_s=300):
    """Down-sample the day result to one frame every `every_s` seconds."""
    x, s = day.series, day.settings
    dt = (x["hour"][1] - x["hour"][0]) * 3600 if len(x["hour"]) > 1 else 30.0
    step = max(1, int(round(every_s / dt)))
    idx = np.arange(0, len(x["hour"]), step)
    if idx[-1] != len(x["hour"]) - 1:
        idx = np.append(idx, len(x["hour"]) - 1)

    def col(k, scale=1.0, nd=3):
        v = np.nan_to_num(np.asarray(x[k], dtype=float)[idx] * scale, nan=0.0)
        return [round(float(a), nd) for a in v]

    # entropy generated in each cycle device (kW/K), from stored state points and water streams
    m = x["m_ref"]
    Tco = s.T_chws
    Qe = x["Q_ch"] + x["Q_chg"]
    with np.errstate(divide="ignore", invalid="ignore"):
        Tci = Tco + np.where(x["m_chw"] > 0, Qe / (x["m_chw"] * CP_W), 0.0)
        Tecw = np.maximum(x["T_sink"] + 273.15, s.T_ecw_min_C + 273.15)
        m_c = x["Q_cond"] / (CP_W * s.dT_cw)
        sg_comp = m * (x["s2"] - x["s1"])
        sg_valve = m * (x["s4"] - x["s3"])
        sg_evap = m * (x["s1"] - x["s4"]) + x["m_chw"] * CP_W * np.log(Tco / np.maximum(Tci, 1.0))
        sg_cond = m * (x["s3"] - x["s2"]) + m_c * CP_W * np.log((Tecw + s.dT_cw) / Tecw)
    sg = lambda a: [round(float(v), 3) for v in np.nan_to_num(a[idx] / 1e3)]

    return dict(
        hour=col("hour"), Tdb=col("T_db", nd=1), Twb=col("T_wb", nd=1), it=col("Q_it", 1e-6, 2),
        itreq=col("Q_it_req", 1e-6, 2), thr=col("throttle"), Tin=col("T_inlet", nd=2), lim=col("T_limit", nd=1),
        soc=col("soc"), mcold=col("m_cold", 1e-3, 0), ffc=col("f_fc"),
        non=[int(v) for v in x["n_on"][idx]], nav=[int(v) for v in x["n_avail"][idx]], plr=col("plr"),
        cop=col("cop", nd=2), copc=col("cop_cycle", nd=2), car=col("cop_carnot", nd=2), eta=col("eta"), xm=col("x_map", nd=2),
        Te=col("T_evap", nd=1), Tc=col("T_cond", nd=1), Pe=col("P_evap", 1e-3, 0), Pc=col("P_cond", 1e-3, 0),
        mref=col("m_ref", nd=1), ae=col("approach_evap", nd=2), ac=col("approach_cond", nd=2),
        pue=col("pue"), price=col("price", nd=0), qfc=col("Q_fc", 1e-6, 2), qch=col("Q_ch", 1e-6, 2),
        qdis=col("Q_dis", 1e-6, 2), qchg=col("Q_chg", 1e-6, 2), qrej=col("Q_rej", 1e-6, 2),
        water=col("water", 3.6, 2), evap=col("evaporation", 3.6, 2), drift=col("drift", 3.6, 3), blow=col("blowdown", 3.6, 2),
        arej=col("approach_rej", nd=1), Tsink=col("T_sink", nd=1),
        ptot=col("P_total", 1e-6, 2), wcomp=col("W_comp", 1e-3, 0), short=col("shortfall", 1e-6, 2),
        pchw=col("P_chw", 1e-3, 0), pcw=col("P_cw", 1e-3, 0), mchw=col("m_chw", nd=0), mcw=col("m_cw", nd=0),
        pfan=col("P_fans", 1e-3, 0), qloop=col("Q_loop", 1e-6, 3),
        sgc=sg(sg_comp), sgk=sg(sg_cond), sgv=sg(sg_valve), sge=sg(sg_evap),
    )


def plant_html(day, autoplay=False, start="hot", focus="chiller", compact=False, fx=None):
    """fx: optional dict(head=str, items=[dict(dev=..., text=...)]) describing what
    a change of settings did; the named equipment is lit when the drawing opens."""
    s = day.settings
    data = frames_from_day(day)
    ev = [dict(t=e.t, until=e.until, title=e.title, text=e.text, kind=e.kind) for e in getattr(day, "events", ())]
    cfg = dict(nch=s.n_installed, tank=bool(s.tank), mode=s.rejection, limit=s.T_limit_C,
               thr=s.T_throttle, target=s.T_chws_C + s.approach_rack, liquid=s.rack_cooling == "liquid",
               chws=s.T_chws_C, dT=s.dT_chw, dTcw=s.dT_cw, events=ev, autoplay=autoplay, start=start, focus=focus, compact=compact,
               tankt=round(s.tank_mass / 1e3), tankMWh=s.tank_MWh, cap=s.chiller_cap_MW, fc=bool(s.free_cooling),
               hx=s.hx_approach, mchwd=round(s.Q_design / (CP_W * 6.0), 1), mcwd=round(1.17 * s.Q_design / (CP_W * 5.0), 1),
               dP=s.dP_chw_kPa, peff=s.pump_eff, pmeff=s.pump_motor_eff, stat=s.static_head_frac, fx=fx,
               qd=round(s.Q_design / 1e6, 3), eta0=s.eta_rated)
    return _TEMPLATE.replace("__DATA__", json.dumps(data)).replace("__CFG__", json.dumps(cfg))


_TEMPLATE = r"""
<div id="pv">
<style>
 @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600&display=swap');
 html,body{margin:0;background:transparent}
 #pv{width:100%;font-family:'Inter',sans-serif;color:#E6E8EB}
 #pv svg text{font-family:'Inter',sans-serif}
 #pv svg .num{font-family:'IBM Plex Mono',monospace}
 #pv svg .lab{font-size:12.5px;letter-spacing:.12em;fill:#A3ABB5;text-transform:uppercase}
 #pv svg .pl{font-size:13.5px;fill:#B4BAC2}
 #pv .dev,#pv .pipe{cursor:pointer}
 #pv [data-part]{transition:opacity .25s}
 #pv .dev .frame{transition:stroke .2s}
 #pv .dev:hover .frame{stroke-width:2}
 #pv .dev.sel .frame{stroke-width:2.2}
 #pv .glow{animation:glow 1.1s ease-in-out infinite alternate}
 #pv .flash{animation:flash .9s ease-out 1}
 @keyframes glow{from{filter:drop-shadow(0 0 1px #E6E8EB)}to{filter:drop-shadow(0 0 9px #E6E8EB)}}
 @keyframes flash{from{filter:drop-shadow(0 0 14px #6FA8DC)}to{filter:none}}
 #pv .sdot.pulse{animation:pulse .9s ease-in-out infinite alternate}
 @keyframes pulse{from{opacity:1}to{opacity:.25}}
 @media (prefers-reduced-motion: reduce){#pv .glow,#pv .flash,#pv .sdot.pulse{animation:none}}
 #pv .modes{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px;font-size:13px;color:#A3ABB5}
 #pv button{background:#151A21;color:#E6E8EB;border:1px solid #2A313B;padding:6px 14px;font-family:inherit;
   cursor:pointer;border-radius:6px;font-size:13px}
 #pv button:hover{border-color:#E6E8EB}
 #pv button.on{border-color:#6FA8DC;color:#6FA8DC;background:#18232F}
 #pv .modes label{margin-left:auto;display:flex;gap:6px;align-items:center;cursor:pointer;color:#E6E8EB}
 #pv .modes input{accent-color:#6FA8DC;width:15px;height:15px}
 #conn{display:none;background:#18232F;border:1px solid #6FA8DC;border-radius:6px;padding:10px 14px;margin-bottom:8px;font-size:13.5px;line-height:1.5}
 #conn b{color:#6FA8DC} #conn .flow{color:#B4BAC2;font-family:'IBM Plex Mono',monospace;font-size:12.5px;margin-top:4px}
 #fx{display:none;background:#151A21;border:1px solid #D9A441;border-radius:6px;padding:10px 14px;margin-bottom:8px;font-size:13.5px;line-height:1.5}
 #fx .h{color:#D9A441;font-weight:600;margin-bottom:6px}
 #fx .chain{display:flex;flex-wrap:wrap;gap:6px;align-items:stretch}
 #fx .chip{border:1px solid #2A313B;border-radius:6px;padding:6px 10px;max-width:300px;cursor:default;background:#0E1116}
 #fx .chip:hover{border-color:#E6E8EB}
 #fx .chip b{display:block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#6FA8DC;font-weight:600}
 #fx .arrow{align-self:center;color:#8A929C}
 #pv .bar{display:grid;grid-template-columns:auto auto 1fr;gap:12px;align-items:start;margin-top:8px}
 #pv input[type=range]{width:100%;accent-color:#E6E8EB;margin:8px 0 0 0}
 #pv select{background:#151A21;color:#E6E8EB;border:1px solid #2A313B;font-family:inherit;padding:6px;border-radius:6px;font-size:13px}
 #tl{position:relative;height:92px;margin-top:2px}
 #tl svg{position:absolute;left:0;top:0;width:100%;height:26px}
 #tl .cur{position:absolute;top:0;width:1px;height:26px;background:#E6E8EB}
 #tl .mk{position:absolute;transform:translateX(-50%);font-size:11px;white-space:nowrap;cursor:pointer;color:#B4BAC2;padding-top:5px}
 #tl .mk:before{content:"";position:absolute;left:50%;top:-2px;width:2px;height:6px;background:currentColor}
 #tl .mk:hover{color:#E6E8EB;text-decoration:underline}
 #tl .key{position:absolute;right:0;top:74px;font-size:10.5px;color:#8A929C}
 #panel{margin-top:8px;background:#151A21;border:1px solid #2A313B;border-radius:6px;padding:12px 16px;display:grid;
   grid-template-columns:230px 1fr 300px;gap:18px;min-height:128px}
 @media (max-width: 820px){#panel{grid-template-columns:1fr} #panel .grid{grid-template-columns:repeat(2,1fr)} #panel .glance{grid-template-columns:repeat(2,1fr)}}
 #panel h4{margin:0 0 4px 0;font-size:15px;font-weight:600}
 #panel .badge{font-family:'IBM Plex Mono',monospace;font-size:11px;border:1px solid #2A313B;border-radius:3px;padding:1px 7px;color:#B4BAC2}
 #panel .why{color:#A3ABB5;font-size:13px;line-height:1.45;margin-top:8px}
 #panel .glance{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-bottom:10px}
 #panel .gl{background:#0E1116;border:1px solid #2A313B;border-radius:6px;padding:6px 8px}
 #panel .gl span{display:block;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:#8A929C}
 #panel .gl b{font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:500}
 #panel .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:4px 18px;align-content:start}
 #panel .kv{display:flex;justify-content:space-between;gap:10px;font-size:12.5px;border-bottom:1px solid #20262E;padding:3px 0}
 #panel .kv span:first-child{color:#8A929C}
 #panel .kv span:last-child{font-family:'IBM Plex Mono',monospace;text-align:right}
 #svwrap{overflow-x:auto}
 #svwrap svg{min-width:720px}
 #panel .eq{font-family:'IBM Plex Mono',monospace;font-size:12px;color:#B4BAC2;line-height:1.7}
 #panel .eqh{color:#8A929C;font-size:11px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:4px}
 #wfbox{margin-top:10px;border-top:1px solid #2A313B;padding-top:8px}
 #wfout{font-size:12.5px;line-height:1.6;color:#B4BAC2} #wfout b{font-family:'IBM Plex Mono',monospace;color:#E6E8EB;font-weight:500}
</style>
<div id="fx"></div>
<div class="modes" id="modes">
 <span>Show</span>
 <button data-m="all" class="on">Whole plant</button>
 <button data-m="collect">Heat collection loop</button>
 <button data-m="reject">Heat rejection loop</button>
 <label><input type="checkbox" id="explore"/> Explore connections (click a part)</label>
</div>
<div id="conn"></div>
<div id="svwrap"><svg id="sv" viewBox="0 0 1200 636" width="100%" style="background:#0E1116;border:1px solid #2A313B;border-radius:6px">
 <rect id="alert_bg" x="0" y="0" width="1200" height="26" fill="#E06A50" opacity="0"/>
 <text id="alert_tx" x="600" y="18" text-anchor="middle" font-size="14" font-weight="600" fill="#0E1116"></text>
 <text x="24" y="52" class="lab">Outside</text>
 <text id="hud_out" x="24" y="76" font-size="16" class="num" fill="#E6E8EB">--</text>
 <text id="clock" x="600" y="74" text-anchor="middle" font-size="30" class="num" fill="#E6E8EB">00:00</text>
 <text x="1176" y="52" text-anchor="end" class="lab">Grid price</text>
 <text id="hud_price" x="1176" y="76" text-anchor="end" font-size="16" class="num" fill="#E6E8EB">--</text>
 <g id="pgauge"><text x="318" y="52" class="lab">Cooling power</text>
  <text id="pg_v" x="318" y="76" font-size="16" class="num" fill="#E6E8EB">--</text>
  <rect x="426" y="64" width="92" height="9" rx="4.5" fill="#151A21" stroke="#2A313B"/><rect id="pg_b" x="426" y="64" width="0" height="9" rx="4.5" fill="#6FA8DC"/></g>
 <g id="hgauge"><text x="700" y="52" class="lab">Heat to remove</text>
  <text id="hg_v" x="700" y="76" font-size="16" class="num" fill="#E6E8EB">--</text>
  <rect x="808" y="64" width="92" height="9" rx="4.5" fill="#151A21" stroke="#2A313B"/><rect id="hg_b" x="808" y="64" width="0" height="9" rx="4.5" fill="#D9A441"/></g>
 <line x1="24" y1="92" x2="1176" y2="92" stroke="#20262E"/>

 <!-- pipes, each drawn in its flow direction -->
 <g id="pipes"></g>
 <text id="lab_sup" x="660" y="204" class="pl">cold supply</text>
 <text id="lab_ret" x="424" y="470" class="pl">warm return</text>
 <text id="lab_heat" x="850" y="468" text-anchor="end" class="pl" fill="#D9A441">--</text>

 <!-- heat rejection -->
 <g class="dev" data-dev="tower" data-part="tower">
  <rect x="62" y="110" width="206" height="270" fill="transparent"/>
  <g id="tower">
   <path class="frame" d="M84 300 L108 150 L222 150 L246 300 Z" fill="#151A21" stroke="#4A525E" stroke-width="1.2"/>
   <line x1="100" y1="200" x2="230" y2="200" stroke="#2A313B"/><line x1="92" y1="250" x2="238" y2="250" stroke="#2A313B"/>
   <g id="plume" opacity="0.4"><path d="M130 142 q10 -22 0 -40 M165 142 q12 -26 0 -46 M200 142 q10 -22 0 -40" stroke="#B4BAC2" stroke-width="1.4" fill="none"/></g>
  </g>
  <g id="dry">
   <rect class="frame" x="74" y="170" width="182" height="110" fill="#151A21" stroke="#4A525E" stroke-width="1.2"/>
   <g id="dryfans"></g>
  </g>
  <circle class="sdot" cx="250" cy="130" r="5"/>
  <text id="rej_name" x="165" y="326" text-anchor="middle" class="lab">Cooling tower</text>
  <text id="hud_water" x="165" y="346" text-anchor="middle" font-size="14" class="num" fill="#B4BAC2">--</text>
  <text id="hud_rej" x="165" y="366" text-anchor="middle" font-size="13.5" fill="#D9A441">--</text>
 </g>

 <!-- chillers -->
 <g class="dev" data-dev="chiller" data-part="chiller">
  <rect x="330" y="100" width="320" height="185" fill="transparent"/>
  <text x="490" y="118" text-anchor="middle" class="lab">Chillers · refrigeration cycle</text>
  <g id="chillers"></g>
 </g>
 <!-- pumps -->
 <g class="dev" data-dev="pump_cw" data-part="pump_cw">
  <circle class="frame" cx="292" cy="215" r="11" fill="#151A21" stroke="#4A525E" stroke-width="1.4"/><path d="M287 210 L299 215 L287 220 Z" fill="#B4BAC2"/>
  <text x="292" y="241" text-anchor="middle" font-size="11.5" fill="#A3ABB5">pump</text>
 </g>
 <g class="dev" data-dev="pump_chw" data-part="pump_chw">
  <circle class="frame" cx="600" cy="480" r="12" fill="#151A21" stroke="#4A525E" stroke-width="1.4"/><path d="M606 474 L593 480 L606 486 Z" fill="#B4BAC2"/>
  <text x="600" y="512" text-anchor="middle" class="lab">Chilled-water pump</text>
 </g>
 <!-- free cooling heat exchanger -->
 <g class="dev" data-dev="fc" data-part="fc">
  <rect class="frame" id="hx" x="345" y="310" width="130" height="50" fill="#151A21" stroke="#4A525E" stroke-width="1.2" rx="3"/>
  <circle class="sdot" cx="466" cy="319" r="4.5"/>
  <text x="402" y="330" text-anchor="middle" class="lab" style="font-size:11.5px">Free cooling</text>
  <text id="hud_fc" x="410" y="350" text-anchor="middle" font-size="13.5" class="num" fill="#B4BAC2">off</text>
 </g>
 <!-- storage tank -->
 <g class="dev" data-dev="tank" data-part="tank" id="tankg_">
  <rect class="frame" x="705" y="272" width="80" height="156" rx="8" fill="#151A21" stroke="#4A525E" stroke-width="1.2"/>
  <rect id="tank_warm" x="708" y="275" width="74" height="150" rx="6" fill="#D9A441" opacity="0.28"/>
  <rect id="tank_cold" x="708" y="275" width="74" height="150" rx="6" fill="#6FA8DC" opacity="0.75"/>
  <circle class="sdot" cx="776" cy="282" r="4.5"/>
  <text x="694" y="340" text-anchor="end" class="lab">Storage</text>
  <text id="hud_tank" x="694" y="359" text-anchor="end" font-size="14" class="num" fill="#B4BAC2">--</text>
 </g>
 <!-- data hall -->
 <g class="dev" data-dev="hall" data-part="hall">
  <rect class="frame" x="860" y="110" width="316" height="405" fill="#12161C" stroke="#4A525E" stroke-width="1.2" rx="3"/>
  <circle class="sdot" cx="1162" cy="124" r="5"/>
  <text x="1018" y="132" text-anchor="middle" class="lab">AI data hall</text>
  <g id="racks"></g>
  <g id="heat"></g>
  <text id="hud_inlet" x="1018" y="446" text-anchor="middle" font-size="24" class="num" fill="#6FA8DC">--</text>
  <text id="inlet_lab" x="1018" y="466" text-anchor="middle" font-size="13.5" fill="#A3ABB5">server inlet air</text>
  <text id="hud_it" x="1018" y="495" text-anchor="middle" font-size="14" class="num" fill="#B4BAC2">--</text>
 </g>

 <!-- gauges -->
 <text x="24" y="420" class="lab">PUE now</text>
 <text id="hud_pue" x="24" y="450" font-size="26" class="num" fill="#E6E8EB">--</text>
 <text x="24" y="482" class="lab">Chiller COP</text>
 <text id="hud_cop" x="24" y="508" font-size="20" class="num" fill="#E6E8EB">--</text>
 <line x1="24" y1="532" x2="1176" y2="532" stroke="#20262E"/>
 <text x="24" y="562" class="lab">Who carries the heat</text>
 <rect x="236" y="550" width="524" height="14" fill="#151A21" stroke="#2A313B"/>
 <rect id="mix_fc" x="236" y="550" width="0" height="14" fill="#6FA8DC"/>
 <rect id="mix_tk" x="236" y="550" width="0" height="14" fill="#8FB39A"/>
 <rect id="mix_ch" x="236" y="550" width="0" height="14" fill="#D9A441"/>
 <rect id="mix_sh" x="236" y="550" width="0" height="14" fill="#E06A50"/>
 <text x="775" y="562" font-size="13.5" fill="#B4BAC2"><tspan fill="#6FA8DC">■</tspan> outside air  <tspan fill="#8FB39A" dx="8">■</tspan> storage  <tspan fill="#D9A441" dx="8">■</tspan> chillers  <tspan fill="#E06A50" dx="8">■</tspan> unmet</text>
 <text id="hud_power" x="236" y="587" font-size="13.5" class="num" fill="#A3ABB5">--</text>
 <g id="legend">
  <text x="24" y="618" class="lab">Equipment state</text>
  <text x="236" y="618" font-size="13.5" fill="#B4BAC2"><tspan fill="#6FA8DC">●</tspan> normal  <tspan fill="#A78BDA" dx="10">●</tspan> high demand  <tspan fill="#D97B3F" dx="10">●</tspan> inefficient  <tspan fill="#E06A50" dx="10">●</tspan> critical  <tspan fill="#6B7380" dx="10">●</tspan> offline</text>
  <text id="clickhint" x="1176" y="618" text-anchor="end" font-size="13.5" fill="#6FA8DC">click any equipment or pipe for details</text>
 </g>
</svg></div>
<div class="bar" id="bar">
 <button id="play">Play day</button>
 <select id="speed"><option value="160">1×</option><option value="70" selected>2×</option><option value="25">5×</option></select>
 <div><input id="scrub" type="range" min="0" max="0" value="0"/>
  <div id="tl"><span class="key">grey: heat load · blue: hall temperature · click a marker to jump</span><svg viewBox="0 0 1000 26" preserveAspectRatio="none"><path id="tl_it" fill="#2A313B"/><path id="tl_T" fill="none" stroke="#6FA8DC" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg><div class="cur" id="tl_cur"></div><div id="tl_m"></div></div>
 </div>
</div>
<div id="panel"><div id="p_left"></div><div id="p_mid"></div><div id="p_right"></div></div>
</div>
<script>
const D = __DATA__, C = __CFG__;
const N = D.hour.length;
const $ = id => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
function el(tag, attrs, parent){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);parent.appendChild(e);return e;}
const SC={normal:"#6FA8DC",high:"#A78BDA",ineff:"#D97B3F",crit:"#E06A50",off:"#6B7380",idle:"#4A525E"};
const RANK={crit:5,ineff:4,high:3,normal:2,idle:1,off:0};
const COLD="#6FA8DC", WARM="#D9A441", GREY="#8A929C";

// ---------------------------------------------------------------- pipes
const PIPES = {
 p_cw:  {d:"M250 215 H335", c:"#7F9FB5", w:3,   arr:[[320,215,0]], name:"Condenser water to the chillers", what:"Water the tower has cooled. It flows to the chiller condensers to pick up heat."},
 p_cw2: {d:"M335 255 H250", c:"#B08A5A", w:3,   arr:[[292,255,180]], name:"Condenser water back to the tower", what:"The same water, now carrying the chillers' heat (cooling load plus compressor work) back to the tower."},
 p_cwfc:{d:"M312 215 V335 H345", c:"#7F9FB5", w:2, arr:[[312,285,90]], name:"Tower water to the free-cooling exchanger", what:"When the tower water is colder than the return water, some of it goes here and cools the return water directly."},
 p_sup: {d:"M645 215 H820 V310 H860", c:COLD, w:3.5, arr:[[690,215,0],[820,268,90]], name:"Chilled-water supply", what:"Cold water leaving the chillers for the data hall."},
 p_ret: {d:"M860 480 H410 V360", c:WARM, w:3.5, arr:[[790,480,180],[505,480,180],[410,420,270]], name:"Chilled-water return", what:"The water after it has picked up the servers' heat. It passes the pump and the free-cooling exchanger on its way back."},
 p_ret2:{d:"M410 310 V282", c:WARM, w:3.5, arr:[[410,297,270]], name:"Return water into the chillers", what:"Whatever heat free cooling did not remove goes into the chiller evaporators here."},
 p_tk1: {d:"M745 215 V272", c:COLD, w:2, arr:[], name:"Tank, cold side", what:"Cold water into the tank when charging, out of it when discharging."},
 p_tk2: {d:"M745 428 V480", c:WARM, w:2, arr:[], name:"Tank, warm side", what:"Warm return water takes the place of the cold water that leaves the tank."},
};
for(const id in PIPES){ const p=PIPES[id];
  const g=el("g",{class:"pipe","data-part":id,"data-pipe":id},$("pipes"));
  el("path",{d:p.d,stroke:"transparent","stroke-width":16,fill:"none"},g);
  p.el=el("path",{d:p.d,stroke:p.c,"stroke-width":p.w,fill:"none","stroke-dasharray":"11 8"},g);
  p.arrows=p.arr.map(([x,y,r])=>el("path",{d:"M-5 -6 L5 0 L-5 6",stroke:p.c,"stroke-width":2.2,fill:"none",transform:`translate(${x} ${y}) rotate(${r})`},g));
  p.g=g;
}
// ---------------------------------------------------------------- chillers, fans, racks
const chG=$("chillers"), chUnits=[];
for(let i=0;i<C.nch;i++){
  const x=340+i*78, g=el("g",{},chG);
  const box=el("rect",{class:"frame",x:x,y:130,width:66,height:150,rx:3,fill:"#151A21",stroke:"#4A525E","stroke-width":1.2},g);
  const dot=el("circle",{class:"sdot",cx:x+57,cy:139,r:4},g);
  const snow=el("text",{x:x+10,y:146,"font-size":13,fill:COLD,opacity:0},g); snow.textContent="❄";
  const fanG=el("g",{transform:`translate(${x+33} 176)`},g);
  el("circle",{cx:0,cy:0,r:19,fill:"none",stroke:"#4A525E","stroke-width":1.2},fanG);
  const rot=el("g",{},fanG);
  for(let b=0;b<3;b++) el("path",{d:"M0 0 Q9 -9 17 -3",stroke:"#A9B0BA","stroke-width":1.6,fill:"none",transform:`rotate(${b*120})`},rot);
  el("rect",{x:x+9,y:208,width:48,height:5,fill:"#2A313B"},g);
  const plr=el("rect",{x:x+9,y:208,width:0,height:5,fill:COLD},g);
  const lab=el("text",{x:x+33,y:236,"text-anchor":"middle","font-size":12,fill:"#A3ABB5"},g); lab.textContent="CH-"+(i+1);
  const st=el("text",{x:x+33,y:255,"text-anchor":"middle","font-size":13,fill:"#8A929C",class:"num"},g);
  const st2=el("text",{x:x+33,y:272,"text-anchor":"middle","font-size":9.8,fill:"#8A929C"},g);
  chUnits.push({g,box,dot,snow,rot,plr,st,st2,angle:0,last:""});
}
for(let i=0;i<4;i++){const g=el("g",{transform:`translate(${100+i*43} 225)`},$("dryfans"));el("circle",{r:17,fill:"none",stroke:"#4A525E","stroke-width":1.2},g);const r=el("g",{class:"df"},g);for(let b=0;b<3;b++)el("path",{d:"M0 0 Q8 -8 15 -3",stroke:"#A9B0BA","stroke-width":1.5,fill:"none",transform:`rotate(${b*120})`},r);}
$("tower").style.display = C.mode==="tower" ? "" : "none";
$("dry").style.display = C.mode==="dry" ? "" : "none";
$("rej_name").textContent = C.mode==="tower" ? "Cooling tower" : "Dry cooler";
$("inlet_lab").textContent = C.liquid ? "coolant to GPU cold plates" : "server inlet air";
if(!C.tank){$("tank_cold").style.display="none";$("tank_warm").style.display="none";}
["p_tk1","p_tk2"].forEach(id=>PIPES[id].g.style.display = C.tank ? "" : "none");
const racks=[], heatM=[];
for(let r=0;r<3;r++)for(let c=0;c<8;c++){
  const x=884+c*34.5, y=150+r*88;
  racks.push(el("rect",{x:x,y:y,width:25,height:72,rx:2,fill:COLD,stroke:"#0E1116"},$("racks")));
  if(c%2===0) heatM.push({e:el("path",{d:"M0 0 q4 -5 0 -10 q-4 -5 0 -10",stroke:"#D97B3F","stroke-width":1.3,fill:"none",opacity:0},$("heat")),x:x+12.5,y:y,ph:(r*3+c)*0.17});
}
function mix(p,q,f){return `rgb(${p.map((v,i)=>Math.round(v+(q[i]-v)*f))})`;}
function tempColor(T){ // steel blue (cold) -> ochre (warm, at limit) -> orange (hot). Red is kept for alarms.
  const a=[111,168,220], b=[217,164,65], c=[217,123,63];
  if(T<=C.target) return mix(a,a,0);
  if(T<=C.limit) return mix(a,b,(T-C.target)/Math.max(.1,C.limit-C.target));
  return mix(b,c,Math.min(1,(T-C.limit)/Math.max(.1,C.thr-C.limit)));
}
function hhmm(h){const m=Math.round(h*60);return String(Math.floor(m/60)%24).padStart(2,"0")+":"+String(m%60).padStart(2,"0");}
const f1=v=>v.toFixed(1), f2=v=>v.toFixed(2), f0=v=>Math.round(v).toLocaleString();
const itMax=Math.max(...D.itreq), itMin=Math.min(...D.itreq);
const pcMax=Math.max(1e-6,...D.wcomp.map((w,k)=>(w+D.pchw[k]+D.pcw[k]+D.pfan[k])/1e3));
const mNom=C.qd*1e6/(4186*C.dT), mMax=1.5*Math.max(C.mchwd,mNom);
let i=0, timer=null, dash=0, sel=C.focus||"chiller", mode="all", explore=false, selPipe=null, wf=100, fxUntil=0, fxHover=null;
if(sel==="pumps") sel="pump_chw";

// ---------------------------------------------------------------- equipment state
function unitStatus(k,i){
  if(k>=D.nav[i]) return ["off","offline"];
  if(k>=D.non[i]) return ["idle","standby"];
  if(D.short[i]>0.01) return ["crit","overloaded"];
  if(D.eta[i] < 0.9*C.eta0) return ["ineff","off its best point"];
  if(D.plr[i]>=0.88) return ["high","high demand"];
  return ["normal","running"];
}
function status(dev,i){
  if(dev==="chiller"){ let best=["idle","standby: not needed now"];
    for(let k=0;k<C.nch;k++){const s=unitStatus(k,i); if(RANK[s[0]]>RANK[best[0]]) best=s;}
    if(best[0]==="idle" && D.nav[i]<C.nch) return ["off","one or more offline"];
    return best; }
  if(dev==="tower"){ if(D.qrej[i]<0.01) return ["idle","no heat to reject"];
    if(C.mode==="dry" && D.Tdb[i]>35) return ["ineff","hot air: the chillers must lift heat further"];
    if(D.qrej[i]>1.17*C.qd) return ["high","above its design heat load"]; return ["normal","rejecting heat"]; }
  if(dev==="pump_chw"){ if(D.mchw[i]<1) return ["idle","stopped"]; if(D.mchw[i]>=0.99*mMax) return ["crit","at its flow limit"];
    if(D.mchw[i]>1.1*mNom) return ["high","above design flow"]; return ["normal","running"]; }
  if(dev==="pump_cw"){ if(D.mcw[i]<1) return ["idle","stopped"]; if(D.mcw[i]>1.05*C.mcwd) return ["high","above design flow"]; return ["normal","running"]; }
  if(dev==="fc"){ if(!C.fc) return ["off","switched off"]; if(D.ffc[i]<0.01) return ["idle","waiting for colder tower water"];
    return ["normal",`carrying ${Math.round(D.ffc[i]*100)} % of the load`]; }
  if(dev==="tank"){ if(!C.tank) return ["off","not installed"]; if(D.qdis[i]>0.01) return ["high","discharging"];
    if(D.qchg[i]>0.01) return ["normal","charging"]; return ["idle", D.soc[i]<0.02?"empty":"holding"]; }
  if(dev==="hall"){ if(D.thr[i]<0.999) return ["crit","GPUs throttling"]; if(D.Tin[i]>D.lim[i]+1e-6) return ["ineff","above the temperature limit"];
    if(itMax-itMin>0.8 && D.itreq[i]>=itMax-0.07*(itMax-itMin)) return ["high","peak heat load"]; return ["normal","within limits"]; }
  return ["normal",""];
}
const devG={}; document.querySelectorAll("#pv .dev").forEach(g=>devG[g.dataset.dev]=g);
const lastSt={};
function paintStatus(){
  for(const dev in devG){ const [k,lbl]=status(dev,i), g=devG[dev], col=SC[k];
    if(dev!=="chiller") g.querySelectorAll(".frame").forEach(f=>{f.setAttribute("stroke", col); f.setAttribute("stroke-dasharray", k==="off"?"4 4":"");});
    g.querySelectorAll(":scope > .sdot").forEach(d=>{d.setAttribute("fill",col); d.classList.toggle("pulse", k==="high"||k==="crit");});
    const was=lastSt[dev]; if(was && (was==="idle"||was==="off") && RANK[k]>=2){ g.classList.remove("flash"); void g.getBBox(); g.classList.add("flash"); }
    lastSt[dev]=k; }
}

// ---------------------------------------------------------------- connections
const LOOPS={
 collect:{pipes:["p_sup","p_ret","p_ret2","p_tk1","p_tk2"],devs:["hall","pump_chw","fc","tank","chiller"],
   title:"Heat collection loop (chilled water)",
   text:"Cold water leaves the chillers, picks up the servers' heat in the data hall and comes back warm. The pump keeps it moving. Free cooling and the storage tank sit on this loop."},
 reject:{pipes:["p_cw","p_cw2","p_cwfc"],devs:["tower","pump_cw","chiller","fc"],
   title:"Heat rejection loop (condenser water)",
   text:"This loop carries the heat out. The chillers hand it the cooling load plus their compressor work, and the tower (or dry cooler) gives it to the outside air."},
};
const CONN={
 tower:{pipes:["p_cw","p_cw2","p_cwfc"],devs:["pump_cw","chiller","fc"],up:"chiller condensers (warm water)",down:"condenser-water pump, then the chillers and the free-cooling exchanger",
   text:"The last stop for the heat. Warm water arrives from the chillers, gives its heat to the outside air and leaves cooler."},
 pump_cw:{pipes:["p_cw","p_cw2","p_cwfc"],devs:["tower","chiller","fc"],up:"cooling tower",down:"chiller condensers",
   text:"Moves the condenser water round the heat rejection loop. Without it the chillers could not get rid of their heat."},
 chiller:{pipes:["p_cw","p_cw2","p_sup","p_ret2"],devs:["tower","pump_cw","fc","hall","pump_chw"],up:"return water from the hall (evaporator side)",down:"cold supply to the hall, and warm condenser water to the tower",
   text:"The bridge between the two loops. Its evaporator takes heat out of the chilled water. Its condenser gives that heat, plus the compressor work, to the condenser water."},
 fc:{pipes:["p_ret","p_ret2","p_cwfc"],devs:["tower","hall","chiller","pump_chw"],up:"warm return water from the hall, and cold water from the tower",down:"the chillers, which now have less to do",
   text:"A shortcut for heat. When the tower water is colder than the return water, heat passes straight across with no compressor."},
 pump_chw:{pipes:["p_sup","p_ret","p_ret2"],devs:["hall","fc","chiller"],up:"data hall (warm return water)",down:"free-cooling exchanger, then the chillers, then back to the hall",
   text:"Moves the chilled water round the heat collection loop. Its work ends up as heat in the water, so it adds a little to the cooling load."},
 tank:{pipes:["p_tk1","p_tk2","p_sup","p_ret"],devs:["chiller","hall","pump_chw"],up:"chillers, when charging",down:"data hall, when discharging",
   text:"A store of cold water. Charging takes cold water from the supply line. Discharging sends it to the hall so the chillers can rest."},
 hall:{pipes:["p_sup","p_ret"],devs:["pump_chw","chiller","fc","tank"],up:"cold supply from the chillers (and the tank)",down:"chilled-water pump, free cooling, chillers",
   text:"Where the heat comes from. Almost every watt the GPUs draw becomes heat that the chilled water must carry away."},
};
const NAME={tower:()=>C.mode==="tower"?"Cooling tower":"Dry cooler",pump_cw:()=>"Condenser-water pump",chiller:()=>"Chillers",fc:()=>"Free-cooling exchanger",pump_chw:()=>"Chilled-water pump",tank:()=>"Storage tank",hall:()=>"AI data hall"};
function pipeFlow(id){
  if(id==="p_sup") return `${f0(D.mchw[i])} kg/s at ${f1(C.chws)} °C, towards the data hall`;
  if(id==="p_ret"||id==="p_ret2") return `${f0(D.mchw[i])} kg/s at ${f1(C.chws+C.dT)} °C, towards the chillers, carrying ${f2(D.qloop[i])} MW of heat`;
  if(id==="p_cw") return `${f0(D.mcw[i])} kg/s at ${f1(D.Tsink[i])} °C, towards the chillers`;
  if(id==="p_cw2") return `${f0(D.mcw[i])} kg/s at ${f1(D.Tsink[i]+C.dTcw)} °C, towards the ${C.mode==="tower"?"tower":"dry cooler"}, carrying ${f2(D.qrej[i])} MW of heat`;
  if(id==="p_cwfc") return D.ffc[i]>0.01 ? `in use: moving ${f2(D.qfc[i])} MW with no compressor` : "not in use now";
  return D.qchg[i]>0.01 ? `charging at ${f2(D.qchg[i])} MW` : (D.qdis[i]>0.01 ? `discharging at ${f2(D.qdis[i])} MW` : "no flow now");
}
function activeSet(){
  if(mode!=="all") return LOOPS[mode];
  if(!explore) return null;
  if(selPipe){ const devs=Object.keys(CONN).filter(d=>CONN[d].pipes.includes(selPipe)); return {pipes:[selPipe],devs}; }
  const c=CONN[sel]; return {pipes:c.pipes,devs:[sel].concat(c.devs)};
}
function applyFocus(){
  const a=activeSet(), now=performance.now();
  document.querySelectorAll("#pv [data-part]").forEach(e=>{ const id=e.dataset.part;
    e.style.opacity = !a ? 1 : ((a.pipes.includes(id)||a.devs.includes(id)) ? 1 : 0.13); });
  for(const id in PIPES){ const on = a && a.pipes.includes(id); PIPES[id].el.setAttribute("stroke-width", PIPES[id].w + (on?2:0)); }
  const box=$("conn");
  if(!a){ box.style.display="none"; }
  else { box.style.display="block";
    if(mode!=="all") box.innerHTML=`<b>${LOOPS[mode].title}.</b> ${LOOPS[mode].text}<div class="flow">${mode==="collect"?pipeFlow("p_ret"):pipeFlow("p_cw2")}</div>`;
    else if(selPipe) box.innerHTML=`<b>${PIPES[selPipe].name}.</b> ${PIPES[selPipe].what}<div class="flow">Now: ${pipeFlow(selPipe)}</div>`;
    else { const c=CONN[sel]; box.innerHTML=`<b>${NAME[sel]()}.</b> ${c.text}<div class="flow">Upstream: ${c.up}<br>Downstream: ${c.down}</div>`; } }
  for(const dev in devG){ const g=devG[dev];
    const fxOn = C.fx && ((now<fxUntil && C.fx.items.some(x=>x.dev===dev)) || fxHover===dev);
    const wfOn = wf<100 && sel==="pump_chw" && ["pump_chw","fc","chiller"].includes(dev);
    g.classList.toggle("glow", !!(fxOn||wfOn)); g.classList.toggle("sel", dev===sel && !selPipe); }
}
document.querySelectorAll("#modes button").forEach(b=>b.onclick=()=>{ mode=b.dataset.m; selPipe=null;
  document.querySelectorAll("#modes button").forEach(x=>x.classList.toggle("on",x===b)); applyFocus(); });
$("explore").onchange=e=>{ explore=e.target.checked; if(explore){mode="all"; document.querySelectorAll("#modes button").forEach(x=>x.classList.toggle("on",x.dataset.m==="all"));} selPipe=null; applyFocus(); };
document.querySelectorAll("#pv .dev").forEach(g=>g.addEventListener("click",()=>{sel=g.dataset.dev;selPipe=null;wf=100;right();panel();applyFocus();}));
document.querySelectorAll("#pv .pipe").forEach(g=>g.addEventListener("click",()=>{ selPipe=g.dataset.pipe;
  if(!explore){ explore=true; $("explore").checked=true; mode="all"; document.querySelectorAll("#modes button").forEach(x=>x.classList.toggle("on",x.dataset.m==="all")); } applyFocus(); }));

// ---------------------------------------------------------------- panels
const pct=v=>Math.round(v*100)+" %";
const PANELS = {
 chiller: i=>({title:"Chillers", kind:"SSSF",
   why:"Four steady-flow devices in a loop: compressor, condenser, valve, evaporator. The plant picks how many chillers to run so the compressors sit near their best-efficiency point.",
   glance:[["Temperature", D.non[i]>0?`${f1(D.Te[i])} → ${f1(D.Tc[i])} °C`:"—"],["Cooling", `${f2(D.qch[i]+D.qchg[i])} of ${f0(D.nav[i]*C.cap)} MW`],["Power", `${f0(D.wcomp[i])} kW`],["Efficiency", D.non[i]>0?`COP ${f1(D.cop[i])}`:"—"]],
   kv: D.non[i]>0 ? [["running",`${D.non[i]} of ${D.nav[i]}`],["load each",`${Math.round(D.plr[i]*100)} %`],["refrigerant flow",`${f1(D.mref[i])} kg/s`],
     ["evaporating",`${f1(D.Te[i])} °C · ${f0(D.Pe[i])} kPa`],["condensing",`${f1(D.Tc[i])} °C · ${f0(D.Pc[i])} kPa`],["lift",`${f1(D.Tc[i]-D.Te[i])} K`],
     ["compressor η",f2(D.eta[i])],["map position x",f2(D.xm[i])],["share of Carnot",pct(D.copc[i]/Math.max(D.car[i],1e-9))],
     ["cycle COP",f2(D.copc[i])],["electrical COP",f2(D.cop[i])],["Carnot COP",f2(D.car[i])],
     ["S_gen compressor",`${f2(D.sgc[i])} kW/K`],["S_gen condenser",`${f2(D.sgk[i])} kW/K`],["S_gen valve",`${f2(D.sgv[i])} kW/K`],
     ["S_gen evaporator",`${f2(D.sge[i])} kW/K`],["approach, evap.",`${f2(D.ae[i])} K`],["approach, cond.",`${f2(D.ac[i])} K`]]
     : [["running",`0 of ${D.nav[i]}`],["why","free cooling or storage carries the load"]],
   eq:["w = h₂ − h₁   (compressor)","q_L = h₁ − h₄   (evaporator)","q_H = h₂ − h₃   (condenser)","h₄ = h₃   (valve)","COP = q_L / w  ≤  T_L / (T_H − T_L)"]}),
 tower: i=>({title: NAME.tower(), kind:"SSSF",
   why: C.mode==="tower" ? "Evaporating a little water cools the rest toward the wet-bulb temperature. Water in equals water out." : "A fan-driven radiator. It uses no water but can only approach the dry-bulb temperature.",
   glance:[["Temperature",`${f1(D.Tsink[i])} °C water out`],["Heat rejected",`${f2(D.qrej[i])} MW`],["Power",`${f0(D.pfan[i])} kW fans`],["Efficiency",`${f1(D.arej[i])} K approach`]],
   kv: [["heat rejected",`${f2(D.qrej[i])} MW`],[C.mode==="tower"?"wet-bulb":"dry-bulb",`${f1(C.mode==="tower"?D.Twb[i]:D.Tdb[i])} °C`],["approach",`${f1(D.arej[i])} K`],
     ["water leaving",`${f1(D.Tsink[i])} °C`],["fan power",`${f0(D.pfan[i])} kW`],["make-up water",`${f1(D.water[i])} m³/h`],
     ["evaporation",`${f1(D.evap[i])} m³/h`],["drift",`${D.drift[i].toFixed(3)} m³/h`],["blowdown",`${f1(D.blow[i])} m³/h`]],
   eq:["Q = ṁ c_p ΔT","make-up = evaporation + drift + blowdown","evaporation = ṁ_air (ω_out − ω_in)"]}),
 fc: i=>({title:"Free-cooling heat exchanger", kind:"SSSF",
   why:"When the tower water is colder than the return water, it pre-cools the return water before the chillers. No compressor work.",
   glance:[["Temperature",`${f1(D.Tsink[i])} °C tower water`],["Cooling",`${f2(D.qfc[i])} MW`],["Power","0 kW compressor"],["Efficiency",`${pct(D.ffc[i])} of load`]],
   kv:[["share of load",pct(D.ffc[i])],["heat moved",`${f2(D.qfc[i])} MW`],["tower water",`${f1(D.Tsink[i])} °C`],
       ["return water",`${f1(C.chws+C.dT)} °C`],["supply set point",`${f1(C.chws)} °C`],["exchanger approach",`${f1(C.hx)} K`]],
   eq:["f = (T_return − (T_tower + 2 K)) / (T_return − T_supply)","Q = ṁ c_p ΔT"]}),
 pump_chw: i=>({title:"Chilled-water pump", kind:"SSSF",
   why:"The work a pump adds is lost to friction around the loop, so it ends up as heat in the water and adds to the cooling load.",
   glance:[["Temperature",`${f1(C.chws)} → ${f1(C.chws+C.dT)} °C`],["Flow",`${f0(D.mchw[i])} kg/s`],["Power",`${f0(D.pchw[i])} kW`],["Efficiency",`η ${f2(C.peff)}`]],
   kv:[["flow",`${f0(D.mchw[i])} kg/s`],["share of design flow",pct(D.mchw[i]/Math.max(mNom,1))],["flow limit",`${f0(mMax)} kg/s`],
       ["electric power",`${f0(D.pchw[i])} kW`],["heat carried",`${f2(D.qloop[i])} MW`],["water temperature rise",`${f1(C.dT)} K`]],
   eq:["W = ṁ ΔP / (ρ η)","ΔP = ΔP_d [0.3 + 0.7 (ṁ/ṁ_d)²]","ṁ = Q / (c_p ΔT)"]}),
 pump_cw: i=>({title:"Condenser-water pump", kind:"SSSF",
   why:"Moves water between the chillers and the tower. Its work also ends up as heat, which the tower rejects.",
   glance:[["Temperature",`${f1(D.Tsink[i])} → ${f1(D.Tsink[i]+C.dTcw)} °C`],["Flow",`${f0(D.mcw[i])} kg/s`],["Power",`${f0(D.pcw[i])} kW`],["Efficiency",`η ${f2(C.peff)}`]],
   kv:[["flow",`${f0(D.mcw[i])} kg/s`],["share of design flow",pct(D.mcw[i]/Math.max(C.mcwd,1))],["electric power",`${f0(D.pcw[i])} kW`],
       ["heat carried",`${f2(D.qrej[i])} MW`],["water temperature rise",`${f1(C.dTcw)} K`],["",""]],
   eq:["W = ṁ ΔP / (ρ η)","ΔP = ΔP_d [0.3 + 0.7 (ṁ/ṁ_d)²]"]}),
 tank: i=>({title:"Chilled-water storage tank", kind:"transient",
   why: C.tank ? "A control volume that stores mass: cold water below, warm return water above. Its cold-water mass changes with time." : "Not installed in this plan. Turn it on in the Storage tank control.",
   glance: C.tank ? [["Temperature",`${f1(C.chws)} °C cold layer`],["Stored",`${f1(D.soc[i]*C.tankMWh)} of ${f0(C.tankMWh)} MWh`],["Power",D.qchg[i]>0.01?`+${f2(D.qchg[i])} MW in`:(D.qdis[i]>0.01?`${f2(D.qdis[i])} MW out`:"0 MW")],["Charge",pct(D.soc[i])]] : [["Temperature","—"],["Stored","—"],["Power","—"],["Charge","—"]],
   kv: C.tank ? [["cold water stored",`${f0(D.mcold[i])} t of ${f0(C.tankt)} t`],["charge",pct(D.soc[i])],["charging",`${f2(D.qchg[i])} MW`],
       ["discharging",`${f2(D.qdis[i])} MW`],["cold layer",`${f1(C.chws)} °C`],["warm layer",`${f1(C.chws+C.dT)} °C`]] : [],
   eq:["dm_cold/dt = ṁ_charge − ṁ_discharge","ṁ = Q / (c_p ΔT)"]}),
 hall: i=>({title:"AI data hall", kind:"transient",
   why:"A control volume that stores energy in its air, racks and structure. If cooling falls short, its temperature rises. GPU throttling and shutdown above the limit are assumed operating rules, not physical laws.",
   glance:[["Temperature",`${f1(D.Tin[i])} °C (limit ${f0(D.lim[i])})`],["Heat load",`${f2(D.it[i])} MW`],["Power",`${f2(D.ptot[i])} MW site`],["Efficiency",`PUE ${D.pue[i].toFixed(3)}`]],
   kv:[[C.liquid?"coolant to GPUs":"server inlet",`${f2(D.Tin[i])} °C`],["target",`${f1(C.target)} °C`],["limit",`${f1(D.lim[i])} °C`],
       ["margin to limit",`${f1(D.lim[i]-D.Tin[i])} K`],["IT load",`${f2(D.it[i])} MW`],["compute delivered",pct(D.thr[i])]],
   eq:["C dT/dt = Q_IT + W_fans − Q_cool","throttle: −8 % power per K above limit + 5 K","shutdown: 12 to 15 K above that"]}),
};
function panel(){
  const p=PANELS[sel](i), [k,lbl]=status(sel,i);
  $("p_left").innerHTML=`<h4>${p.title}</h4><span class="badge">${p.kind==="SSSF"?"SSSF · steady flow":"transient control volume"}</span><div class="why">${p.why}</div>`;
  const gl=[["Status",`<span style="color:${SC[k]==="#4A525E"?"#A3ABB5":SC[k]}">● ${lbl}</span>`]].concat(p.glance).map(([a,b])=>`<div class="gl"><span>${a}</span><b>${b}</b></div>`).join("");
  $("p_mid").innerHTML=`<div class="glance">${gl}</div><div class="grid">${p.kv.map(([a,b])=>`<div class="kv"><span>${a}</span><span>${b}</span></div>`).join("")}</div>`;
  if(sel==="pump_chw") whatif();
}
function right(){
  const p=PANELS[sel](i);
  let h=`<div class="eqh">Governing equations</div><div class="eq">${p.eq.join("<br>")}</div>`;
  if(sel==="pump_chw") h+=`<div id="wfbox"><div class="eqh">What if this pump ran slower?</div><input id="wf" type="range" min="40" max="100" step="5" value="${wf}"/><div id="wfout"></div></div>`;
  $("p_right").innerHTML=h;
  const s=$("wf"); if(s) s.oninput=e=>{wf=+e.target.value; whatif(); applyFocus();};
}
function whatif(){
  const o=$("wfout"); if(!o) return;
  const m0=D.mchw[i], Q=D.qloop[i]*1e6;
  if(m0<1||Q<=0){ o.innerHTML="The pump is stopped at this moment."; return; }
  const f=wf/100, m=f*m0, cp=4186;
  const pw=mm=>mm*C.dP*1e3*(C.stat+(1-C.stat)*Math.pow(mm/C.mchwd,2))/(1000*C.peff*C.pmeff)/1e3;
  const dT0=Q/(m0*cp), dT=Q/(m*cp), Tr0=C.chws+dT0, Tr=C.chws+dT;
  const fcs=T=>C.fc?Math.max(0,Math.min(1,(T-(D.Tsink[i]+C.hx))/Math.max(T-C.chws,1e-6))):0;
  o.innerHTML=`Speed <b>${wf} %</b> → flow <b>${f0(m)} kg/s</b><br>
   Same heat, less water: return water <b>${f1(Tr0)} → ${f1(Tr)} °C</b><br>
   Pump power <b>${f0(pw(m0))} → ${f0(pw(m))} kW</b><br>
   Free cooling could carry <b>${pct(fcs(Tr0))} → ${pct(fcs(Tr))}</b><br>
   <span style="color:#8A929C">Same equations as the model, at this instant, with the other equipment unchanged. In the controls this is "How much the water warms up".</span>`;
  PIPES.p_ret.el.setAttribute("stroke", wf<100 ? mix([217,164,65],[217,123,63],Math.min(1,(dT-dT0)/6)) : WARM);
}

// ---------------------------------------------------------------- what a change did
if(C.fx && C.fx.items && C.fx.items.length && !C.compact){
  const fx=$("fx"); fx.style.display="block";
  fx.innerHTML=`<div class="h">${C.fx.head}</div><div class="chain">`+C.fx.items.map((x,k)=>(k?'<span class="arrow">→</span>':'')+`<div class="chip" data-dev="${x.dev}"><b>${x.label}</b>${x.text}</div>`).join("")+`</div>`;
  fx.querySelectorAll(".chip").forEach(c=>{ c.onmouseenter=()=>{fxHover=c.dataset.dev;applyFocus();}; c.onmouseleave=()=>{fxHover=null;applyFocus();}; });
  fxUntil=performance.now()+9000; setTimeout(applyFocus, 9100);
}

// ---------------------------------------------------------------- drawing one frame
let prevQ=null;
function draw(){
  const h=D.hour[i];
  $("clock").textContent=hhmm(h);
  $("hud_out").textContent=`${f1(D.Tdb[i])} °C · wet-bulb ${f1(D.Twb[i])} °C`;
  $("hud_price").textContent=`$${D.price[i]}/MWh`;
  chUnits.forEach((u,k)=>{
    const [s,lbl0]=unitStatus(k,i), on=RANK[s]>=2, col=SC[s], lbl={overloaded:"overloaded","off its best point":"off best pt","high demand":"high demand"}[lbl0]||lbl0;
    u.box.setAttribute("stroke", col); u.box.setAttribute("stroke-dasharray", s==="off" ? "4 4" : "");
    u.dot.setAttribute("fill", col); u.dot.classList.toggle("pulse", s==="high"||s==="crit");
    u.plr.setAttribute("width", on ? 48*Math.min(1,D.plr[i]) : 0); u.plr.setAttribute("fill", on?col:COLD);
    u.st.textContent = s==="off" ? "offline" : (on ? Math.round(D.plr[i]*100)+" %" : "standby");
    u.st.setAttribute("fill", s==="off" ? "#8A929C" : (on ? "#E6E8EB":"#8A929C"));
    u.st2.textContent = on && s!=="normal" ? lbl : ""; u.st2.setAttribute("fill", col);
    u.snow.setAttribute("opacity", on ? 0.35+0.65*Math.min(1,D.plr[i]) : 0);
    if(u.last && RANK[u.last]<2 && on){ u.g.classList.remove("flash"); void u.g.getBBox(); u.g.classList.add("flash"); }
    u.last=s;
    if(on){u.angle=(u.angle+6+10*D.plr[i])%360;} u.rot.setAttribute("transform",`rotate(${u.angle})`);
  });
  const fc=D.ffc[i];
  $("hud_fc").textContent = !C.fc ? "switched off" : (fc>0.01 ? `${Math.round(fc*100)} % of load` : "off");
  PIPES.p_cwfc.el.setAttribute("opacity", fc>0.01 ? 1 : 0.3); PIPES.p_cwfc.arrows.forEach(a=>a.setAttribute("opacity", fc>0.01?1:0.3));
  const soc=D.soc[i];
  $("tank_cold").setAttribute("height", 150*soc); $("tank_cold").setAttribute("y", 275+150*(1-soc));
  let tk = C.tank ? `${Math.round(soc*100)} %` : "not installed";
  if(C.tank && D.qchg[i]>0.01) tk += " charging"; if(C.tank && D.qdis[i]>0.01) tk += " in use";
  $("hud_tank").textContent=tk;
  $("plume").setAttribute("opacity", Math.min(0.9, 0.15 + D.water[i]/40));
  $("hud_water").textContent= C.mode==="tower" ? `${f1(D.water[i])} m³/h water` : "no water";
  $("hud_rej").textContent= D.qrej[i]>0.01 ? `↑ ${f1(D.qrej[i])} MW of heat to the air` : "";
  const col=tempColor(D.Tin[i]);
  racks.forEach(r=>{r.setAttribute("fill", col); r.setAttribute("opacity", 0.35+0.6*D.thr[i]);});
  $("hud_inlet").textContent=`${f1(D.Tin[i])} °C`; $("hud_inlet").setAttribute("fill", col);
  const rising = prevQ!==null && D.itreq[i]>prevQ+0.02; prevQ=D.itreq[i];
  $("hud_it").textContent=`IT load ${f2(D.it[i])} MW`+(rising?"  ▲ rising":"");
  $("lab_sup").textContent=`cold supply ${f1(C.chws)} °C`;
  $("lab_ret").textContent=`warm return ${f1(C.chws+C.dT)} °C`;
  $("lab_heat").textContent=`← ${f1(D.qloop[i])} MW of heat from the servers`;
  // cooling power and heat load, with the direction they are moving
  const pc=(D.wcomp[i]+D.pchw[i]+D.pcw[i]+D.pfan[i])/1e3, pp=i>0?(D.wcomp[i-1]+D.pchw[i-1]+D.pcw[i-1]+D.pfan[i-1])/1e3:pc;
  const tr=(a,b,t)=>a>b+t?" ▲":(a<b-t?" ▼":"");
  $("pg_v").textContent=f2(pc)+" MW"+tr(pc,pp,0.004); $("pg_v").setAttribute("fill", pc>pp+0.004?"#D97B3F":(pc<pp-0.004?"#6FA8DC":"#E6E8EB"));
  $("pg_b").setAttribute("width", 92*Math.min(1,pc/pcMax)); $("pg_b").setAttribute("fill", pc>0.85*pcMax?"#D97B3F":"#6FA8DC");
  const qh=D.itreq[i], qp=i>0?D.itreq[i-1]:qh;
  $("hg_v").textContent=f2(qh)+" MW"+tr(qh,qp,0.01); $("hg_b").setAttribute("width", 92*Math.min(1,qh/Math.max(itMax,1e-6)));
  // pipe width follows the flow
  const fr=Math.min(1.5,D.mchw[i]/Math.max(mNom,1));
  // alert bar: red only for real alarms, ochre for notices
  const thr=D.thr[i]; let msg="", colr="#E06A50";
  const tripped = D.nav[i] < C.nch && C.events.some(e=>e.kind==="trip" && h>=e.t && h<e.until);
  if(thr<0.999) msg=`GPUs throttling: ${Math.round((1-thr)*100)} % of compute lost`;
  else if(D.Tin[i]>D.lim[i]+1e-6) msg=`Above the ${D.lim[i]} °C limit`;
  else if(D.short[i]>0.01) msg=`Cooling short by ${f2(D.short[i])} MW`;
  else if(tripped) msg="Chiller offline";
  else { const e=C.events.find(e=>h>=e.t && h<Math.min(e.until,e.t+1.5)); if(e){msg=e.title; colr="#D9A441";} }
  $("alert_bg").setAttribute("opacity", msg?1:0); $("alert_bg").setAttribute("fill", colr); $("alert_tx").textContent=msg;
  $("hud_pue").textContent=D.pue[i]>0 ? D.pue[i].toFixed(3) : "—";
  $("hud_cop").textContent= D.cop[i]>0 ? f1(D.cop[i]) : "off";
  const tot=Math.max(1e-6, D.qfc[i]+D.qdis[i]+D.qch[i]+D.short[i]);
  let x0=236; [["mix_fc",D.qfc[i]],["mix_tk",D.qdis[i]],["mix_ch",D.qch[i]],["mix_sh",D.short[i]]].forEach(([id,v])=>{
    const w=524*v/tot; $(id).setAttribute("x",x0); $(id).setAttribute("width",w); x0+=w;});
  $("hud_power").textContent=`site ${f2(D.ptot[i])} MW · compressors ${f0(D.wcomp[i])} kW · pumps ${f0(D.pchw[i]+D.pcw[i])} kW · fans ${f0(D.pfan[i])} kW`;
  $("scrub").value=i; $("tl_cur").style.left=(100*i/Math.max(1,N-1))+"%";
  paintStatus(); panel(); applyFocus();
}
function animate(){
  dash+=1;
  const chw=Math.min(2.4, 1.6*D.mchw[i]/Math.max(mNom,1)), cw=Math.min(2.4, 1.6*D.mcw[i]/Math.max(C.mcwd,1));
  PIPES.p_sup.off=(PIPES.p_sup.off||0)-chw; PIPES.p_cw.off=(PIPES.p_cw.off||0)-cw;
  ["p_sup","p_ret","p_ret2"].forEach(id=>PIPES[id].el.setAttribute("stroke-dashoffset", PIPES.p_sup.off));
  ["p_cw","p_cw2"].forEach(id=>PIPES[id].el.setAttribute("stroke-dashoffset", PIPES.p_cw.off));
  PIPES.p_cwfc.off=(PIPES.p_cwfc.off||0)-(D.ffc[i]>0.01?cw:0); PIPES.p_cwfc.el.setAttribute("stroke-dashoffset", PIPES.p_cwfc.off);
  const tk = D.qchg[i]>0.01 ? -1.2 : (D.qdis[i]>0.01 ? 1.2 : 0);
  PIPES.p_tk1.off=(PIPES.p_tk1.off||0)+tk; PIPES.p_tk1.el.setAttribute("stroke-dashoffset", PIPES.p_tk1.off); PIPES.p_tk2.el.setAttribute("stroke-dashoffset", -PIPES.p_tk1.off);
  document.querySelectorAll(".df").forEach(f=>f.setAttribute("transform",`rotate(${(dash*3*Math.min(1.5,D.qrej[i]/Math.max(C.qd,1)))%360})`));
  const load=Math.min(1.2,D.it[i]/Math.max(itMax,1e-6));
  heatM.forEach(hm=>{ const t=((dash*0.012*(0.5+load))+hm.ph)%1; hm.e.setAttribute("transform",`translate(${hm.x} ${hm.y-2-14*t})`); hm.e.setAttribute("opacity", (1-t)*0.75*load); });
  requestAnimationFrame(animate);
}
// ---------------------------------------------------------------- timeline
function buildTimeline(){
  const X=k=>1000*k/Math.max(1,N-1);
  const lo=itMin-0.15*(itMax-itMin+0.5), hi=itMax+0.05*(itMax-itMin+0.5);
  let a="M0 26"; D.itreq.forEach((v,k)=>a+=` L${X(k).toFixed(1)} ${(26-24*(v-lo)/(hi-lo)).toFixed(1)}`); $("tl_it").setAttribute("d",a+" L1000 26 Z");
  const tmx=Math.max(...D.Tin, C.limit), tmn=Math.min(...D.Tin)-0.5;
  let b=""; D.Tin.forEach((v,k)=>b+=`${k?"L":"M"}${X(k).toFixed(1)} ${(25-22*(v-tmn)/Math.max(tmx-tmn,0.5)).toFixed(1)} `); $("tl_T").setAttribute("d",b);
  const mk=[], am=arr=>arr.indexOf(Math.max(...arr));
  C.events.forEach(e=>{ if(e.t<=D.hour[N-1]+1e-6) mk.push({k:D.hour.findIndex(h=>h>=e.t-1e-6), t:e.title, c:"#D9A441"}); });
  const ks=D.short.findIndex(v=>v>0.01); if(ks>=0) mk.push({k:ks,t:"cooling falls short",c:"#E06A50"});
  const kt=am(D.Tin); if(Math.max(...D.Tin)-Math.min(...D.Tin)>0.3) mk.push({k:kt,t:`hall peaks at ${f1(D.Tin[kt])} °C`,c:D.Tin[kt]>D.lim[kt]?"#E06A50":"#6FA8DC"});
  if(itMax-itMin>0.5){ const k=am(D.itreq); mk.push({k,t:`peak heat load ${f1(D.itreq[k])} MW`,c:"#B4BAC2"}); }
  { const k=am(D.Tdb); mk.push({k,t:`hottest outside ${f1(D.Tdb[k])} °C`,c:"#D97B3F"}); }
  { const k=am(D.ptot); mk.push({k,t:`peak power ${f1(D.ptot[k])} MW`,c:"#B4BAC2"}); }
  for(let k=1;k<N;k++){ if(D.ffc[k]>0.01 && D.ffc[k-1]<=0.01){ mk.push({k,t:"free cooling starts",c:"#6FA8DC"}); break; } }
  for(let k=1;k<N;k++){ if(D.ffc[k]<=0.01 && D.ffc[k-1]>0.01){ mk.push({k,t:"free cooling ends",c:"#8A929C"}); break; } }
  for(let k=1;k<N;k++){ if(D.qdis[k]>0.01 && D.qdis[k-1]<=0.01){ mk.push({k,t:"tank starts discharging",c:"#8FB39A"}); break; } }
  mk.sort((p,q)=>p.k-q.k);
  const rows=[-99,-99,-99], host=$("tl_m");
  mk.forEach(m=>{ const pos=100*m.k/Math.max(1,N-1); let r=rows.findIndex(v=>pos-v>Math.min(26, 5+m.t.length*0.62)); if(r<0) return; rows[r]=pos;
    const d=document.createElement("div"); d.className="mk"; d.textContent=m.t; d.style.color=m.c;
    d.style.left=Math.min(94,Math.max(6,pos))+"%"; d.style.top=(28+r*15)+"px"; d.onclick=()=>{i=Math.max(0,m.k);draw();}; host.appendChild(d); });
}
$("scrub").max=N-1;
$("scrub").oninput=e=>{i=+e.target.value;draw();};
function stop(lbl){clearInterval(timer);timer=null;$("play").textContent=lbl;}
$("play").onclick=()=>{
  if(timer){stop("Play day");return;}
  if(i>=N-1)i=0;
  $("play").textContent="Pause";
  timer=setInterval(()=>{i++; if(i>=N){ if(C.autoplay){i=0;} else {i=N-1;stop("Replay");} } draw();}, +$("speed").value);
};
$("speed").onchange=()=>{if(timer){stop("Play day");$("play").click();}};
if(C.compact){["panel","tl","modes","conn","fx","legend","pgauge","hgauge"].forEach(id=>$(id).style.display="none");$("sv").style.minWidth="0";$("sv").setAttribute("viewBox","0 0 1200 600");}
if(C.start==="end") i=N-1; else if(C.start==="zero") i=0; else { const mx=Math.max(...D.Tin), mn=Math.min(...D.Tin); i = (mx-mn>0.2) ? D.Tin.indexOf(mx) : D.Tdb.indexOf(Math.max(...D.Tdb)); if(i<0)i=0; }
buildTimeline(); right(); draw(); animate();
if(C.autoplay){ i=0; $("play").click(); }
// make the frame as tall as its content, so nothing is cut off and no space is wasted
function fit(){ try{ const fe=window.frameElement; if(!fe) return; const h=Math.ceil($("pv").getBoundingClientRect().height)+8;
  if(Math.abs(parseFloat(fe.style.height||0)-h)>3){ fe.style.height=h+"px"; fe.setAttribute("height",h);
    const p=fe.parentElement; if(p && p.children.length===1) p.style.height=h+"px"; } }catch(e){} }
try{ new ResizeObserver(fit).observe($("pv")); }catch(e){} fit();
</script>
"""
