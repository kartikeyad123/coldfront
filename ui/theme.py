"""theme.py - Visual identity: quiet graphite control room. Inter for the
interface, IBM Plex Mono for live numbers, a serif for headlines.
Colour carries meaning: steel blue = cold, ochre = warm, orange = hot;
red is used only for alarms."""

BG, PANEL, LINE, TEXT, MUTED = "#0E1116", "#151A21", "#2A313B", "#E6E8EB", "#8A929C"
COLD, WARM, HOT, ALARM, OK = "#6FA8DC", "#D9A441", "#D97B3F", "#E06A50", "#8FB39A"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&display=swap');
html, body, [class*="css"], .stMarkdown, p, label, li, td, th, input, textarea, select, button {
  font-family: 'Inter', sans-serif !important; }
h1, h2, h3 { font-family: 'Source Serif 4', Georgia, serif !important; font-weight: 600 !important; letter-spacing: -0.01em; }
.block-container { padding-top: 3.6rem; max-width: 1480px; padding-left: 2.2rem; padding-right: 2.2rem; }
header[data-testid="stHeader"] { background: transparent; }
.cf-bar { display:flex; align-items:baseline; gap:16px; border-bottom:1px solid #2A313B; padding-bottom:10px; margin-bottom:14px; }
.cf-brand { font-family:'Inter',sans-serif; font-size:20px; font-weight:600; color:#E6E8EB; letter-spacing:.32em; }
.cf-sub { color:#C3C9D1; font-size:16.5px; }
.cf-tag { margin-left:auto; color:#A3ABB5; font-size:13.5px; }
.cf-h { color:#A3ABB5; font-size:12.5px; text-transform:uppercase; letter-spacing:.14em; margin:18px 0 6px 0; }
.cf-hero { font-family:'Source Serif 4',Georgia,serif; font-size:46px; line-height:1.08; font-weight:600; color:#E6E8EB; margin:26px 0 10px 0; }
.cf-lede { color:#B4BAC2; font-size:17px; max-width:640px; line-height:1.5; }
div[data-testid="stMetric"] { background:#151A21; border:1px solid #2A313B; padding:12px 14px; border-radius:6px; }
div[data-testid="stMetricValue"] { font-family:'IBM Plex Mono',monospace !important; font-size:24px; color:#E6E8EB; }
div[data-testid="stMetricLabel"] p { color:#A3ABB5 !important; font-size:13px !important; }
.cf-card { background:#151A21; border:1px solid #2A313B; border-radius:6px; padding:16px 18px; margin-bottom:10px; line-height:1.5; }
.cf-card b { color:#E6E8EB; }
.cf-num { font-family:'IBM Plex Mono',monospace; }
.cf-guide { background:#151A21; border:1px solid #6FA8DC; border-radius:6px; padding:14px 18px; margin:6px 0 12px 0; }
.cf-guide .n { font-family:'IBM Plex Mono',monospace; color:#6FA8DC; font-size:12px; letter-spacing:.08em; }
.cf-alert { border-left:3px solid #E06A50; background:#151A21; padding:12px 16px; border-radius:0 6px 6px 0; margin:8px 0; }
.cf-note { border-left:3px solid #D9A441; background:#151A21; padding:12px 16px; border-radius:0 6px 6px 0; margin:8px 0; }
.cf-grade { font-family:'Source Serif 4',Georgia,serif; font-size:64px; font-weight:600; line-height:1; }
.cf-mono { color:#A3ABB5; font-size:13.5px; line-height:1.5; }
.cf-set { font-size:13.5px; margin:8px 0 0 0; }
div[data-testid="stButtonGroup"] { flex-wrap:wrap; }
.cf-badge { display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:11px; padding:1px 7px; border:1px solid #2A313B;
  border-radius:3px; color:#B4BAC2; margin-left:6px; }
table.cf-t { width:100%; border-collapse:collapse; font-size:14px; }
table.cf-t th { text-align:left; color:#8A929C; font-weight:500; font-size:12px; border-bottom:1px solid #2A313B; padding:6px 8px; }
table.cf-t td { border-bottom:1px solid #20262E; padding:7px 8px; }
table.cf-t td.n { font-family:'IBM Plex Mono',monospace; text-align:right; }
div[data-testid="stPopover"] button, .stButton button { border:1px solid #2A313B; border-radius:6px; }
.cf-fact { color:#C3C9D1; font-size:14.5px; margin-top:5px; line-height:1.4; }
.cf-flow { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:6px 0 4px 0; }
.cf-flow > div { background:#151A21; border:1px solid #2A313B; border-radius:8px; padding:12px 14px; position:relative; }
.cf-flow > div:not(:last-child):after { content:"→"; position:absolute; right:-10px; top:50%; transform:translate(50%,-50%); color:#6FA8DC; font-size:16px; z-index:2; }
.cf-flow svg { width:26px; height:26px; display:block; margin-bottom:6px; }
.cf-flow b { display:block; font-size:15px; color:#E6E8EB; }
.cf-flow span { color:#B4BAC2; font-size:13.5px; line-height:1.4; display:block; margin-top:2px; }
.cf-flow i { font-style:normal; font-family:'IBM Plex Mono',monospace; color:#6FA8DC; font-size:12px; letter-spacing:.08em; }
@media (max-width: 900px) { .cf-flow { grid-template-columns:repeat(2,1fr); } .cf-flow > div:after { display:none; } }
.cf-step { display:flex; gap:10px; align-items:center; margin:16px 0 8px 0; }
.cf-step .n { width:26px; height:26px; border-radius:50%; background:#6FA8DC; color:#0E1116; font-weight:700; font-size:14px;
  display:flex; align-items:center; justify-content:center; flex:none; }
.cf-step b { font-size:16.5px; color:#E6E8EB; } .cf-step span { color:#A3ABB5; font-size:13.5px; display:block; }
.cf-learn { border:1px solid #2A313B; border-left:3px solid #6FA8DC; background:#151A21; border-radius:0 8px 8px 0; padding:12px 16px; margin:10px 0; font-size:15px; line-height:1.5; color:#C3C9D1; }
.cf-learn b { color:#E6E8EB; }
.cf-fx { border:1px solid #D9A441; background:#151A21; border-radius:8px; padding:12px 16px; margin:8px 0; }
.cf-fx .h { color:#D9A441; font-weight:600; margin-bottom:8px; font-size:14.5px; }
.cf-fx .chain { display:flex; flex-wrap:wrap; gap:8px; align-items:stretch; }
.cf-fx .chip { border:1px solid #2A313B; border-radius:6px; padding:8px 12px; max-width:330px; background:#0E1116; font-size:13.5px; line-height:1.45; color:#C3C9D1; }
.cf-fx .chip b { display:block; font-size:11.5px; letter-spacing:.1em; text-transform:uppercase; color:#6FA8DC; font-weight:600; }
.cf-fx .arrow { align-self:center; color:#8A929C; }
.cf-ask { border:1px solid #2A313B; background:#151A21; border-radius:8px; padding:14px 16px; margin:8px 0; line-height:1.55; font-size:15px; }
.cf-ask b { color:#E6E8EB; }
.cf-rank { display:flex; align-items:center; gap:22px; border:1px solid #2A313B; border-radius:8px; padding:16px 20px; margin:6px 0 18px 0;
  background:linear-gradient(90deg,#151A21 0%,#10141A 100%); }
.cf-rank .r { font-family:'Source Serif 4',Georgia,serif; font-size:26px; font-weight:600; color:#E6E8EB; line-height:1.1; }
.cf-rank .bar { flex:1; height:8px; border-radius:4px; background:#1B2129; overflow:hidden; } .cf-rank .bar i { display:block; height:100%; background:#D9A441; border-radius:4px; }
.cf-rank .slots { display:flex; gap:8px; }
.cf-mis { position:relative; min-height:212px; }
.cf-mis .no { font-family:'IBM Plex Mono',monospace; font-size:12.5px; letter-spacing:2.5px; color:#8A929C; }
.cf-mis .ti { font-family:'Source Serif 4',Georgia,serif; font-size:23px; font-weight:600; color:#E6E8EB; line-height:1.2; margin:4px 0 6px 0; }
.cf-mis .tag { display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:11.5px; letter-spacing:1.5px; padding:2px 8px; border:1px solid #3A4350; border-radius:3px; color:#B4BAC2; margin-right:6px; }
.cf-mis .tag.new { border-color:#6FA8DC; color:#6FA8DC; } .cf-mis .pip { letter-spacing:3px; color:#D97B3F; }
.cf-mis .med { position:absolute; right:0; bottom:0; }
.cf-objs { display:flex; gap:12px; flex-wrap:wrap; }
.cf-obj { flex:1 1 180px; border:1px solid #2A313B; border-left:3px solid #6FA8DC; border-radius:6px; padding:12px 14px; background:#10141A; }
.cf-obj .k { font-family:'IBM Plex Mono',monospace; font-size:11.5px; letter-spacing:2px; color:#8A929C; }
.cf-obj .t { font-size:15px; color:#B4BAC2; margin-top:2px; } .cf-obj .v { font-family:'IBM Plex Mono',monospace; font-size:24px; color:#E6E8EB; margin:2px 0; }
.cf-obj .s { font-size:13px; color:#8A929C; } .cf-obj.ok { border-left-color:#8FB39A; } .cf-obj.bad { border-left-color:#E06A50; }
.cf-obj.ok .v { color:#8FB39A; } .cf-obj.bad .v { color:#E06A50; }
.cf-brief { font-size:18.5px; line-height:1.5; color:#E6E8EB; }
.cf-medals { display:flex; gap:18px; flex-wrap:wrap; align-items:center; color:#B4BAC2; font-size:14px; margin-top:14px; }
.cf-medals span { display:inline-flex; align-items:center; gap:7px; }
@keyframes cfpop { 0%{transform:scale(.2) rotate(-25deg);opacity:0} 60%{transform:scale(1.18) rotate(4deg);opacity:1} 100%{transform:scale(1) rotate(0)} }
@keyframes cfin { 0%{transform:translateY(10px);opacity:0} 100%{transform:none;opacity:1} }
@keyframes cfsweep { 0%{background-position:-400px 0} 100%{background-position:1600px 0} }
@keyframes cfblink { 0%,100%{opacity:1} 50%{opacity:.35} }
.cf-hero { display:flex; align-items:center; gap:20px; border:1px solid #2A313B; border-radius:8px; padding:14px 20px; margin:2px 0 14px 0;
  background:linear-gradient(100deg,#171D26 0%,#10141A 55%,#0E1116 100%); position:relative; overflow:hidden; animation:cfin .35s ease-out; }
.cf-hero::after { content:""; position:absolute; left:0; right:0; bottom:0; height:2px; background:linear-gradient(90deg,transparent,#6FA8DC,transparent);
  background-size:400px 2px; background-repeat:no-repeat; animation:cfsweep 3.2s linear infinite; }
.cf-hero .no { font-family:'IBM Plex Mono',monospace; font-size:12.5px; letter-spacing:3px; color:#6FA8DC; }
.cf-hero .ti { font-family:'Source Serif 4',Georgia,serif; font-size:30px; font-weight:600; color:#E6E8EB; line-height:1.15; }
.cf-chip { display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:11.5px; letter-spacing:1px; padding:2px 8px; border:1px solid #2F3742; border-radius:3px; color:#A3ABB5; margin:6px 6px 0 0; }
.cf-stages { display:flex; align-items:center; gap:0; margin-left:auto; font-family:'IBM Plex Mono',monospace; font-size:11.5px; letter-spacing:1.5px; color:#5A626E; white-space:nowrap; }
.cf-stages span { padding:5px 10px; border:1px solid #2A313B; margin-left:-1px; } .cf-stages span:first-child { border-radius:4px 0 0 4px; } .cf-stages span:last-child { border-radius:0 4px 4px 0; }
.cf-stages .done { color:#8FB39A; } .cf-stages .now { color:#0E1116; background:#6FA8DC; border-color:#6FA8DC; font-weight:600; }
.cf-tx { border-left:3px solid #6FA8DC; }
.cf-tx .from { font-family:'IBM Plex Mono',monospace; font-size:12px; letter-spacing:2px; color:#6FA8DC; } .cf-tx .from i { display:inline-block; width:7px; height:7px; border-radius:50%; background:#6FA8DC; margin-right:8px; animation:cfblink 1.4s infinite; }
.cf-outcome { display:flex; align-items:center; gap:18px; animation:cfin .4s ease-out; }
.cf-outcome .m { animation:cfpop .7s cubic-bezier(.2,.9,.3,1.2) both; } .cf-outcome .w { font-family:'IBM Plex Mono',monospace; font-size:13px; letter-spacing:4px; }
.cf-outcome .big { font-family:'Source Serif 4',Georgia,serif; font-size:30px; font-weight:600; line-height:1.15; color:#E6E8EB; }
.cf-rankup { display:inline-block; margin-top:8px; font-family:'IBM Plex Mono',monospace; font-size:12.5px; letter-spacing:2px; color:#0E1116; background:#D9A441; padding:3px 10px; border-radius:3px; animation:cfpop .8s .3s both; }
.cf-event svg .p, .cf-event { animation:none; } .cf-event .eyebrow { animation:cfblink 1.2s infinite; }
/* drawings size themselves; the Streamlit wrappers follow them (never set heights on wrappers from script: React reuses those nodes) */
div[data-testid="stElementContainer"]:not([height="0px"]):has(> iframe) { height:auto !important; flex:0 0 auto !important; }
</style>
"""


def header(subtitle=""):
    return f"""<div class="cf-bar"><div class="cf-brand">COLDFRONT</div>
    <div class="cf-sub">{subtitle}</div><div class="cf-tag">Kartikeya Daiya</div></div>"""


_S = 'fill="none" stroke="#6FA8DC" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"'
ICONS = dict(
    scenario=f'<svg viewBox="0 0 26 26"><circle cx="13" cy="11" r="4.5" {_S}/><path {_S} d="M13 2 v2.5 M13 17.5 V20 M4 11 h2.5 M19.5 11 H22 M6.6 4.6 l1.8 1.8 M17.6 15.6 l1.8 1.8 M19.4 4.6 l-1.8 1.8 M8.4 15.6 l-1.8 1.8 M5 24 h16"/></svg>',
    plant=f'<svg viewBox="0 0 26 26"><path {_S} d="M4 7 h18 M4 13 h18 M4 19 h18"/><circle cx="9" cy="7" r="2.4" fill="#151A21" {_S}/><circle cx="17" cy="13" r="2.4" fill="#151A21" {_S}/><circle cx="11" cy="19" r="2.4" fill="#151A21" {_S}/></svg>',
    run=f'<svg viewBox="0 0 26 26"><circle cx="13" cy="13" r="10" {_S}/><path {_S} d="M10.5 8.5 L18 13 L10.5 17.5 Z"/></svg>',
    explore=f'<svg viewBox="0 0 26 26"><circle cx="11" cy="11" r="7" {_S}/><path {_S} d="M16.2 16.2 L23 23 M8 13 l2.5 -3 l2 2 l2 -3.5"/></svg>')


def flow(active=None):
    """The four-step sequence every page follows."""
    steps = [("scenario", "Choose a scenario", "A city, a workload, a day."), ("plant", "Set the plant", "Water, chillers, tower, tank."),
             ("run", "Run the day", "24 hours in a second."), ("explore", "Explore the results", "What happened, and why.")]
    return '<div class="cf-flow">' + "".join(
        f'<div>{ICONS[k]}<i>STEP {i + 1}</i><b>{t}</b><span>{d}</span></div>' for i, (k, t, d) in enumerate(steps)) + '</div>'


def step(n, title, sub="", cls=""):
    return f'<div class="cf-step {cls}"><div class="n">{n}</div><div><b>{title}</b><span>{sub}</span></div></div>'
