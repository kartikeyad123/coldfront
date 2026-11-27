"""
cycle_view.py - Animated refrigeration-loop diagram for the Chiller lab.
Refrigerant parcels travel around the loop. Their colour follows the local
temperature, their look follows the phase (solid = liquid, hollow = vapor) and
their speed follows the mass flow. Click a component for its numbers.
Pure visualization: every value is passed in from the solved cycle.
"""

import json
import CoolProp.CoolProp as CP

C2K = 273.15


def cycle_html(cyc, m_ref, Q_evap_kW, W_kW, eta=None):
    T = [round(t - C2K, 1) for t in cyc.T]
    try:
        x4 = float(CP.PropsSI("Q", "P", cyc.P_evap, "H", cyc.h[3], cyc.fluid))
    except Exception:
        x4 = 0.25
    x4 = min(max(x4, 0.0), 1.0)
    data = dict(T=T, P=[round(cyc.P_evap / 1e3), round(cyc.P_cond / 1e3), round(cyc.P_cond / 1e3),
                        round(cyc.P_evap / 1e3)],
                h=[round(h / 1e3, 1) for h in cyc.h], m=round(m_ref, 3), Q=round(Q_evap_kW),
                W=round(W_kW), Qc=round(Q_evap_kW + W_kW), cop=round(cyc.cop, 2), car=round(cyc.cop_carnot, 2),
                x4=round(x4, 3), eta=round(eta if eta is not None else (cyc.h2s - cyc.h[0]) / max(cyc.h[1] - cyc.h[0], 1e-9), 3),
                Te=round(cyc.T_evap - C2K, 1), Tc=round(cyc.T_cond - C2K, 1),
                qe=round(cyc.q_evap / 1e3, 1), w=round(cyc.w_comp / 1e3, 1), qc=round(cyc.q_cond / 1e3, 1))
    return _T.replace("__D__", json.dumps(data))


_T = r"""
<div id="cv" style="font-family:'Inter',sans-serif;color:#E6E8EB">
<style>@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@400;500;600&display=swap');
html,body{margin:0;background:transparent}
#cv svg text{font-family:'IBM Plex Mono',monospace}
#cv .t{font-family:'Inter',sans-serif;font-weight:600;letter-spacing:.06em}
#cv .c{cursor:pointer} #cv .c .f{transition:stroke-width .15s} #cv .c:hover .f{stroke-width:3.2} #cv .c.sel .f{stroke-width:3.6}
#cv .c.sel{filter:drop-shadow(0 0 7px rgba(230,232,235,.55))}
#cp{margin-top:8px;background:#151A21;border:1px solid #2A313B;border-radius:6px;padding:12px 14px}
#cp h4{margin:0 0 2px 0;font-size:15px;font-weight:600}
#cp p{margin:4px 0 10px 0;font-size:13.5px;color:#B4BAC2;line-height:1.45}
#cp .g{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}
@media (max-width:640px){#cp .g{grid-template-columns:repeat(2,1fr)}}
#cp .gl{background:#0E1116;border:1px solid #2A313B;border-radius:6px;padding:6px 8px}
#cp .gl span{display:block;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:#8A929C}
#cp .gl b{font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:500}
</style>
<svg viewBox="-14 0 836 440" width="100%" style="background:#0E1116;border:1px solid #2A313B;border-radius:6px">
 <path d="M610 215 V100 H150 V215" fill="none" stroke="#3B2F1E" stroke-width="18"/>
 <path d="M150 215 V330 H610 V215" fill="none" stroke="#1C2836" stroke-width="18"/>
 <path id="loop" d="M150 330 H610 V100 H150 Z" fill="none" stroke="none"/>
 <text x="560" y="150" text-anchor="end" font-size="10.5" fill="#D9A441" id="hp">HIGH PRESSURE</text>
 <text x="560" y="292" text-anchor="end" font-size="10.5" fill="#6FA8DC" id="lp">LOW PRESSURE</text>
 <g id="dots"></g>
 <g class="c" data-c="cond"><rect class="f" x="250" y="70" width="260" height="60" rx="4" fill="#151A21" stroke="#D9A441" stroke-width="2"/>
  <text x="380" y="93" text-anchor="middle" class="t" font-size="13" fill="#D9A441">CONDENSER</text>
  <text id="qc" x="380" y="116" text-anchor="middle" font-size="12" fill="#E6E8EB">--</text></g>
 <g class="c" data-c="evap"><rect class="f" x="250" y="300" width="260" height="60" rx="4" fill="#151A21" stroke="#6FA8DC" stroke-width="2"/>
  <text x="380" y="323" text-anchor="middle" class="t" font-size="13" fill="#6FA8DC">EVAPORATOR</text>
  <text id="qe" x="380" y="346" text-anchor="middle" font-size="12" fill="#E6E8EB">--</text></g>
 <g class="c" data-c="comp"><circle class="f" cx="610" cy="215" r="42" fill="#151A21" stroke="#C77B4A" stroke-width="2"/>
  <g transform="translate(610 215)"><g id="imp"><path d="M0 0 L30 -8 L30 8Z" fill="#C77B4A"/><path d="M0 0 L30 -8 L30 8Z" fill="#C77B4A" transform="rotate(120)"/><path d="M0 0 L30 -8 L30 8Z" fill="#C77B4A" transform="rotate(240)"/></g></g>
  <text x="662" y="210" text-anchor="start" class="t" font-size="13" fill="#C77B4A">COMPRESSOR</text>
  <text id="wc" x="662" y="228" text-anchor="start" font-size="12" fill="#E6E8EB">--</text></g>
 <g class="c" data-c="valve"><rect x="118" y="186" width="64" height="58" fill="transparent"/>
  <path class="f" d="M132 198 L168 198 L150 215 Z M132 232 L168 232 L150 215 Z" fill="#151A21" stroke="#A9B0BA" stroke-width="2"/>
  <text x="112" y="212" text-anchor="end" class="t" font-size="13" fill="#A9B0BA">VALVE</text>
  <text id="vx" x="112" y="230" text-anchor="end" font-size="12" fill="#E6E8EB">--</text></g>
 <g id="labels"></g>
 <text x="380" y="200" text-anchor="middle" class="t" font-size="13" fill="#8A929C">COP</text>
 <text id="cop" x="380" y="238" text-anchor="middle" class="t" font-size="34" fill="#FFFFFF">--</text>
 <text id="mf" x="380" y="262" text-anchor="middle" font-size="12" fill="#A3ABB5">--</text>
 <text x="380" y="30" text-anchor="middle" font-size="11.5" fill="#A3ABB5">heat rejected to condenser water ↑</text>
 <text x="380" y="398" text-anchor="middle" font-size="11.5" fill="#A3ABB5">↑ heat taken from chilled water</text>
 <text x="20" y="426" font-size="11.5" fill="#A3ABB5"><tspan fill="#E6E8EB">●</tspan> liquid   <tspan fill="#E6E8EB" dx="10">○</tspan> vapor   <tspan dx="14">colour: blue cold → yellow hot</tspan></text>
 <text x="806" y="426" text-anchor="end" font-size="12" fill="#6FA8DC">click a component</text>
</svg>
<div id="cp"></div></div>
<script>
const D=__D__, NS="http://www.w3.org/2000/svg", $=i=>document.getElementById(i);
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);p.appendChild(e);return e;}
$("qc").textContent=`${D.Qc.toLocaleString()} kW of heat out`; $("qe").textContent=`${D.Q.toLocaleString()} kW of heat in`; $("wc").textContent=`${D.W.toLocaleString()} kW work in`;
$("vx").textContent=`${Math.round(D.x4*100)} % flashes`;
$("cop").textContent=D.cop.toFixed(2); $("mf").textContent=`refrigerant ${D.m.toFixed(1)} kg/s`;
$("hp").textContent=`HIGH PRESSURE · ${D.P[1].toLocaleString()} kPa`; $("lp").textContent=`LOW PRESSURE · ${D.P[0].toLocaleString()} kPa`;
// state labels: 1 compressor in (bottom-right), 2 compressor out (top-right), 3 condenser out (top-left), 4 valve out (bottom-left)
const PH=["vapor","hot vapor","liquid",`liquid + ${Math.round(D.x4*100)} % vapor`];
[0,1,2,3].forEach(k=>{const g=el("g",{},$("labels"));
  el("circle",{cx:k<2?610:150,cy:k%3===0?330:100,r:10,fill:"#0E1116",stroke:"#FFFFFF","stroke-width":2},g);
  const t=el("text",{x:k<2?610:150,y:(k%3===0?334:104),"text-anchor":"middle","font-size":11,fill:"#FFFFFF"},g); t.textContent=k+1;
  const x=k<2?634:126, y=k%3===0?352:44, a=k<2?"start":"end";
  [[PH[k],0,"#FFFFFF"],[`${D.T[k]} °C`,15,"#E6E8EB"],[`${D.P[k].toLocaleString()} kPa`,30,"#E6E8EB"],[`h ${D.h[k]} kJ/kg`,45,"#A3ABB5"]].forEach(([s,dy,c])=>{const tt=el("text",{x:x,y:y+dy,"text-anchor":a,"font-size":11,fill:c},g);tt.textContent=s;});
});
const path=$("loop"), L=path.getTotalLength(), dots=[];
for(let k=0;k<34;k++) dots.push(el("circle",{r:5,fill:"#6FA8DC",stroke:"#6FA8DC","stroke-width":1.6},$("dots")));
// along the loop: bottom (evaporator) 4->1, right (compressor) 1->2, top (condenser) 2->3, left (valve) 3->4
const seg=[460,230,460,230], tot=1380;
function at(d){let u=d,k=0; while(u>seg[k]){u-=seg[k];k++;} const f=u/seg[k];
  const Ta=[D.T[3],D.T[0],D.T[1],D.T[2]][k], Tb=[D.T[0],D.T[1],D.T[2],D.T[3]][k];
  // temperature: flat while boiling or condensing, changes in the compressor and the valve
  let T = k===0 ? (f<0.85?D.T[3]:D.T[3]+(D.T[0]-D.T[3])*(f-0.85)/0.15) : k===2 ? (f<0.15?D.T[1]+(D.Tc-D.T[1])*f/0.15:(f<0.9?D.Tc:D.Tc+(D.T[2]-D.Tc)*(f-0.9)/0.1)) : (k===1 ? (f<0.5?Ta:Tb) : (f<0.5?Ta:Tb));
  // vapor fraction: boils along the evaporator, condenses along the condenser, flashes at the valve
  const v = k===0 ? Math.min(1,D.x4+(1-D.x4)*f/0.85) : k===1 ? 1 : k===2 ? Math.max(0,1-Math.max(0,f-0.15)/0.75) : (f<0.5?0:D.x4);
  return {T,v};}
const Tmin=Math.min(...D.T), Tmax=Math.max(...D.T);
function col(T){const f=Math.max(0,Math.min(1,(T-Tmin)/Math.max(1,Tmax-Tmin))); const c1=[111,168,220], c2=[217,164,65];
  return `rgb(${c1.map((v,i)=>Math.round(v+(c2[i]-v)*f))})`;}
let off=0; const speed=0.6+Math.min(3,D.m*0.25);
function tick(){off=(off+speed)%L;
  dots.forEach((d,k)=>{const s=(off+k*L/dots.length)%L, p=path.getPointAtLength(s), q=at(s/L*tot), c=col(q.T);
    d.setAttribute("cx",p.x); d.setAttribute("cy",p.y); d.setAttribute("fill",c); d.setAttribute("stroke",c);
    d.setAttribute("fill-opacity",1-0.9*q.v); d.setAttribute("r",3.6+2.6*q.v);});
  $("imp").setAttribute("transform",`rotate(${(off*4)%360})`); requestAnimationFrame(tick);}
tick();
// ---- component panels
const SC={normal:"#6FA8DC",high:"#A78BDA",ineff:"#D97B3F",crit:"#E06A50"};
const pr=D.P[1]/Math.max(D.P[0],1), lift=D.Tc-D.Te;
const INFO={
 comp:()=>{ const st = D.T[1]>110?["crit","discharge too hot"]:(D.eta<0.7?["ineff","low efficiency: extra work becomes heat"]:(pr>4?["high","high pressure ratio"]:["normal","running"]));
   return {t:"Compressor  (1 → 2)", st, why:`Squeezes cold low-pressure vapor into hot high-pressure vapor. This is the only place work goes in. The bigger the lift (${lift.toFixed(0)} K here), the harder it works.`,
   g:[["Temperature",`${D.T[0]} → ${D.T[1]} °C`],["Pressure",`${D.P[0]} → ${D.P[1]} kPa`],["Power",`${D.W.toLocaleString()} kW`],["Efficiency",`η ${D.eta.toFixed(2)}`]]};},
 cond:()=>({t:"Condenser  (2 → 3)", st:["normal","rejecting heat"], why:"The hot vapor gives its heat to the condenser water and turns into liquid. It gives up the cooling load plus the compressor work.",
   g:[["Temperature",`${D.T[1]} → ${D.T[2]} °C`],["Heat out",`${D.Qc.toLocaleString()} kW`],["Power","0 kW (no work)"],["Condensing at",`${D.Tc} °C`]]}),
 valve:()=>{ const st = D.x4>0.35?["ineff","a lot flashes to vapor before the evaporator"]:["normal","throttling"];
   return {t:"Expansion valve  (3 → 4)", st, why:`Drops the pressure. The liquid turns very cold and ${Math.round(D.x4*100)} % of it boils at once. No heat or work crosses, so the enthalpy stays the same (h₄ = h₃).`,
   g:[["Temperature",`${D.T[2]} → ${D.T[3]} °C`],["Pressure",`${D.P[2]} → ${D.P[3]} kPa`],["Power","0 kW (no work)"],["Vapor after",`${Math.round(D.x4*100)} %`]]};},
 evap:()=>({t:"Evaporator  (4 → 1)", st:["normal","cooling"], why:"The cold mixture boils by taking heat from the chilled water. This is the cooling the data hall asked for.",
   g:[["Temperature",`${D.T[3]} → ${D.T[0]} °C`],["Cooling",`${D.Q.toLocaleString()} kW`],["Power","0 kW (no work)"],["Per kg",`${D.qe} kJ/kg`]]}),
};
let sel="comp";
function show(){ const p=INFO[sel]();
  $("cp").innerHTML=`<h4>${p.t}</h4><p>${p.why}</p><div class="g"><div class="gl"><span>Status</span><b style="color:${SC[p.st[0]]}">● ${p.st[1]}</b></div>`+
    p.g.map(([a,b])=>`<div class="gl"><span>${a}</span><b>${b}</b></div>`).join("")+`</div>`;
  document.querySelectorAll("#cv .c").forEach(g=>g.classList.toggle("sel",g.dataset.c===sel)); fit(); }
document.querySelectorAll("#cv .c").forEach(g=>g.addEventListener("click",()=>{sel=g.dataset.c;show();}));
function fit(){ try{ const fe=window.frameElement; if(!fe) return; const h=Math.ceil($("cv").getBoundingClientRect().height)+8;
  if(Math.abs(parseFloat(fe.style.height||0)-h)>3){ fe.style.height=h+"px"; fe.setAttribute("height",h); } }catch(e){} }
show(); try{ new ResizeObserver(fit).observe($("cv")); }catch(e){}
</script>
"""
