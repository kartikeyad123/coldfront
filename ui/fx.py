"""Sound cues and screen flashes. Every sound is synthesised in the browser
(Web Audio), so there are no audio files and nothing to download."""
import json
import streamlit.components.v1 as components

SYNTH = r"""
function cfCue(W,name){ try{
  const AC=W.AudioContext||W.webkitAudioContext; if(!AC) return; const c=W.__cfAC||(W.__cfAC=new AC()); if(c.state==="suspended") c.resume();
  const t0=c.currentTime+0.03, out=c.createGain(); out.gain.value=0.16; out.connect(c.destination);
  const tone=(f,at,d,type,g,f2)=>{ const o=c.createOscillator(), a=c.createGain(); o.type=type||"triangle"; o.frequency.setValueAtTime(f,t0+at);
    if(f2) o.frequency.exponentialRampToValueAtTime(f2,t0+at+d); a.gain.setValueAtTime(0.0001,t0+at); a.gain.exponentialRampToValueAtTime(g||0.6,t0+at+0.015);
    a.gain.exponentialRampToValueAtTime(0.0001,t0+at+d); o.connect(a); a.connect(out); o.start(t0+at); o.stop(t0+at+d+0.05); };
  const C5=523.25,E5=659.25,G5=783.99,C6=1046.5,E6=1318.5,G4=392,E4=329.63;
  ({ gold:()=>{[C5,E5,G5,C6].forEach((f,i)=>tone(f,i*0.11,0.22)); [C5,E5,G5,C6].forEach(f=>tone(f,0.48,0.9,"sine",0.35)); },
     win:()=>{[E5,G5,C6].forEach((f,i)=>tone(f,i*0.12,0.3));},
     meh:()=>{tone(G4,0,0.22,"sine");tone(E4,0.2,0.4,"sine");},
     fail:()=>{tone(220,0,0.45,"sawtooth",0.35,110);tone(165,0.4,0.7,"sawtooth",0.35,82);},
     alarm:()=>{for(let i=0;i<3;i++){tone(880,i*0.36,0.16,"square",0.22);tone(660,i*0.36+0.18,0.16,"square",0.22);}},
     blip:()=>{tone(880,0,0.12,"square",0.2);tone(660,0.14,0.12,"square",0.2);},
     notice:()=>{tone(660,0,0.18,"sine");tone(880,0.16,0.35,"sine");},
     clear:()=>{tone(660,0,0.12,"sine",0.4);tone(990,0.1,0.25,"sine",0.4);},
     rank:()=>{[C5,E5,G5,C6,E6].forEach((f,i)=>tone(f,1.0+i*0.08,0.25));},
     tick:()=>{tone(880,0,0.09,"sine",0.4);tone(1320,0.07,0.14,"sine",0.4);},
     no:()=>{tone(180,0,0.2,"square",0.2,140);} }[name]||(()=>{}))();
}catch(e){} }
function cfFlash(D,color,times,shake){ try{
  const v=D.createElement("div"); v.style.cssText="position:fixed;inset:0;pointer-events:none;z-index:2147483000;opacity:0;box-shadow:inset 0 0 220px 40px "+color+";background:"+color+"14";
  D.body.appendChild(v); const k=[]; for(let i=0;i<times;i++){k.push({opacity:0},{opacity:1});} k.push({opacity:0});
  v.animate(k,{duration:480*times+260,easing:"ease-out"}).onfinish=()=>v.remove();
  if(shake && !D.defaultView.matchMedia("(prefers-reduced-motion: reduce)").matches){ const m=D.querySelector('[data-testid="stMainBlockContainer"]')||D.body.firstElementChild;
    if(m) m.animate([{transform:"translateX(0)"},{transform:"translateX(-9px)"},{transform:"translateX(8px)"},{transform:"translateX(-6px)"},{transform:"translateX(4px)"},{transform:"translateX(0)"}],{duration:420}); }
}catch(e){} }
"""

KINDS = {            # cue, flash colour, number of flashes, shake
    "gold":   ("gold",   "#D9A441", 1, False),
    "win":    ("win",    "#8FB39A", 1, False),
    "meh":    ("meh",    "#D9A441", 1, False),
    "fail":   ("fail",   "#E5574B", 2, True),
    "alarm":  ("alarm",  "#E5574B", 3, True),
    "notice": ("notice", "#D9A441", 1, False),
}


def fire(kind, nonce, sound=True, rank=False):
    """Play one cue and flash the page, once per nonce (a rerun does not repeat it)."""
    cue, color, times, shake = KINDS[kind]
    components.html(
        "<script>" + SYNTH + f"""
(function(){{ const P=window.parent; P.__cfFx=P.__cfFx||new Set(); const n={json.dumps(nonce)}; if(P.__cfFx.has(n)) return; P.__cfFx.add(n);
  if({json.dumps(bool(sound))}){{ cfCue(P,{json.dumps(cue)}); {'cfCue(P,"rank");' if rank else ''} }}
  cfFlash(P.document,{json.dumps(color)},{times},{json.dumps(shake)}); }})();
</script>""", height=0)
