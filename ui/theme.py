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
.block-container { padding-top: 3.6rem; max-width: 1320px; }
header[data-testid="stHeader"] { background: transparent; }
.cf-bar { display:flex; align-items:baseline; gap:16px; border-bottom:1px solid #2A313B; padding-bottom:10px; margin-bottom:14px; }
.cf-brand { font-family:'Inter',sans-serif; font-size:15px; font-weight:600; color:#E6E8EB; letter-spacing:.32em; }
.cf-sub { color:#8A929C; font-size:13px; }
.cf-tag { margin-left:auto; color:#8A929C; font-size:12px; }
.cf-h { color:#8A929C; font-size:11px; text-transform:uppercase; letter-spacing:.14em; margin:18px 0 6px 0; }
.cf-hero { font-family:'Source Serif 4',Georgia,serif; font-size:46px; line-height:1.08; font-weight:600; color:#E6E8EB; margin:26px 0 10px 0; }
.cf-lede { color:#B4BAC2; font-size:17px; max-width:640px; line-height:1.5; }
div[data-testid="stMetric"] { background:#151A21; border:1px solid #2A313B; padding:12px 14px; border-radius:6px; }
div[data-testid="stMetricValue"] { font-family:'IBM Plex Mono',monospace !important; font-size:24px; color:#E6E8EB; }
div[data-testid="stMetricLabel"] p { color:#8A929C !important; font-size:12px !important; }
.cf-card { background:#151A21; border:1px solid #2A313B; border-radius:6px; padding:16px 18px; margin-bottom:10px; line-height:1.5; }
.cf-card b { color:#E6E8EB; }
.cf-num { font-family:'IBM Plex Mono',monospace; }
.cf-guide { background:#151A21; border:1px solid #6FA8DC; border-radius:6px; padding:14px 18px; margin:6px 0 12px 0; }
.cf-guide .n { font-family:'IBM Plex Mono',monospace; color:#6FA8DC; font-size:12px; letter-spacing:.08em; }
.cf-alert { border-left:3px solid #E06A50; background:#151A21; padding:12px 16px; border-radius:0 6px 6px 0; margin:8px 0; }
.cf-note { border-left:3px solid #D9A441; background:#151A21; padding:12px 16px; border-radius:0 6px 6px 0; margin:8px 0; }
.cf-grade { font-family:'Source Serif 4',Georgia,serif; font-size:64px; font-weight:600; line-height:1; }
.cf-mono { color:#8A929C; font-size:12.5px; line-height:1.5; }
.cf-set { font-size:13.5px; margin:8px 0 0 0; }
div[data-testid="stButtonGroup"] { flex-wrap:wrap; }
.cf-badge { display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:11px; padding:1px 7px; border:1px solid #2A313B;
  border-radius:3px; color:#B4BAC2; margin-left:6px; }
table.cf-t { width:100%; border-collapse:collapse; font-size:14px; }
table.cf-t th { text-align:left; color:#8A929C; font-weight:500; font-size:12px; border-bottom:1px solid #2A313B; padding:6px 8px; }
table.cf-t td { border-bottom:1px solid #20262E; padding:7px 8px; }
table.cf-t td.n { font-family:'IBM Plex Mono',monospace; text-align:right; }
div[data-testid="stPopover"] button, .stButton button { border:1px solid #2A313B; border-radius:6px; }
</style>
"""


def header(subtitle=""):
    return f"""<div class="cf-bar"><div class="cf-brand">COLDFRONT</div>
    <div class="cf-sub">{subtitle}</div><div class="cf-tag">Kartikeya Daiya</div></div>"""
