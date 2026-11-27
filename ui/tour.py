"""
tour.py - First-visit spotlight tour. The page dims, one element is lit, a
card explains it, and the visitor presses Next. Interface only, no physics.

How it works: a tiny hidden component injects a script that draws the dim
layer and the card in the page itself. Each step names its target either by a
CSS selector ("css") or by the visible text of a button ("button"); "closest"
widens the highlight to an enclosing block. A step whose target is missing is
skipped. Progress is kept for the browser session, and a finished or skipped
tour is remembered so it only shows itself once (it can be replayed).
"""

import json
import streamlit.components.v1 as components

ROW = '[data-testid="stHorizontalBlock"]'

HOME = [
    dict(css=".cf-hero", title="Welcome to COLDFRONT",
         text="You run the cooling plant of an AI data center for one day. This 30-second tour shows you where everything is."),
    dict(css=".cf-flow", title="Four steps, always the same",
         text="Choose a scenario, set the plant, run the day, explore what happened. Every page follows this order."),
    dict(css="iframe", title="This is the plant",
         text="Chillers in the middle, the cooling tower on the left, the servers on the right. It is playing a real simulated day. Blue means cold, yellow means warm."),
    dict(button="Start first shift", title="Start here",
         text="Your first mission is guided. It takes two minutes and teaches the one idea behind everything else."),
    dict(button="Open the console", title="Or just explore",
         text="The console is free play. Pick any city and any plant and just experiment. There are no targets to hit."),
    dict(css='[data-testid="stButtonGroup"], [role="radiogroup"]', title="Seven views",
         text="Work orders are the missions. Console is free play. Chiller lab is one refrigeration cycle. Compare runs two plans side by side. Proof shows how the model was checked. Build a chiller is a three-minute game for beginners. Every page has its own tour: press Take the tour.", last="Got it"),
]

BRIEF = [
    dict(css=".cf-job", title="Your job for this shift",
         text="Every work order is one day at a client's site. This card says what you must achieve."),
    dict(css=".cf-targets", title="What earns a good grade",
         text="Each target has a limit. Stay inside every limit to pass. PUE is total power divided by computer power, so lower is better."),
    dict(css=".cf-guide", title="Follow the blue card",
         text="On this first mission a blue guide card always tells you the next step."),
    dict(css=".st-key-cf_ctl", title="These four buttons are your controls",
         text="Each one opens a panel for part of the plant: water temperature, chillers, tower or dry cooler, storage tank. For now, leave them as they are."),
    dict(button="Start mission", title="Run the day",
         text="Press Start mission. The model simulates 24 hours in a second and shows you what happened.", last="Got it"),
]

RESULT = [
    dict(css=".cf-gradecard", title="The grade for this attempt",
         text="A means every target met with room to spare. B is a pass. C means the servers were safe but the plant wasted energy. D means a safety limit was crossed. It is only this attempt: retry any time."),
    dict(css=".cf-targets", title="Why you got it",
         text="Each row shows the limit, what you achieved and the margin between them. Green is inside the limit, red is outside."),
    dict(css=".cf-what", title="What happened, in plain words",
         text="This paragraph is written from your run's own numbers. Read it first when a result surprises you."),
    dict(css="iframe", title="Replay the day",
         text="Press Play day or drag the slider. Click any equipment (a chiller, the tower, the data hall) to see its live numbers and equations."),
    dict(button="Try again", title="Change one thing and run again",
         text="Try again takes you back to the controls. Follow the blue guide card: it tells you exactly what to change.", last="Got it"),
]

PAUSE = [
    dict(css=".cf-event", title="The shift has paused",
         text="Something just happened. This card says what, and what it means for the plant."),
    dict(css=".st-key-cf_ctl", title="React",
         text="Change the plant with the same four controls. Whatever you set now applies from this minute onward."),
    dict(button="Resume mission", title="Then resume",
         text="Resume runs the rest of the day with your new settings. Or resume without changes to see what happens. Restart takes you back to the briefing.", last="Got it"),
]

LIST = [
    dict(css=".cf-wocard", title="Six missions",
         text="Each card is one shift at a client's site, with its own problem to solve. They are in the recommended order, but all are open."),
    dict(css=".cf-rank", title="Your rank",
         text="Clear shifts to fill the bar and collect medals. Six golds makes you Chief engineer."),
    dict(button="Play", title="Play one",
         text="Press Play to read the briefing and its objectives. Each mission has three sets of numbers.", last="Got it"),
]

CONSOLE = [
    dict(css=".st-key-cf_step1", title="1 · Choose the scenario",
         text="Pick the city and its weather, what the servers are doing, and how electricity is priced. This is the situation the plant has to cope with."),
    dict(css=".st-key-cf_step2", title="2 · Set the plant",
         text="Four controls, one per part of the plant. Open one, change a setting, click outside to close it. The day reruns at once."),
    dict(css="iframe", title="3 · Watch the day run",
         text="Press Play day. Colours show each machine's state: blue normal, purple high demand, orange inefficient, red critical, grey offline. Click any machine or pipe for its numbers."),
    dict(css=".cf-fxnote", title="What your change did",
         text="After every change, a strip above the drawing names what you changed and which equipment felt it, with the numbers. Those machines glow for a few seconds."),
    dict(css=".cf-what", title="4 · Explore the results",
         text="This paragraph explains the day in plain words. Below it are the day's numbers and charts."),
    dict(css=".st-key-cf_ask", title="Ask the plant",
         text="Type a question in your own words, such as 'why is the PUE high' or 'what does the tower do'. It answers from this run's numbers.", last="Got it"),
]

LAB = [
    dict(css=".st-key-cf_labctl", title="One refrigeration cycle",
         text="This page is the chiller on its own. Set the two temperatures, the refrigerant and the compressor efficiency here."),
    dict(css="iframe", title="Watch the refrigerant",
         text="Solid blobs are liquid, hollow ones are vapor. Blue is cold, yellow is hot. Each corner shows temperature, pressure and phase. Click a component for its numbers."),
    dict(css=".js-plotly-plot", title="The same cycle on property diagrams",
         text="Pressure against enthalpy and temperature against entropy, drawn on the refrigerant's saturation dome."),
    dict(css=".cf-chal", title="Three small challenges",
         text="Each one can be met by moving the sliders above. They turn green when met.", last="Got it"),
]

COMPARE = [
    dict(css=".st-key-cf_step1", title="Same day for both",
         text="Choose one site, workload and price. Both plans face exactly the same day."),
    dict(css=".st-key-cf_planA", title="Plan A and Plan B",
         text="Set each plant with the same four controls. Change one thing in Plan B to see what that one thing does."),
    dict(css=".cf-fxcard", title="What the difference did",
         text="This chain reads from cause to effect: what differs between the plans, which equipment it touched, and the result."),
    dict(css=".cf-cmp", title="Every number side by side",
         text="The last column is B minus A.", last="Got it"),
]

PROOF = [
    dict(css=".cf-proofintro", title="Why trust the numbers",
         text="Every check on this page is recomputed live by the model. Nothing here is typed in by hand."),
    dict(css=".cf-p1", title="Against a textbook",
         text="The cycle is compared with a worked example from Çengel and Boles."),
    dict(css=".cf-note", title="One check fails, on purpose visible",
         text="The model overstates the saving from warmer water compared with a rule of thumb. It is shown, with what it means.", last="Got it"),
]

KIDS = [
    dict(css="iframe", title="Build a chiller",
         text="Drag each part to where it belongs in the loop. If one is wrong it bounces back with a clue. No reading needed.", last="Got it"),
]

_JS = r"""
<script>
(function(){
  let P; try { P = window.parent; P.document.body; } catch(e) { return; }
  const D = P.document, KEY = __KEY__, STEPS = __STEPS__, FORCE = __FORCE__;
  const mem = P.__cfTour = P.__cfTour || {};
  const get = (s,k)=>{ try { return P[s].getItem(k); } catch(e) { return mem[k]; } };
  const set = (s,k,v)=>{ mem[k]=v; try { P[s].setItem(k,v); } catch(e) {} };
  const old = D.getElementById("cf-tour"); if (old) { if (old.__stop) old.__stop(); old.remove(); }
  if (FORCE && get("sessionStorage","cfForce:"+KEY) !== FORCE) {
    set("sessionStorage","cfForce:"+KEY, FORCE); set("localStorage","cfSeen:"+KEY, ""); set("sessionStorage","cfStep:"+KEY, "0");
  }
  if (get("localStorage","cfSeen:"+KEY) === "1") return;

  function target(st){
    let el = null;
    if (st.button) { el = Array.from(D.querySelectorAll("button")).find(b => { const t = b.innerText.trim(); return (t === st.button || t.startsWith(st.button) || t.split("\n").some(l => l.trim() === st.button)) && b.offsetParent !== null; }); }
    else if (st.css) { el = Array.from(D.querySelectorAll(st.css)).find(e => e.offsetParent !== null && e.getBoundingClientRect().height > 8); }
    if (el && st.closest) el = el.closest(st.closest) || el;
    return el;
  }
  const root = D.createElement("div"); root.id = "cf-tour";
  root.innerHTML = `<style>
    #cf-tour{position:fixed;inset:0;z-index:999990;font-family:Inter,system-ui,sans-serif}
    #cf-tour .hole{position:fixed;border-radius:8px;box-shadow:0 0 0 9999px rgba(6,8,11,.74);outline:2px solid #6FA8DC;outline-offset:2px;transition:all .25s ease;pointer-events:none}
    #cf-tour .card{position:fixed;width:340px;max-width:calc(100vw - 24px);background:#151A21;border:1px solid #3A4350;border-radius:10px;padding:16px 18px 14px;color:#E6E8EB;box-shadow:0 12px 40px rgba(0,0,0,.5);transition:top .25s ease,left .25s ease}
    #cf-tour .n{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;color:#6FA8DC;margin-bottom:6px}
    #cf-tour h4{margin:0 0 6px 0;font-size:16px;font-weight:600;color:#E6E8EB;font-family:Inter,system-ui,sans-serif}
    #cf-tour p{margin:0 0 14px 0;font-size:14px;line-height:1.5;color:#B4BAC2}
    #cf-tour .row{display:flex;gap:8px;align-items:center}
    #cf-tour button{font:inherit;font-size:13px;border-radius:6px;padding:6px 14px;cursor:pointer;border:1px solid #3A4350;background:transparent;color:#E6E8EB}
    #cf-tour button.next{background:#6FA8DC;border-color:#6FA8DC;color:#0E1116;font-weight:600;margin-left:auto}
    #cf-tour button.skip{border-color:transparent;color:#8A929C;padding-left:0}
    #cf-tour button:hover{border-color:#E6E8EB}
  </style><div class="hole"></div><div class="card" role="dialog" aria-live="polite"></div>`;
  root.style.display = "none";            // nothing is covered until the first step is ready
  D.body.appendChild(root);
  const hole = root.querySelector(".hole"), card = root.querySelector(".card");
  let i = parseInt(get("sessionStorage","cfStep:"+KEY) || "0", 10) || 0, timer = null, cur = null;

  function finish(){ set("localStorage","cfSeen:"+KEY,"1"); stop(); root.remove(); }
  function stop(){ if (timer) P.clearInterval(timer); }
  root.__stop = stop;
  function place(){
    if (!cur || !D.body.contains(cur)) { cur = target(STEPS[i]); if (!cur) return; }
    const r = cur.getBoundingClientRect(), W = P.innerWidth, H = P.innerHeight, pad = 6;
    hole.style.left = (r.left - pad) + "px"; hole.style.top = (r.top - pad) + "px";
    hole.style.width = (r.width + 2*pad) + "px"; hole.style.height = (r.height + 2*pad) + "px";
    const cw = card.offsetWidth, ch = card.offsetHeight;
    let top = r.bottom + 16, left = Math.min(Math.max(12, r.left), W - cw - 12);
    if (top + ch > H - 12) top = r.top - ch - 16;                 // above
    if (top < 12) { top = Math.min(Math.max(12, r.top), H - ch - 12); left = r.right + 16;   // beside
      if (left + cw > W - 12) left = Math.max(12, r.left - cw - 16);
      if (left < 12 || (left < r.right && left + cw > r.left)) { left = W - cw - 16; top = H - ch - 16; } }
    card.style.top = top + "px"; card.style.left = left + "px";
  }
  function show(dir){
    let guard = 0;
    while (i >= 0 && i < STEPS.length && !target(STEPS[i]) && guard++ < 20) i += dir;
    if (i < 0) i = 0;
    if (i >= STEPS.length || !target(STEPS[i])) { if (dir < 0) return; root.style.display = "none"; return; }
    root.style.display = "";
    set("sessionStorage","cfStep:"+KEY, String(i));
    const st = STEPS[i]; cur = target(st);
    const isLast = !STEPS.slice(i + 1).some(x => target(x));
    const live = STEPS.map((x, k) => target(x) ? k : -1).filter(k => k >= 0);
    card.innerHTML = `<div class="n">${live.indexOf(i)+1} OF ${live.length}</div><h4>${st.title}</h4><p>${st.text}</p>
      <div class="row"><button class="skip">Skip tour</button>${i>0?'<button class="back">Back</button>':''}
      <button class="next">${isLast ? (st.last || "Done") : "Next"}</button></div>`;
    card.querySelector(".skip").onclick = finish;
    const b = card.querySelector(".back"); if (b) b.onclick = ()=>{ i--; show(-1); };
    card.querySelector(".next").onclick = ()=>{ if (isLast) finish(); else { i++; show(1); } };
    try { cur.scrollIntoView({block:"center", behavior:"smooth"}); } catch(e) {}
    place();
  }
  D.addEventListener("keydown", function esc(e){ if (!D.body.contains(root)) { D.removeEventListener("keydown", esc); return; }
    if (e.key === "Escape") finish(); if (e.key === "ArrowRight" || e.key === "Enter") { const n = card.querySelector(".next"); if (n) n.click(); } });
  // the page may still be rendering: wait for the first target, then keep the highlight glued to it
  let tries = 0;
  const wait = P.setInterval(()=>{ if (target(STEPS[Math.min(i, STEPS.length-1)]) || ++tries > 240) { P.clearInterval(wait); show(1); timer = P.setInterval(place, 200); } }, 150);
})();
</script>
"""


def tour(key, steps, force=None):
    """Show the tour `key` once per browser. `force` (any changing value)
    replays it even if it was seen before."""
    html = (_JS.replace("__KEY__", json.dumps(key)).replace("__STEPS__", json.dumps(steps))
            .replace("__FORCE__", json.dumps(str(force) if force else "")))
    components.html(html, height=0)
