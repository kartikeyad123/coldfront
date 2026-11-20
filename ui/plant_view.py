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
        pfan=col("P_fans", 1e-3, 0),
        sgc=sg(sg_comp), sgk=sg(sg_cond), sgv=sg(sg_valve), sge=sg(sg_evap),
    )


def plant_html(day, autoplay=False, start="hot", focus="chiller", compact=False):
    s = day.settings
    data = frames_from_day(day)
    ev = [dict(t=e.t, until=e.until, title=e.title, text=e.text, kind=e.kind) for e in getattr(day, "events", ())]
    cfg = dict(nch=s.n_installed, tank=bool(s.tank), mode=s.rejection, limit=s.T_limit_C,
               thr=s.T_throttle, target=s.T_chws_C + s.approach_rack, liquid=s.rack_cooling == "liquid",
               chws=s.T_chws_C, dT=s.dT_chw, dTcw=s.dT_cw, events=ev, autoplay=autoplay, start=start, focus=focus, compact=compact,
               tankt=round(s.tank_mass / 1e3))
    return _TEMPLATE.replace("__DATA__", json.dumps(data)).replace("__CFG__", json.dumps(cfg))


_TEMPLATE = r"""
<div id="pv">
<style>
 @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600&display=swap');
 #pv{width:100%;font-family:'Inter',sans-serif;color:#E6E8EB}
 #pv svg text{font-family:'Inter',sans-serif}
 #pv svg .num{font-family:'IBM Plex Mono',monospace}
 #pv svg .lab{font-size:10.5px;letter-spacing:.12em;fill:#8A929C;text-transform:uppercase}
 #pv .dev{cursor:pointer}
 #pv .dev .frame{transition:stroke .15s}
 #pv .dev:hover .frame{stroke:#E6E8EB}
 #pv .dev.sel .frame{stroke:#E6E8EB;stroke-width:1.6}
 #pv .bar{display:flex;gap:12px;align-items:center;margin-top:8px}
 #pv button{background:#151A21;color:#E6E8EB;border:1px solid #2A313B;padding:6px 16px;font-family:inherit;
   cursor:pointer;border-radius:6px;font-size:13px}
 #pv button:hover{border-color:#E6E8EB}
 #pv input[type=range]{flex:1;accent-color:#E6E8EB}
 #pv select{background:#151A21;color:#E6E8EB;border:1px solid #2A313B;font-family:inherit;padding:5px;border-radius:6px}
 #ticks{position:relative;height:12px;margin:0 86px 0 96px}
 #ticks span{position:absolute;top:0;width:2px;height:10px;background:#D9A441}
 #panel{margin-top:8px;background:#151A21;border:1px solid #2A313B;border-radius:6px;padding:12px 16px;display:grid;
   grid-template-columns:230px 1fr 300px;gap:18px;min-height:128px}
 @media (max-width: 900px){#panel{grid-template-columns:1fr} #panel .grid{grid-template-columns:repeat(2,1fr)}}
 #panel h4{margin:0 0 4px 0;font-size:15px;font-weight:600}
 #panel .badge{font-family:'IBM Plex Mono',monospace;font-size:11px;border:1px solid #2A313B;border-radius:3px;padding:1px 7px;color:#B4BAC2}
 #panel .why{color:#8A929C;font-size:12.5px;line-height:1.45;margin-top:8px}
 #panel .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:4px 18px;align-content:start}
 #panel .kv{display:flex;justify-content:space-between;gap:10px;font-size:12.5px;border-bottom:1px solid #20262E;padding:3px 0}
 #panel .kv span:first-child{color:#8A929C}
 #panel .kv span:last-child{font-family:'IBM Plex Mono',monospace;text-align:right}
 #svwrap{overflow-x:auto}
 #svwrap svg{min-width:720px}
 #panel .eq{font-family:'IBM Plex Mono',monospace;font-size:12px;color:#B4BAC2;line-height:1.7}
 #panel .eqh{color:#8A929C;font-size:11px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:4px}
</style>
<div id="svwrap"><svg id="sv" viewBox="0 0 1200 600" width="100%" style="background:#0E1116;border:1px solid #2A313B;border-radius:6px">
 <rect id="alert_bg" x="0" y="0" width="1200" height="26" fill="#E06A50" opacity="0"/>
 <text id="alert_tx" x="600" y="18" text-anchor="middle" font-size="12.5" font-weight="600" fill="#0E1116"></text>
 <text x="24" y="52" class="lab">Outside</text>
 <text id="hud_out" x="24" y="76" font-size="15" class="num" fill="#E6E8EB">--</text>
 <text id="clock" x="600" y="74" text-anchor="middle" font-size="30" class="num" fill="#E6E8EB">00:00</text>
 <text x="1176" y="52" text-anchor="end" class="lab">Grid price</text>
 <text id="hud_price" x="1176" y="76" text-anchor="end" font-size="15" class="num" fill="#E6E8EB">--</text>
 <line x1="24" y1="92" x2="1176" y2="92" stroke="#20262E"/>

 <!-- pipes: condenser water (grey), chilled supply (cold), return (warm) -->
 <path id="p_cw" d="M250 215 H335" stroke="#8A929C" stroke-width="3" fill="none" stroke-dasharray="10 8"/>
 <path id="p_cw2" d="M250 255 H335" stroke="#5E6670" stroke-width="3" fill="none" stroke-dasharray="10 8"/>
 <path id="p_sup" d="M645 215 H820 V310 H860" stroke="#6FA8DC" stroke-width="3.5" fill="none" stroke-dasharray="12 8"/>
 <path id="p_ret" d="M860 480 H410 V360" stroke="#D9A441" stroke-width="3.5" fill="none" stroke-dasharray="12 8"/>
 <path id="p_ret2" d="M410 310 V282" stroke="#D9A441" stroke-width="3.5" fill="none" stroke-dasharray="12 8"/>
 <path id="p_tk1" d="M745 215 V272" stroke="#6FA8DC" stroke-width="2" fill="none" stroke-dasharray="5 5"/>
 <path id="p_tk2" d="M745 428 V480" stroke="#D9A441" stroke-width="2" fill="none" stroke-dasharray="5 5"/>

 <!-- heat rejection -->
 <g class="dev" data-dev="tower" id="g_rej">
  <rect x="62" y="110" width="206" height="260" fill="transparent"/>
  <g id="tower">
   <path class="frame" d="M84 300 L108 150 L222 150 L246 300 Z" fill="#151A21" stroke="#4A525E" stroke-width="1.2"/>
   <line x1="100" y1="200" x2="230" y2="200" stroke="#2A313B"/><line x1="92" y1="250" x2="238" y2="250" stroke="#2A313B"/>
   <g id="plume" opacity="0.4"><path d="M130 142 q10 -22 0 -40 M165 142 q12 -26 0 -46 M200 142 q10 -22 0 -40" stroke="#B4BAC2" stroke-width="1.4" fill="none"/></g>
  </g>
  <g id="dry">
   <rect class="frame" x="74" y="170" width="182" height="110" fill="#151A21" stroke="#4A525E" stroke-width="1.2"/>
   <g id="dryfans"></g>
  </g>
  <text id="rej_name" x="165" y="326" text-anchor="middle" class="lab">Cooling tower</text>
  <text id="hud_water" x="165" y="346" text-anchor="middle" font-size="12.5" class="num" fill="#B4BAC2">--</text>
 </g>

 <!-- chillers -->
 <g class="dev" data-dev="chiller">
  <rect x="330" y="100" width="320" height="185" fill="transparent"/>
  <text x="490" y="118" text-anchor="middle" class="lab">Chillers · refrigeration cycle</text>
  <g id="chillers"></g>
 </g>
 <!-- pumps -->
 <g class="dev" data-dev="pumps">
  <circle class="frame" cx="292" cy="255" r="11" fill="#151A21" stroke="#4A525E" stroke-width="1.2"/><path d="M287 250 L299 255 L287 260 Z" fill="#8A929C"/>
  <circle class="frame" cx="600" cy="480" r="11" fill="#151A21" stroke="#4A525E" stroke-width="1.2"/><path d="M605 475 L593 480 L605 485 Z" fill="#8A929C"/>
  <text x="600" y="512" text-anchor="middle" class="lab">Pumps</text>
 </g>
 <!-- free cooling heat exchanger -->
 <g class="dev" data-dev="fc">
  <rect class="frame" id="hx" x="345" y="310" width="130" height="50" fill="#151A21" stroke="#4A525E" stroke-width="1.2" rx="3"/>
  <text x="410" y="330" text-anchor="middle" class="lab">Free cooling</text>
  <text id="hud_fc" x="410" y="349" text-anchor="middle" font-size="12.5" class="num" fill="#B4BAC2">off</text>
 </g>
 <!-- storage tank -->
 <g class="dev" data-dev="tank" id="tankg_">
  <rect class="frame" x="705" y="272" width="80" height="156" rx="8" fill="#151A21" stroke="#4A525E" stroke-width="1.2"/>
  <rect id="tank_warm" x="708" y="275" width="74" height="150" rx="6" fill="#D9A441" opacity="0.28"/>
  <rect id="tank_cold" x="708" y="275" width="74" height="150" rx="6" fill="#6FA8DC" opacity="0.75"/>
  <text x="694" y="340" text-anchor="end" class="lab">Storage</text>
  <text id="hud_tank" x="694" y="358" text-anchor="end" font-size="12.5" class="num" fill="#B4BAC2">--</text>
 </g>
 <!-- data hall -->
 <g class="dev" data-dev="hall">
  <rect class="frame" x="860" y="110" width="316" height="405" fill="#12161C" stroke="#4A525E" stroke-width="1.2" rx="3"/>
  <text x="1018" y="132" text-anchor="middle" class="lab">AI data hall</text>
  <g id="racks"></g>
  <text id="hud_inlet" x="1018" y="446" text-anchor="middle" font-size="24" class="num" fill="#6FA8DC">--</text>
  <text id="inlet_lab" x="1018" y="465" text-anchor="middle" font-size="11.5" fill="#8A929C">server inlet air</text>
  <text id="hud_it" x="1018" y="494" text-anchor="middle" font-size="12.5" class="num" fill="#B4BAC2">--</text>
 </g>

 <!-- gauges -->
 <text x="24" y="420" class="lab">PUE now</text>
 <text id="hud_pue" x="24" y="450" font-size="26" class="num" fill="#E6E8EB">--</text>
 <text x="24" y="482" class="lab">Chiller COP</text>
 <text id="hud_cop" x="24" y="508" font-size="20" class="num" fill="#E6E8EB">--</text>
 <line x1="24" y1="532" x2="1176" y2="532" stroke="#20262E"/>
 <text x="24" y="562" class="lab">Who carries the heat</text>
 <rect x="200" y="550" width="560" height="14" fill="#151A21" stroke="#2A313B"/>
 <rect id="mix_fc" x="200" y="550" width="0" height="14" fill="#6FA8DC"/>
 <rect id="mix_tk" x="200" y="550" width="0" height="14" fill="#8FB39A"/>
 <rect id="mix_ch" x="200" y="550" width="0" height="14" fill="#D9A441"/>
 <rect id="mix_sh" x="200" y="550" width="0" height="14" fill="#E06A50"/>
 <text x="780" y="562" font-size="11.5" fill="#B4BAC2"><tspan fill="#6FA8DC">■</tspan> outside air  <tspan fill="#8FB39A" dx="8">■</tspan> storage  <tspan fill="#D9A441" dx="8">■</tspan> chillers  <tspan fill="#E06A50" dx="8">■</tspan> unmet</text>
 <text id="hud_power" x="200" y="586" font-size="12" class="num" fill="#8A929C">--</text>
 <text id="clickhint" x="1176" y="586" text-anchor="end" font-size="12" fill="#6FA8DC">click any equipment for details</text>
</svg></div>
<div class="bar">
 <button id="play">Play day</button>
 <input id="scrub" type="range" min="0" max="0" value="0"/>
 <select id="speed"><option value="160">1×</option><option value="70" selected>2×</option><option value="25">5×</option></select>
</div>
<div id="ticks"></div>
<div id="panel"></div>
</div>
<script>
const D = __DATA__, C = __CFG__;
const N = D.hour.length;
const $ = id => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
function el(tag, attrs, parent){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);parent.appendChild(e);return e;}
// chillers
const chG=$("chillers"), chUnits=[];
for(let i=0;i<C.nch;i++){
  const x=340+i*78, g=el("g",{},chG);
  const box=el("rect",{class:"frame",x:x,y:130,width:66,height:150,rx:3,fill:"#151A21",stroke:"#4A525E","stroke-width":1.2},g);
  const fanG=el("g",{transform:`translate(${x+33} 172)`},g);
  el("circle",{cx:0,cy:0,r:19,fill:"none",stroke:"#4A525E","stroke-width":1.2},fanG);
  const rot=el("g",{},fanG);
  for(let b=0;b<3;b++) el("path",{d:"M0 0 Q9 -9 17 -3",stroke:"#A9B0BA","stroke-width":1.6,fill:"none",transform:`rotate(${b*120})`},rot);
  el("rect",{x:x+9,y:206,width:48,height:5,fill:"#2A313B"},g);
  const plr=el("rect",{x:x+9,y:206,width:0,height:5,fill:"#D9A441"},g);
  const lab=el("text",{x:x+33,y:234,"text-anchor":"middle","font-size":10.5,fill:"#8A929C"},g); lab.textContent="CH-"+(i+1);
  const st=el("text",{x:x+33,y:256,"text-anchor":"middle","font-size":11,fill:"#8A929C",class:"num"},g);
  chUnits.push({box,rot,plr,st,angle:0});
}
for(let i=0;i<4;i++){const g=el("g",{transform:`translate(${100+i*43} 225)`},$("dryfans"));el("circle",{r:17,fill:"none",stroke:"#4A525E","stroke-width":1.2},g);const r=el("g",{class:"df"},g);for(let b=0;b<3;b++)el("path",{d:"M0 0 Q8 -8 15 -3",stroke:"#A9B0BA","stroke-width":1.5,fill:"none",transform:`rotate(${b*120})`},r);}
$("tower").style.display = C.mode==="tower" ? "" : "none";
$("dry").style.display = C.mode==="dry" ? "" : "none";
$("rej_name").textContent = C.mode==="tower" ? "Cooling tower" : "Dry cooler";
$("inlet_lab").textContent = C.liquid ? "coolant to GPU cold plates" : "server inlet air";
$("tankg_").style.opacity = C.tank ? 1 : 0.45;
if(!C.tank){$("tank_cold").style.display="none";$("tank_warm").style.display="none";}
["p_tk1","p_tk2"].forEach(id=>$(id).style.display = C.tank ? "" : "none");
const racks=[];
for(let r=0;r<3;r++)for(let c=0;c<8;c++){
  const x=884+c*34.5, y=150+r*88;
  racks.push(el("rect",{x:x,y:y,width:25,height:72,rx:2,fill:"#6FA8DC",stroke:"#0E1116"},$("racks")));
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
let i=0, timer=null, dash=0, sel=C.focus||"chiller";

const PANELS = {
 chiller: i=>({title:"Chillers", kind:"SSSF",
   why:"Four steady-flow devices in a loop. The plant picks how many chillers to run so the compressors sit near their best-efficiency point.",
   kv: D.non[i]>0 ? [["running",`${D.non[i]} of ${D.nav[i]}`],["load each",`${Math.round(D.plr[i]*100)} %`],["refrigerant flow",`${f1(D.mref[i])} kg/s`],
     ["evaporating",`${f1(D.Te[i])} °C · ${f0(D.Pe[i])} kPa`],["condensing",`${f1(D.Tc[i])} °C · ${f0(D.Pc[i])} kPa`],["lift",`${f1(D.Tc[i]-D.Te[i])} K`],
     ["compressor η",f2(D.eta[i])],["map position x",f2(D.xm[i])],["compressor power",`${f0(D.wcomp[i])} kW`],
     ["cycle COP",f2(D.copc[i])],["electrical COP",f2(D.cop[i])],["Carnot COP",f2(D.car[i])],
     ["S_gen compressor",`${f2(D.sgc[i])} kW/K`],["S_gen condenser",`${f2(D.sgk[i])} kW/K`],["S_gen valve",`${f2(D.sgv[i])} kW/K`],
     ["S_gen evaporator",`${f2(D.sge[i])} kW/K`],["approach, evap.",`${f2(D.ae[i])} K`],["approach, cond.",`${f2(D.ac[i])} K`]]
     : [["running",`0 of ${D.nav[i]}`],["status","off: free cooling or storage carries the load"]],
   eq:["w = h₂ − h₁   (compressor)","q_L = h₁ − h₄   (evaporator)","q_H = h₂ − h₃   (condenser)","h₄ = h₃   (valve)","COP = q_L / w  ≤  T_L / (T_H − T_L)"]}),
 tower: i=>({title: C.mode==="tower"?"Cooling tower":"Dry cooler", kind:"SSSF",
   why: C.mode==="tower" ? "Evaporating a little water cools the rest toward the wet-bulb temperature. Water in equals water out." : "A fan-driven radiator. It uses no water but can only approach the dry-bulb temperature.",
   kv: [["heat rejected",`${f2(D.qrej[i])} MW`],[C.mode==="tower"?"wet-bulb":"dry-bulb",`${f1(C.mode==="tower"?D.Twb[i]:D.Tdb[i])} °C`],["approach",`${f1(D.arej[i])} K`],
     ["water leaving",`${f1(D.Tsink[i])} °C`],["fan power",`${f0(D.pfan[i])} kW`],["make-up water",`${f1(D.water[i])} m³/h`],
     ["evaporation",`${f1(D.evap[i])} m³/h`],["drift",`${D.drift[i].toFixed(3)} m³/h`],["blowdown",`${f1(D.blow[i])} m³/h`]],
   eq:["Q = ṁ c_p ΔT","make-up = evaporation + drift + blowdown","evaporation = ṁ_air (ω_out − ω_in)"]}),
 fc: i=>({title:"Free-cooling heat exchanger", kind:"SSSF",
   why:"When the tower water is colder than the return water, it pre-cools the return water before the chillers. No compressor work.",
   kv:[["share of load",`${Math.round(D.ffc[i]*100)} %`],["heat moved",`${f2(D.qfc[i])} MW`],["tower water",`${f1(D.Tsink[i])} °C`],
       ["return water",`${f1(C.chws+C.dT)} °C`],["supply set point",`${f1(C.chws)} °C`],["exchanger approach","2.0 K"]],
   eq:["f = (T_return − (T_tower + 2 K)) / (T_return − T_supply)","Q = ṁ c_p ΔT"]}),
 pumps: i=>({title:"Pumps", kind:"SSSF",
   why:"The work a pump adds is lost to friction around the loop, so it ends up as heat in the water and adds to the cooling load.",
   kv:[["chilled-water flow",`${f0(D.mchw[i])} kg/s`],["chilled-water pump",`${f0(D.pchw[i])} kW`],["",""],
       ["condenser-water flow",`${f0(D.mcw[i])} kg/s`],["condenser-water pump",`${f0(D.pcw[i])} kW`],["",""]],
   eq:["W = ṁ ΔP / (ρ η)","ΔP = ΔP_d [0.3 + 0.7 (ṁ/ṁ_d)²]"]}),
 tank: i=>({title:"Chilled-water storage tank", kind:"transient",
   why: C.tank ? "A control volume that stores mass: cold water below, warm return water above. Its cold-water mass changes with time." : "Not installed in this plan.",
   kv: C.tank ? [["cold water stored",`${f0(D.mcold[i])} t of ${f0(C.tankt)} t`],["charge",`${Math.round(D.soc[i]*100)} %`],["charging",`${f2(D.qchg[i])} MW`],
       ["discharging",`${f2(D.qdis[i])} MW`],["cold layer",`${f1(C.chws)} °C`],["warm layer",`${f1(C.chws+C.dT)} °C`]] : [],
   eq:["dm_cold/dt = ṁ_charge − ṁ_discharge","ṁ = Q / (c_p ΔT)"]}),
 hall: i=>({title:"AI data hall", kind:"transient",
   why:"A control volume that stores energy in its air, racks and structure. If cooling falls short, its temperature rises. GPU throttling above the limit is an assumed operating rule, not a physical law.",
   kv:[[C.liquid?"coolant to GPUs":"server inlet",`${f2(D.Tin[i])} °C`],["target",`${f1(C.target)} °C`],["limit",`${f1(D.lim[i])} °C`],
       ["margin to limit",`${f1(D.lim[i]-D.Tin[i])} K`],["IT load",`${f2(D.it[i])} MW`],["compute delivered",`${Math.round(D.thr[i]*100)} %`]],
   eq:["C dT/dt = Q_IT + W_fans − Q_cool","throttle: −8 % power per K above limit + 5 K"]}),
};
function panel(){
  const p=PANELS[sel](i);
  const kv=p.kv.map(([k,v])=>`<div class="kv"><span>${k}</span><span>${v}</span></div>`).join("");
  $("panel").innerHTML=`<div><h4>${p.title}</h4><span class="badge">${p.kind==="SSSF"?"SSSF · steady flow":"transient control volume"}</span><div class="why">${p.why}</div></div>
   <div class="grid">${kv}</div><div><div class="eqh">Governing equations</div><div class="eq">${p.eq.join("<br>")}</div></div>`;
  document.querySelectorAll("#pv .dev").forEach(g=>g.classList.toggle("sel", g.dataset.dev===sel));
}
document.querySelectorAll("#pv .dev").forEach(g=>g.addEventListener("click",()=>{sel=g.dataset.dev;panel();}));

function draw(){
  const h=D.hour[i];
  $("clock").textContent=hhmm(h);
  $("hud_out").textContent=`${f1(D.Tdb[i])} °C · wet-bulb ${f1(D.Twb[i])} °C`;
  $("hud_price").textContent=`$${D.price[i]}/MWh`;
  chUnits.forEach((u,k)=>{
    const on = k < D.non[i], off = k >= D.nav[i];
    u.box.setAttribute("stroke", off ? "#E06A50" : (on ? "#A9B0BA" : "#4A525E"));
    u.box.setAttribute("stroke-dasharray", off ? "4 4" : "");
    u.plr.setAttribute("width", on ? 48*D.plr[i] : 0);
    u.st.textContent = off ? "offline" : (on ? Math.round(D.plr[i]*100)+" %" : "standby");
    u.st.setAttribute("fill", off ? "#E06A50" : (on ? "#E6E8EB":"#8A929C"));
    if(on){u.angle=(u.angle+6+10*D.plr[i])%360;} u.rot.setAttribute("transform",`rotate(${u.angle})`);
  });
  const fc=D.ffc[i];
  $("hx").setAttribute("stroke", fc>0.01 ? "#6FA8DC" : "#4A525E");
  $("hud_fc").textContent = fc>0.01 ? `${Math.round(fc*100)} % of load` : "off";
  const soc=D.soc[i];
  $("tank_cold").setAttribute("height", 150*soc); $("tank_cold").setAttribute("y", 275+150*(1-soc));
  let tk = C.tank ? `${Math.round(soc*100)} %` : "not installed";
  if(C.tank && D.qchg[i]>0.01) tk += " charging"; if(C.tank && D.qdis[i]>0.01) tk += " in use";
  $("hud_tank").textContent=tk;
  $("plume").setAttribute("opacity", Math.min(0.9, 0.15 + D.water[i]/40));
  $("hud_water").textContent= C.mode==="tower" ? `${f1(D.water[i])} m³/h water` : "no water";
  const col=tempColor(D.Tin[i]);
  racks.forEach(r=>{r.setAttribute("fill", col); r.setAttribute("opacity", 0.35+0.6*D.thr[i]);});
  $("hud_inlet").textContent=`${f1(D.Tin[i])} °C`; $("hud_inlet").setAttribute("fill", col);
  $("hud_it").textContent=`IT load ${f2(D.it[i])} MW`;
  // alert bar: red only for real alarms, ochre for notices
  const thr=D.thr[i]; let msg="", colr="#E06A50";
  const tripped = D.nav[i] < C.nch && C.events.some(e=>e.kind==="trip" && h>=e.t && h<e.until);
  if(thr<0.999) msg=`GPUs throttling: ${Math.round((1-thr)*100)} % of compute lost`;
  else if(D.Tin[i]>D.lim[i]+1e-6) msg=`Above the ${D.lim[i]} °C limit`;
  else if(D.short[i]>0.01) msg=`Cooling short by ${f2(D.short[i])} MW`;
  else if(tripped) msg="Chiller offline";
  else { const e=C.events.find(e=>h>=e.t && h<Math.min(e.until,e.t+1.5)); if(e){msg=e.title; colr="#D9A441";} }
  $("alert_bg").setAttribute("opacity", msg?1:0); $("alert_bg").setAttribute("fill", colr); $("alert_tx").textContent=msg;
  $("hud_pue").textContent=D.pue[i].toFixed(3);
  $("hud_cop").textContent= D.cop[i]>0 ? f1(D.cop[i]) : "off";
  const tot=Math.max(1e-6, D.qfc[i]+D.qdis[i]+D.qch[i]+D.short[i]);
  let x0=200; [["mix_fc",D.qfc[i]],["mix_tk",D.qdis[i]],["mix_ch",D.qch[i]],["mix_sh",D.short[i]]].forEach(([id,v])=>{
    const w=560*v/tot; $(id).setAttribute("x",x0); $(id).setAttribute("width",w); x0+=w;});
  $("hud_power").textContent=`site ${f2(D.ptot[i])} MW · compressors ${f0(D.wcomp[i])} kW · pumps ${f0(D.pchw[i]+D.pcw[i])} kW`;
  $("scrub").value=i; panel();
}
function animatePipes(){
  dash=(dash-0.5)%1000;
  const flow=Math.min(2.2, 0.4+ D.it[i]/8);
  ["p_sup","p_ret","p_ret2","p_tk1","p_tk2"].forEach(id=>$(id).setAttribute("stroke-dashoffset", dash*flow));
  ["p_cw","p_cw2"].forEach(id=>$(id).setAttribute("stroke-dashoffset", -dash*flow));
  document.querySelectorAll(".df").forEach(f=>f.setAttribute("transform",`rotate(${(dash*-5)%360})`));
  requestAnimationFrame(animatePipes);
}
$("scrub").max=N-1;
$("scrub").oninput=e=>{i=+e.target.value;draw();};
C.events.forEach(e=>{ if(e.t<=D.hour[N-1]){const s=document.createElement("span"); s.style.left=(100*e.t/Math.max(D.hour[N-1],1e-6))+"%"; s.title=e.title; $("ticks").appendChild(s);} });
function stop(lbl){clearInterval(timer);timer=null;$("play").textContent=lbl;}
$("play").onclick=()=>{
  if(timer){stop("Play day");return;}
  if(i>=N-1)i=0;
  $("play").textContent="Pause";
  timer=setInterval(()=>{i++; if(i>=N){ if(C.autoplay){i=0;} else {i=N-1;stop("Replay");} } draw();}, +$("speed").value);
};
$("speed").onchange=()=>{if(timer){stop("Play day");$("play").click();}};
if(C.compact){$("panel").style.display="none";$("ticks").style.display="none";$("clickhint").style.display="none";$("sv").style.minWidth="0";}
if(C.start==="end") i=N-1; else if(C.start==="zero") i=0; else { const mx=Math.max(...D.Tin), mn=Math.min(...D.Tin); i = (mx-mn>0.2) ? D.Tin.indexOf(mx) : D.Tdb.indexOf(Math.max(...D.Tdb)); if(i<0)i=0; }
draw(); animatePipes();
if(C.autoplay){ i=0; $("play").click(); }
</script>
"""
