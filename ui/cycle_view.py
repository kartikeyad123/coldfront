"""
cycle_view.py - Animated refrigeration-loop diagram for the Chiller Room.
Refrigerant parcels travel around the loop; their colour follows the local
refrigerant temperature, and their speed follows the refrigerant mass flow.
"""

import json

C2K = 273.15


def cycle_html(cyc, m_ref, Q_evap_kW, W_kW):
    T = [round(t - C2K, 1) for t in cyc.T]
    data = dict(T=T, P=[round(cyc.P_evap / 1e3), round(cyc.P_cond / 1e3), round(cyc.P_cond / 1e3),
                        round(cyc.P_evap / 1e3)],
                h=[round(h / 1e3, 1) for h in cyc.h], m=round(m_ref, 3), Q=round(Q_evap_kW),
                W=round(W_kW), Qc=round(Q_evap_kW + W_kW), cop=round(cyc.cop, 2))
    return _T.replace("__D__", json.dumps(data))


_T = r"""
<div style="font-family:'IBM Plex Mono',monospace;color:#E6E8EB">
<style>@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@600&display=swap');
.t{font-family:'Inter',sans-serif;font-weight:600;letter-spacing:.06em}</style>
<svg viewBox="0 0 760 430" width="100%" style="background:#0E1116;border:1px solid #2A313B;border-radius:4px">
 <path id="loop" d="M150 330 H610 V100 H150 Z" fill="none" stroke="#2A313B" stroke-width="16"/>
 <rect x="250" y="70" width="260" height="60" rx="4" fill="#151A21" stroke="#D9A441" stroke-width="2"/>
 <text x="380" y="88" text-anchor="middle" class="t" font-size="13" fill="#D9A441">CONDENSER</text>
 <text id="qc" x="380" y="124" text-anchor="middle" font-size="12" fill="#E6E8EB">--</text>
 <rect x="250" y="300" width="260" height="60" rx="4" fill="#151A21" stroke="#6FA8DC" stroke-width="2"/>
 <text x="380" y="318" text-anchor="middle" class="t" font-size="13" fill="#6FA8DC">EVAPORATOR</text>
 <text id="qe" x="380" y="354" text-anchor="middle" font-size="12" fill="#E6E8EB">--</text>
 <circle cx="610" cy="215" r="42" fill="#151A21" stroke="#C77B4A" stroke-width="2"/>
 <g transform="translate(610 215)"><g id="imp"><path d="M0 0 L30 -8 L30 8Z" fill="#C77B4A"/><path d="M0 0 L30 -8 L30 8Z" fill="#C77B4A" transform="rotate(120)"/><path d="M0 0 L30 -8 L30 8Z" fill="#C77B4A" transform="rotate(240)"/></g></g>
 <text x="662" y="210" text-anchor="start" class="t" font-size="13" fill="#C77B4A">COMPRESSOR</text>
 <text id="wc" x="662" y="228" text-anchor="start" font-size="12" fill="#E6E8EB">--</text>
 <path d="M135 200 L165 200 L150 230 Z M135 230 L165 230 L150 200 Z" fill="#A9B0BA"/>
 <text x="172" y="220" text-anchor="start" class="t" font-size="13" fill="#A9B0BA">VALVE</text>
 <g id="dots"></g>
 <g id="labels"></g>
 <text x="380" y="215" text-anchor="middle" class="t" font-size="13" fill="#8A929C">COP</text>
 <text id="cop" x="380" y="250" text-anchor="middle" class="t" font-size="34" fill="#FFFFFF">--</text>
 <text id="mf" x="380" y="275" text-anchor="middle" font-size="12" fill="#8A929C">--</text>
 <text x="380" y="30" text-anchor="middle" font-size="11" fill="#8A929C">heat rejected to condenser water ↑</text>
 <text x="380" y="400" text-anchor="middle" font-size="11" fill="#8A929C">↑ heat taken from chilled water</text>
</svg></div>
<script>
const D=__D__, NS="http://www.w3.org/2000/svg", $=i=>document.getElementById(i);
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);p.appendChild(e);return e;}
$("qc").textContent=`${D.Qc} kW out`; $("qe").textContent=`${D.Q} kW in`; $("wc").textContent=`${D.W} kW work`;
$("cop").textContent=D.cop.toFixed(2); $("mf").textContent=`refrigerant ${D.m} kg/s`;
// state labels: 1 compressor in (bottom-right), 2 compressor out (top-right), 3 condenser out (top-left), 4 valve out (bottom-left)
const pos=[[625,345],[625,88],[95,88],[95,345]], anchor=["start","start","end","end"];
pos.forEach((p,k)=>{const g=el("g",{},$("labels"));
  el("circle",{cx:k<2?610:150,cy:k%3===0?330:100,r:9,fill:"#0E1116",stroke:"#FFFFFF","stroke-width":2},g);
  const t=el("text",{x:k<2?610:150,y:(k%3===0?334:104),"text-anchor":"middle","font-size":11,fill:"#FFFFFF"},g); t.textContent=k+1;
  const x=k<2?640:120, y=k%3===0?372:58, a=k<2?"start":"end";
  [[`${D.T[k]} °C`,0],[`${D.P[k]} kPa`,15],[`h ${D.h[k]} kJ/kg`,30]].forEach(([s,dy])=>{const tt=el("text",{x:x,y:y+dy,"text-anchor":a,"font-size":11,fill:"#E6E8EB"},g);tt.textContent=s;});
});
const path=$("loop"), L=path.getTotalLength(), dots=[];
for(let k=0;k<26;k++) dots.push(el("circle",{r:6,fill:"#6FA8DC"},$("dots")));
// temperature along the loop (piecewise): bottom (evap) T4->T1, right (compressor) T1->T2, top (condenser) T2->T3, left (valve) T3->T4
const seg=[460,230,460,230]; const tot=seg.reduce((a,b)=>a+b);
function tAt(d){let u=d, k=0; while(u>seg[k]){u-=seg[k];k++;} const f=u/seg[k];
  const a=[D.T[3],D.T[0],D.T[1],D.T[2]][k], b=[D.T[0],D.T[1],D.T[2],D.T[3]][k]; return a+(b-a)*f;}
const Tmin=Math.min(...D.T), Tmax=Math.max(...D.T);
function col(T){const f=(T-Tmin)/Math.max(1,Tmax-Tmin); const c1=[111,168,220], c2=[217,164,65];
  return `rgb(${c1.map((v,i)=>Math.round(v+(c2[i]-v)*f))})`;}
let off=0; const speed=0.6+Math.min(3,D.m*0.4);
function tick(){off=(off+speed)%L;
  dots.forEach((d,k)=>{const s=(off+k*L/dots.length)%L, p=path.getPointAtLength(s); d.setAttribute("cx",p.x); d.setAttribute("cy",p.y); d.setAttribute("fill",col(tAt(s/L*tot)));});
  $("imp").setAttribute("transform",`rotate(${(off*4)%360})`); requestAnimationFrame(tick);}
tick();
</script>
"""
