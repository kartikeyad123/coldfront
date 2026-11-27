"""
kids_view.py - "Build a chiller": a short game for visitors with no engineering
background. Level 1: put the four parts of a chiller in the right places and
watch the refrigerant go round. Level 2: choose how cold to make the water.
Pure interface. The numbers shown come from the same model as the rest of the
app and are passed in: one solved refrigeration cycle, and a table of solved
days (one per water temperature).
"""
import json


SOUND = True        # set by the app from the Sound switch


def kids_html(cycle, table, limit=27.0):
    from .art import ART
    from .fx import SYNTH
    """cycle: dict(T=[4], P=[4], x4); table: list of dict(T, peak, bill, pue)."""
    return _T.replace("__SYNTH__", SYNTH).replace("__SND__", json.dumps(bool(SOUND))).replace("__ART__", json.dumps(dict(hot=ART["hot"], ok=ART["ok"], cost=ART["cost"]))).replace("__C__", json.dumps(cycle)).replace("__TAB__", json.dumps(table)).replace("__LIM__", json.dumps(limit))


_T = r"""
<div id="kg" style="position:relative">
<div id="pop"><div class="box"><button class="x" id="popx" aria-label="Close">×</button><div id="popb"></div><button class="big" id="popok">Continue</button></div></div>
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500&family=Inter:wght@400;500;600;700&display=swap');
html,body{margin:0;background:transparent}
#kg{font-family:'Inter',sans-serif;color:#E6E8EB;max-width:980px;margin:0 auto;user-select:none;-webkit-user-select:none}
#kg h2{font-size:26px;margin:0 0 4px 0;font-weight:700}
#kg .sub{color:#B4BAC2;font-size:16px;margin-bottom:12px}
#kg .steps{display:flex;gap:8px;margin-bottom:12px}
#kg .steps span{flex:1;text-align:center;padding:7px;border-radius:999px;border:1px solid #2A313B;color:#8A929C;font-size:13.5px;font-weight:600}
#kg .steps span.on{border-color:#6FA8DC;color:#0E1116;background:#6FA8DC}
#kg .steps span.done{border-color:#8FB39A;color:#8FB39A}
#stage{position:relative;background:#0E1116;border:1px solid #2A313B;border-radius:12px;overflow:hidden}
#stage svg{display:block;width:100%}
.slot{position:absolute;transform:translate(-50%,-50%);width:17%;height:20%;border:2.5px dashed #5E6670;border-radius:12px;display:flex;align-items:center;justify-content:center;
  color:#8A929C;font-size:13px;text-align:center;background:rgba(21,26,33,.92);transition:border-color .15s,background .15s;padding:4px;box-sizing:border-box}
.slot.hot{border-color:#6FA8DC;background:#18232F}
.slot.full{border-style:solid;border-color:#8FB39A;background:#151A21}
.slot.bad{animation:shake .35s}
@keyframes shake{25%{transform:translate(-56%,-50%)}75%{transform:translate(-44%,-50%)}}
.tag{position:absolute;background:rgba(14,17,22,.88);padding:1px 8px;border-radius:6px;font-size:13px;font-weight:600;letter-spacing:.06em;color:#B4BAC2;transform:translateX(-50%);white-space:nowrap;text-align:center}
#tray{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:12px;min-height:118px}
.part{background:#151A21;border:2px solid #3A4350;border-radius:12px;padding:10px;cursor:grab;touch-action:none;display:flex;gap:10px;align-items:center}
.part:hover{border-color:#E6E8EB}.part.pick{border-color:#6FA8DC;box-shadow:0 0 0 3px rgba(111,168,220,.25)}
.part svg{width:54px;height:54px;flex:none}.part b{display:block;font-size:15.5px}.part small{color:#B4BAC2;font-size:13px;line-height:1.3;display:block}
.part.inslot{border:0;background:transparent;padding:0;cursor:default;flex-direction:column;gap:2px}.part.inslot small{display:none}.part.inslot svg{width:46px;height:46px}.part.inslot b{font-size:13px}
#ghost{position:fixed;pointer-events:none;z-index:99;opacity:.92;width:210px}
#msg{margin-top:12px;background:#151A21;border:1px solid #2A313B;border-left:4px solid #6FA8DC;border-radius:8px;padding:12px 16px;font-size:16px;line-height:1.45;min-height:26px}
#msg.good{border-left-color:#8FB39A}#msg.oops{border-left-color:#D97B3F}
#kg button.big{font:inherit;font-size:16px;font-weight:600;background:#6FA8DC;color:#0E1116;border:0;border-radius:8px;padding:10px 20px;cursor:pointer;margin-top:12px}
#kg button.big:hover{background:#8BBBE6}#kg button.ghost{font:inherit;font-size:15px;background:transparent;color:#E6E8EB;border:1px solid #3A4350;border-radius:8px;padding:9px 16px;cursor:pointer;margin:12px 0 0 8px}
.read{position:absolute;transform:translate(-50%,-50%);background:#151A21;border:1px solid #3A4350;border-radius:10px;padding:7px 10px;font-size:12.5px;line-height:1.5;white-space:nowrap;display:none}
.read b{font-family:'IBM Plex Mono',monospace;font-weight:500;font-size:13.5px}.read .n{display:inline-block;width:20px;height:20px;border-radius:50%;border:2px solid #fff;text-align:center;line-height:20px;font-size:12px;margin-right:6px;font-weight:700}
.read.lit{border-color:#fff;box-shadow:0 0 0 3px rgba(255,255,255,.18)}
.lesson{display:none;margin-top:12px;grid-template-columns:repeat(3,1fr);gap:10px}
.lesson div{background:#151A21;border:1px solid #2A313B;border-radius:10px;padding:12px 14px;font-size:15px;line-height:1.45}
.lesson span{display:block;font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:#6FA8DC;font-weight:700;margin-bottom:4px}
#l2{display:none}
#l2 .row{display:grid;grid-template-columns:1.1fr 1fr;gap:14px}
@media (max-width:720px){#l2 .row,#tray,.lesson{grid-template-columns:1fr 1fr}#l2 .row{grid-template-columns:1fr}}
#l2 .box{background:#151A21;border:1px solid #2A313B;border-radius:12px;padding:16px}
#l2 input[type=range]{width:100%;accent-color:#6FA8DC;height:34px}
#l2 .big{font-family:'IBM Plex Mono',monospace;font-size:34px;font-weight:500}
#l2 .meter{height:18px;background:#0E1116;border:1px solid #2A313B;border-radius:9px;position:relative;margin:6px 0 14px 0;overflow:hidden}
#l2 .meter i{position:absolute;left:0;top:0;bottom:0;border-radius:9px;transition:width .2s,background .2s}
#l2 .meter u{position:absolute;top:-3px;bottom:-3px;width:2px;background:#E6E8EB}
#l2 .lab{display:flex;justify-content:space-between;font-size:14px;color:#B4BAC2}
#racks{display:grid;grid-template-columns:repeat(8,1fr);gap:6px;margin-top:10px}
#racks i{height:54px;border-radius:4px;transition:background .2s}
#stars{font-size:38px;letter-spacing:6px;color:#D9A441}
#pop{display:none;position:absolute;inset:0;background:rgba(5,7,10,.78);z-index:20;align-items:flex-start;justify-content:center;padding-top:70px}
#pop .box{background:#151A21;border:1px solid #3A4350;border-radius:14px;padding:22px 26px;max-width:520px;width:86%;position:relative;text-align:center;box-shadow:0 12px 40px rgba(0,0,0,.6)}
#pop .x{position:absolute;right:12px;top:8px;font-size:26px;cursor:pointer;color:#A3ABB5;background:none;border:0;line-height:1}
#pop .x:hover{color:#fff}
#pop .st{font-size:46px;letter-spacing:8px;color:#D9A441}
#pop h3{font-size:24px;margin:6px 0 8px 0}
#pop p{font-size:16px;line-height:1.5;color:#C3C9D1;margin:0 0 6px 0}
#pop .hint{background:#0E1116;border-left:3px solid #6FA8DC;border-radius:0 8px 8px 0;padding:8px 12px;text-align:left;font-size:15px;margin-top:10px}
</style>
<h2>Build a chiller</h2>
<div class="sub">The machine that keeps an AI data center from melting. No instructions needed: just try.</div>
<div class="steps"><span id="s1" class="on">1 · Build it</span><span id="s2">2 · Watch it run</span><span id="s3">3 · Keep the servers cool</span></div>

<div id="l1">
 <div id="stage">
  <svg viewBox="0 0 900 480">
   <path d="M700 240 V110 H200 V240" fill="none" stroke="#3B2F1E" stroke-width="22" stroke-linejoin="round"/>
   <path d="M200 240 V370 H700 V240" fill="none" stroke="#1C2836" stroke-width="22" stroke-linejoin="round"/>
   <path id="kloop" d="M200 370 H700 V110 H200 Z" fill="none" stroke="none"/>
   <g id="arrows" fill="none" stroke="#8A929C" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <path d="M585 362 l10 8 l-10 8"/><path d="M692 175 l8 -10 l8 10"/><path d="M315 118 l-10 -8 l10 -8"/><path d="M208 305 l-8 10 l-8 -10"/></g>
   <g id="kdots"></g>
   <g id="outside" opacity=".9"><path d="M300 44 q8 -14 0 -26 M330 44 q8 -14 0 -26 M570 44 q8 -14 0 -26 M600 44 q8 -14 0 -26" stroke="#D97B3F" stroke-width="3" fill="none" stroke-linecap="round" opacity="0" id="heatout"/></g>
   <g id="srv"><rect x="330" y="436" width="240" height="34" rx="4" fill="#151A21" stroke="#3A4350"/><g id="srvbars"></g>
    <path d="M385 430 q8 -12 0 -22 M450 430 q8 -12 0 -22 M515 430 q8 -12 0 -22" stroke="#D97B3F" stroke-width="3" fill="none" stroke-linecap="round" opacity=".0" id="heatin"/></g>
  </svg>
  <div class="tag" style="left:50%;top:1.5%">OUTSIDE AIR<br><span style="font-weight:400;color:#8A929C">heat has to leave here</span></div>
  <div class="tag" style="left:50%;top:91.5%;background:transparent">SERVERS <span style="font-weight:400;color:#8A929C">· heat comes from here</span></div>
  <div class="tag" style="left:77.8%;top:64%;color:#D9A441">▲ gas gets squeezed</div>
  <div class="tag" style="left:22.2%;top:33%;color:#6FA8DC">▼ pressure released</div>
  <div class="slot" data-slot="cond" style="left:50%;top:22.9%">?</div>
  <div class="slot" data-slot="comp" style="left:77.8%;top:50%">?</div>
  <div class="slot" data-slot="evap" style="left:50%;top:77.1%">?</div>
  <div class="slot" data-slot="valve" style="left:22.2%;top:50%">?</div>
  <div class="read" id="r1" style="left:83%;top:80%"></div><div class="read" id="r2" style="left:83%;top:19%"></div>
  <div class="read" id="r3" style="left:17%;top:19%"></div><div class="read" id="r4" style="left:17%;top:80%"></div>
 </div>
 <div id="tray"></div>
 <div id="msg">Drag each part to where it belongs in the loop. (Or tap a part, then tap a spot.)</div>
 <div id="lesson" class="lesson"></div>
 <div id="btns"></div>
</div>

<div id="l2">
 <div class="row">
  <div class="box">
   <div style="font-size:18px;font-weight:600">How cold should the chiller make the water?</div>
   <div class="sub" style="margin:4px 0 10px 0">Slide it. Watch the servers and the bill.</div>
   <div class="big"><span id="tv">10</span> °C</div>
   <input id="tw" type="range" min="6" max="20" step="1" value="6"/>
   <div class="lab"><span>ice cold</span><span>barely cool</span></div>
   <button class="big" id="lock">Lock it in</button><button class="ghost" id="give2" style="display:none">I give up: show me</button>
  </div>
  <div class="box">
   <div class="lab"><span>Hottest server today</span><b id="pk"></b></div>
   <div class="meter"><i id="pkbar"></i><u id="pklim"></u></div>
   <div class="lab"><span>Cooling bill for the day</span><b id="bl"></b></div>
   <div class="meter"><i id="blbar"></i></div>
   <div class="lab"><span>The server hall</span><b id="ok"></b></div>
   <div id="racks"></div>
  </div>
 </div>
 <div id="msg2" style="margin-top:12px;background:#151A21;border:1px solid #2A313B;border-left:4px solid #6FA8DC;border-radius:8px;padding:12px 16px;font-size:16px;line-height:1.45">Goal: keep every server under <b id="limtxt"></b> and spend as little as you can.</div>
 <div id="lesson2" class="lesson"></div>
 <div id="btns2"></div>
</div>
</div>
<script>
__SYNTH__
const SND=__SND__;
function fxk(cue,color,times,shake){ if(SND) cfCue(window,cue); if(color) cfFlash(document,color,times||1,!!shake); }
const C=__C__, TAB=__TAB__, LIM=__LIM__, ARTS=__ART__;
const $=id=>document.getElementById(id), NS="http://www.w3.org/2000/svg";
function sv(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);p.appendChild(e);return e;}
const ICON={
 comp:'<svg viewBox="0 0 60 60"><circle cx="30" cy="30" r="24" fill="#151A21" stroke="#C77B4A" stroke-width="3"/><g class="spin" style="transform-origin:30px 30px"><path d="M30 30 L50 24 L50 36Z" fill="#C77B4A"/><path d="M30 30 L50 24 L50 36Z" fill="#C77B4A" transform="rotate(120 30 30)"/><path d="M30 30 L50 24 L50 36Z" fill="#C77B4A" transform="rotate(240 30 30)"/></g></svg>',
 cond:'<svg viewBox="0 0 60 60"><rect x="6" y="18" width="48" height="30" rx="4" fill="#151A21" stroke="#D9A441" stroke-width="3"/><path d="M14 26 h32 M14 33 h32 M14 40 h32" stroke="#D9A441" stroke-width="2.5"/><path d="M20 12 q4 -5 0 -9 M30 12 q4 -5 0 -9 M40 12 q4 -5 0 -9" stroke="#D97B3F" stroke-width="2.5" fill="none" stroke-linecap="round"/></svg>',
 valve:'<svg viewBox="0 0 60 60"><path d="M12 14 L48 14 L30 30 Z M12 46 L48 46 L30 30 Z" fill="#151A21" stroke="#A9B0BA" stroke-width="3" stroke-linejoin="round"/><path d="M30 30 h18 M48 24 v12" stroke="#A9B0BA" stroke-width="3" stroke-linecap="round"/></svg>',
 evap:'<svg viewBox="0 0 60 60"><rect x="6" y="12" width="48" height="30" rx="4" fill="#151A21" stroke="#6FA8DC" stroke-width="3"/><path d="M14 20 h32 M14 27 h32 M14 34 h32" stroke="#6FA8DC" stroke-width="2.5"/><path d="M30 46 v10 M25 49 l10 5 M35 49 l-10 5" stroke="#6FA8DC" stroke-width="2.2" stroke-linecap="round"/></svg>'};
const PARTS={
 comp:{n:"Compressor",d:"I squeeze the gas hard. Squeezing makes it hot.",no:"The compressor squeezes. Look for where the gas gets squeezed."},
 cond:{n:"Condenser",d:"I let hot gas dump its heat. It turns into liquid.",no:"The condenser throws heat away. Where can heat leave?"},
 valve:{n:"Valve",d:"I release the pressure. The liquid turns icy cold.",no:"The valve lets the pressure go. Look for where pressure is released."},
 evap:{n:"Evaporator",d:"I soak up heat. The cold liquid boils back to gas.",no:"The evaporator soaks up heat. Where is the heat coming from?"}};
let placed={}, pick=null, tries=0, drag=null, wrong=0, gave=false;
// ---------------------------------------------------------------- level 1: build
function card(k){const d=document.createElement("div");d.className="part";d.dataset.k=k;d.innerHTML=ICON[k]+`<div><b>${PARTS[k].n}</b><small>${PARTS[k].d}</small></div>`;return d;}
function tray(){const t=$("tray");t.innerHTML="";["valve","cond","evap","comp"].forEach(k=>{ if(placed[k])return; const c=card(k); t.appendChild(c);
   c.addEventListener("pointerdown",e=>startDrag(e,k,c)); }); if(!t.children.length) t.style.display="none";}
function say(t,cls){const m=$("msg");m.className=cls||"";m.innerHTML=t;}
function slotAt(x,y){return [...document.querySelectorAll(".slot")].find(s=>{const r=s.getBoundingClientRect();return x>=r.left-10&&x<=r.right+10&&y>=r.top-10&&y<=r.bottom+10;});}
function startDrag(e,k,c){ e.preventDefault(); const g=c.cloneNode(true); g.id="ghost"; document.body.appendChild(g);
  drag={k,g,c,x0:e.clientX,y0:e.clientY,moved:false}; moveGhost(e);
  const mv=ev=>{ if(Math.abs(ev.clientX-drag.x0)+Math.abs(ev.clientY-drag.y0)>8) drag.moved=true; moveGhost(ev);
    document.querySelectorAll(".slot").forEach(s=>s.classList.remove("hot")); const s=slotAt(ev.clientX,ev.clientY); if(s&&!s.classList.contains("full")) s.classList.add("hot"); };
  const up=ev=>{ window.removeEventListener("pointermove",mv); window.removeEventListener("pointerup",up); g.remove();
    document.querySelectorAll(".slot").forEach(s=>s.classList.remove("hot"));
    const s=slotAt(ev.clientX,ev.clientY);
    if(drag.moved && s) drop(k,s); else if(!drag.moved){ pick = pick===k?null:k; document.querySelectorAll(".part").forEach(p=>p.classList.toggle("pick",p.dataset.k===pick)); if(pick) say(`<b>${PARTS[k].n}</b> picked. Now tap the spot where it belongs.`); }
    drag=null; };
  window.addEventListener("pointermove",mv); window.addEventListener("pointerup",up); }
function moveGhost(e){ if(drag){ drag.g.style.left=(e.clientX-105)+"px"; drag.g.style.top=(e.clientY-40)+"px"; } }
function drop(k,s){ if(s.classList.contains("full")) return; tries++;
  if(s.dataset.slot===k){ fxk("tick"); placed[k]=true; s.classList.add("full"); s.innerHTML=""; const c=card(k); c.classList.add("inslot"); s.appendChild(c); pick=null; tray();
    const left=4-Object.keys(placed).length; say(left? `Yes! The <b>${PARTS[k].n.toLowerCase()}</b> goes there. ${left} to go.` : "", "good"); if(!left) built(); }
  else { s.classList.remove("bad"); void s.offsetWidth; s.classList.add("bad"); say("Not there. "+PARTS[k].no,"oops"); wrong++; fxk("no","#E5574B");
    if(wrong>=3 && !$("giveup")){ $("btns").innerHTML='<button class="ghost" id="giveup" style="margin-left:0">I give up: show me</button>';
      $("giveup").onclick=()=>{ gave=true; ["comp","cond","valve","evap"].forEach(q=>{ if(!placed[q]) drop(q, document.querySelector(`.slot[data-slot=${q}]`)); }); }; } } }
document.querySelectorAll(".slot").forEach(s=>s.addEventListener("click",()=>{ if(pick) drop(pick,s); }));
// ---------------------------------------------------------------- level 1b: watch it run
const path=$("kloop"), L=path.getTotalLength(), dots=[];
const seg=[500,260,500,260], tot=1520;
function at(d){let u=d,k=0; while(u>seg[k]){u-=seg[k];k++;} const f=u/seg[k];
  const T = k===0 ? C.T[3] : k===1 ? (f<0.5?C.T[0]:C.T[1]) : k===2 ? (f<0.2?C.T[1]:C.T[2]) : (f<0.5?C.T[2]:C.T[3]);
  const v = k===0 ? Math.min(1,C.x4+(1-C.x4)*f/0.85) : k===1 ? 1 : k===2 ? Math.max(0,1-Math.max(0,f-0.15)/0.75) : (f<0.5?0:C.x4);
  return {T,v};}
const Tmin=Math.min(...C.T), Tmax=Math.max(...C.T);
function colr(T){const f=Math.max(0,Math.min(1,(T-Tmin)/Math.max(1,Tmax-Tmin))); const a=[111,168,220], b=[217,123,63];
  return `rgb(${a.map((v,i)=>Math.round(v+(b[i]-v)*f))})`;}
let off=0, running=false, lit=-1;
function tick(){ if(!running) return; off=(off+2.2)%L;
  dots.forEach((d,k)=>{const s=(off+k*L/dots.length)%L, p=path.getPointAtLength(s), q=at(s/L*tot), c=colr(q.T);
    d.setAttribute("cx",p.x); d.setAttribute("cy",p.y); d.setAttribute("fill",c); d.setAttribute("stroke",c); d.setAttribute("fill-opacity",1-0.9*q.v); d.setAttribute("r",4.5+3.5*q.v);});
  document.querySelectorAll(".spin").forEach(g=>g.style.transform=`rotate(${off*3}deg)`);
  const t=(off/40)%1; ["heatout","heatin"].forEach(id=>{$(id).setAttribute("opacity",0.9*(1-t)); $(id).setAttribute("transform",`translate(0 ${-10*t})`);});
  requestAnimationFrame(tick); }
const STORY=[
 {r:"r1",t:"<b>1 → 2 · Squeeze.</b> The compressor squeezes the cold gas. Squeezing anything makes it hot (feel a bike pump). Now it is hotter than the outside air."},
 {r:"r2",t:"<b>2 → 3 · Dump the heat.</b> Because the gas is hotter than outside, heat flows out of it by itself. Losing heat turns the gas into liquid."},
 {r:"r3",t:"<b>3 → 4 · Release.</b> The valve lets the pressure drop. The liquid suddenly turns icy cold, colder than the servers' water."},
 {r:"r4",t:"<b>4 → 1 · Soak up heat.</b> Because it is so cold, heat flows into it from the servers' water. That boils it back into gas, and round it goes again."}];
function readouts(){
  const st=["gas","hot gas","liquid",`liquid + a little gas`], pr=["LOW","HIGH","HIGH","LOW"];
  [0,1,2,3].forEach(k=>{ const e=$("r"+(k+1)); e.style.display="block";
    e.innerHTML=`<span class="n">${k+1}</span><b style="color:${colr(C.T[k])}">${C.T[k]} °C</b><br>pressure <b>${pr[k]}</b> · ${C.P[k].toLocaleString()} kPa<br>${st[k]}`; }); }
function built(){
  $("s1").className="done"; $("s2").className="on"; running=true;
  for(let k=0;k<40;k++) dots.push(sv("circle",{r:5,"stroke-width":2},$("kdots")));
  readouts(); tick(); fitNow();
  say(`<b>It runs!</b> You built it in ${tries} ${tries===1?"try":"tries"}. Solid blobs are liquid, hollow ones are gas. Blue is cold, orange is hot.`,"good");
  const bs = gave?0:(tries<=4?3:(tries<=6?2:1));
  if(gave) pop(null,"Here is how it goes together","Squeezer on the side where the gas gets squeezed, heat dumper facing outside, pressure release opposite the squeezer, heat soaker facing the servers. Watch it run, then try level 2 yourself.",null,"Watch it run");
  else pop(bs, bs===3?"Perfect build!":"You built a chiller!", `You placed all four parts in ${tries} ${tries===1?"try":"tries"}. The squeezer faces the hot side, the heat soaker faces the servers, and now the refrigerant is going round.`,
      bs===3?null:"Each part sits where its job happens: heat leaves at the top, heat comes in at the bottom.", "Watch it run","ok");
  const b=$("btns"); b.innerHTML='<button class="big" id="nx">Follow the refrigerant →</button>';
  $("nx").onclick=()=>{ lit++; document.querySelectorAll(".read").forEach(e=>e.classList.remove("lit"));
    if(lit<4){ $(STORY[lit].r).classList.add("lit"); say(STORY[lit].t); $("nx").textContent = lit<3?"Next →":"What did I just learn?"; }
    else { lesson("lesson",["You put a squeezer, a heat dumper, a pressure release and a heat soaker in a loop.","The fluid got hot enough to push heat outside, then cold enough to pull heat from the servers.",
        "A chiller does not make cold. It <b>moves heat</b> from a cool place to a warm one, and that costs electricity."]);
      say("Heat only flows from hot to cold by itself. The trick of a chiller is to make the fluid hotter than outside in one place and colder than the servers in another.","good");
      b.innerHTML='<button class="big" id="go2">Level 2: keep the servers cool →</button>'; $("go2").onclick=level2; fitNow(); } };
}
function pop(stars,title,text,hint,ok,art){ const s = (art?`<div style="margin:-6px 0 -8px 0">${ARTS[art]}</div>`:"") + (stars===null ? "" : `<div class="st">${"★".repeat(stars)}<span style="color:#3A4350">${"★".repeat(3-stars)}</span></div>`);
  $("popb").innerHTML=s+`<h3>${title}</h3><p>${text}</p>`+(hint?`<div class="hint"><b>Hint:</b> ${hint}</div>`:"");
  $("popok").textContent=ok||"Continue"; $("pop").style.display="flex";
  if(art==="hot") fxk("fail","#E5574B",2,true); else if(art==="cost") fxk("meh","#D9A441"); else if(stars===3||stars===null) fxk("gold","#D9A441"); else fxk("win","#8FB39A"); $("kg").scrollIntoView({block:"start"}); try{ window.frameElement.scrollIntoView({block:"start",behavior:"smooth"}); }catch(e){} }
function unpop(){ $("pop").style.display="none"; }
$("popx").onclick=unpop; $("popok").onclick=unpop; $("pop").addEventListener("click",e=>{ if(e.target.id==="pop") unpop(); });
function lesson(id,t){ const e=$(id); e.style.display="grid"; e.innerHTML=["You did","The machine did","So we learn"].map((h,i)=>`<div><span>${h}</span>${t[i]}</div>`).join(""); }
// ---------------------------------------------------------------- level 2: how cold?
const bmin=Math.min(...TAB.map(r=>r.bill)), bmax=Math.max(...TAB.map(r=>r.bill));
const safe=TAB.filter(r=>r.peak<=LIM+0.05), best=safe.reduce((a,b)=>b.bill<a.bill?b:a, safe[0]);
function row(T){return TAB.find(r=>r.T===T)||TAB[0];}
function l2draw(){ const T=+$("tw").value, r=row(T); $("tv").textContent=T;
  const hot=r.peak>LIM+0.05; $("pk").textContent=r.peak.toFixed(1)+" °C"; $("pk").style.color=hot?"#E06A50":"#E6E8EB";
  const lo=10, hi=Math.max(LIM+6,...TAB.map(x=>x.peak)); $("pkbar").style.width=(100*(r.peak-lo)/(hi-lo))+"%"; $("pkbar").style.background=hot?"#E06A50":(r.peak>LIM-3?"#D9A441":"#6FA8DC");
  $("pklim").style.left=(100*(LIM-lo)/(hi-lo))+"%";
  $("bl").textContent="$"+Math.round(r.bill).toLocaleString(); $("blbar").style.width=(18+82*(r.bill-bmin)/Math.max(1,bmax-bmin))+"%"; $("blbar").style.background="#D9A441";
  $("ok").textContent=hot?"TOO HOT":"safe"; $("ok").style.color=hot?"#E06A50":"#8FB39A";
  const f=Math.max(0,Math.min(1,(r.peak-14)/(LIM-14))); const c=hot?"#E06A50":`rgb(${[111,168,220].map((v,i)=>Math.round(v+([217,164,65][i]-v)*f))})`;
  document.querySelectorAll("#racks i").forEach(e=>e.style.background=c); }
let fails=0;
function level2(){ $("give2").onclick=()=>{ $("tw").value=best.T; l2draw(); pop(null,"The best setting is "+best.T+" °C",`That is the warmest water that still keeps the servers at or under ${LIM} °C. Any colder and you pay for cooling you do not need. Any warmer and the servers overheat.`,null,"Got it"); };
 $("l1").style.display="none"; $("l2").style.display="block"; $("s2").className="done"; $("s3").className="on"; running=false;
  $("limtxt").textContent=LIM+" °C"; const R=$("racks"); R.innerHTML=""; for(let k=0;k<16;k++) R.appendChild(document.createElement("i"));
  $("tw").min=TAB[0].T; $("tw").max=TAB[TAB.length-1].T; $("tw").value=TAB[0].T; $("tw").oninput=l2draw; l2draw(); fitNow();
  $("lock").onclick=()=>{ const r=row(+$("tw").value), hot=r.peak>LIM+0.05, extra=r.bill-best.bill;
    const stars = hot?0:(extra<=0.03*best.bill?3:(extra<=0.15*best.bill?2:1));
    const cold=TAB[0];
    $("msg2").innerHTML=`<div id="stars">${"★".repeat(stars)}<span style="color:#3A4350">${"★".repeat(3-stars)}</span></div>`+
      (hot?`<b>Too warm.</b> The servers hit ${r.peak.toFixed(1)} °C, over the ${LIM} °C limit. Slide it colder and try again.`
       : stars===3?`<b>Perfect.</b> Servers safe at ${r.peak.toFixed(1)} °C and the lowest bill you can get: $${Math.round(r.bill).toLocaleString()}.`
       : `<b>Safe, but you paid $${Math.round(extra).toLocaleString()} more than you needed to.</b> The servers would still be fine with warmer water. Try again.`);
    if(!hot){ $("lesson2").style.display="grid"; lesson("lesson2",[`You set the water to ${r.T} °C.`,
        `The servers peaked at ${r.peak.toFixed(1)} °C and cooling cost $${Math.round(r.bill).toLocaleString()}. At ${cold.T} °C it costs $${Math.round(cold.bill).toLocaleString()}.`,
        "Colder is not safer, only more expensive. Engineers pick the <b>warmest</b> water the servers allow, because the chiller then has less of a hill to push heat up."]); }
    fails += stars<3 ? 1 : 0; if(fails>=2) $("give2").style.display="inline-block";
    if(hot) pop(0,"Too hot. Don't worry, try again!",`You set the water to ${r.T} °C, so the servers reached ${r.peak.toFixed(1)} °C. The limit is ${LIM} °C.`,"The servers get the water plus about 8 °C. Slide the water a little colder.","Try again","hot");
    else if(stars===3) pop(3,"Three stars!",`Water at ${r.T} °C kept the servers safe at ${r.peak.toFixed(1)} °C for only $${Math.round(r.bill).toLocaleString()}. Warmer water means the chiller pushes heat up a smaller hill, so it uses less electricity.`,null,"See what I learned","ok");
    else pop(stars,"Safe, but you overpaid.",`Water at ${r.T} °C kept the servers at ${r.peak.toFixed(1)} °C, far below the ${LIM} °C limit. You paid $${Math.round(extra).toLocaleString()} more than you needed to.`,"When the water is warmer, the bill goes down. How warm can you go before the servers hit the limit?","Try again","cost");
    $("btns2").innerHTML= stars===3 ? '<button class="big" id="again">Play again</button><span style="margin-left:14px;color:#B4BAC2;font-size:15px">Ready for the real thing? Open <b>Work orders</b> at the top and play First Shift.</span>' : '';
    const a=$("again"); if(a) a.onclick=()=>{ $("lesson2").style.display="none"; $("btns2").innerHTML=""; $("tw").value=TAB[0].T; l2draw(); $("msg2").innerHTML=`Goal: keep every server under <b>${LIM} °C</b> and spend as little as you can.`; }; fitNow(); }; }
function fitNow(){ try{ const fe=window.frameElement; if(!fe) return; const h=Math.ceil($("kg").getBoundingClientRect().height)+8;
  if(Math.abs(parseFloat(fe.style.height||0)-h)>3){ fe.style.height=h+"px"; fe.setAttribute("height",h); } }catch(e){} }
tray(); fitNow(); try{ new ResizeObserver(fitNow).observe($("kg")); }catch(e){}
</script>
"""
