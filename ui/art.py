"""
art.py - Small line illustrations for alerts and results. Original drawings in
one style: white outline, one accent colour that carries the meaning
(red = alarm, ochre = caution, blue or green = fine).
"""
W, RED, OCH, BLUE, GRN = "#E6E8EB", "#E5574B", "#D9A441", "#6FA8DC", "#8FB39A"
_L = f'fill="none" stroke="{W}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"'


def _servers(dx=0):
    out = ""
    for k, y in enumerate((62, 104, 146)):
        out += (f'<rect x="{20 + dx}" y="{y}" width="112" height="34" rx="9" {_L}/>'
                f'<path d="M{38 + dx} {y + 17} h26" {_L}/>'
                + "".join(f'<circle cx="{98 + dx + 13 * j}" cy="{y + 17}" r="3.2" fill="{W}"/>' for j in range(2 - (k == 2))))
    return out


def _waves(x, color, y=44):
    return "".join(f'<path d="M{x + 24 * k} {y} q9 -9 0 -18 q-9 -9 0 -18" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round"/>'
                   for k in range(3))


def _wrap(body, pulse=None):
    anim = (f'<style>.p{{animation:cfp 1.1s ease-in-out infinite alternate}}@keyframes cfp{{from{{opacity:1}}to{{opacity:.35}}}}'
            f'@media (prefers-reduced-motion: reduce){{.p{{animation:none}}}}</style>') if pulse else ""
    return f'<svg viewBox="0 0 200 200" width="150" height="150" xmlns="http://www.w3.org/2000/svg">{anim}{body}</svg>'


ART = dict(
    hot=_wrap(f'<g class="p">{_waves(46, RED)}</g>' + _servers()
              + f'<rect x="126" y="96" width="34" height="74" rx="17" fill="#0E1116" {_L[11:]}/>'
                f'<circle cx="143" cy="162" r="24" fill="#0E1116" stroke="{W}" stroke-width="5"/>'
                f'<circle cx="143" cy="162" r="13" fill="{RED}"/><rect x="138" y="112" width="10" height="46" rx="5" fill="{RED}"/>', True),
    ok=_wrap(_servers()
             + f'<circle cx="146" cy="150" r="34" fill="#0E1116" stroke="{GRN}" stroke-width="5"/>'
               f'<path d="M130 151 l11 12 l22 -25" fill="none" stroke="{GRN}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
               f'<g stroke="{BLUE}" stroke-width="4.5" stroke-linecap="round"><path d="M76 14 v36 M60 23 l32 18 M92 23 l-32 18"/></g>'),
    cost=_wrap(_servers()
               + f'<circle cx="146" cy="150" r="34" fill="#0E1116" stroke="{OCH}" stroke-width="5"/>'
                 f'<path d="M156 138 q-10 -8 -20 0 q-6 8 10 12 q16 4 10 13 q-10 8 -21 0 M146 126 v48" fill="none" stroke="{OCH}" stroke-width="5" stroke-linecap="round"/>'
                 f'<path d="M52 44 l22 -24 l14 12 l26 -22 M114 10 h-14 M114 10 v14" fill="none" stroke="{OCH}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'),
    water=_wrap(_servers()
                + f'<circle cx="146" cy="150" r="36" fill="#0E1116" stroke="{RED}" stroke-width="5"/>'
                  f'<path d="M146 126 q-18 24 -18 33 a18 18 0 0 0 36 0 q0 -9 -18 -33 Z" fill="none" stroke="{BLUE}" stroke-width="5" stroke-linejoin="round"/>'
                  f'<path d="M122 126 l48 48" stroke="{RED}" stroke-width="6" stroke-linecap="round"/>'),
    trip=_wrap(f'<rect x="34" y="40" width="100" height="130" rx="10" {_L}/><circle cx="84" cy="88" r="30" {_L}/>'
               f'<path d="M84 88 l22 -10 M84 88 l-20 14 M84 88 l-2 -26" {_L}/><path d="M54 140 h60" {_L}/>'
               f'<g class="p"><path d="M150 20 l-22 44 h20 l-10 38 l34 -52 h-22 l12 -30 Z" fill="{RED}"/></g>'
               f'<path d="M20 30 l150 150" stroke="{RED}" stroke-width="6" stroke-linecap="round" opacity=".0"/>', True),
    heat=_wrap(f'<circle cx="80" cy="84" r="34" fill="none" stroke="{OCH}" stroke-width="5"/>'
               f'<g stroke="{OCH}" stroke-width="5" stroke-linecap="round" class="p"><path d="M80 22 v16 M80 130 v16 M18 84 h16 M36 40 l12 12 M124 40 l-12 12 M36 128 l12 -12"/></g>'
               f'<rect x="126" y="60" width="34" height="100" rx="17" fill="#0E1116" stroke="{W}" stroke-width="5"/>'
               f'<circle cx="143" cy="156" r="24" fill="#0E1116" stroke="{W}" stroke-width="5"/>'
               f'<circle cx="143" cy="156" r="13" fill="{RED}"/><rect x="138" y="80" width="10" height="72" rx="5" fill="{RED}"/>', True),
    price=_wrap(f'<path d="M28 172 h150" {_L}/><rect x="40" y="124" width="26" height="48" rx="4" {_L}/><rect x="82" y="96" width="26" height="76" rx="4" {_L}/>'
                f'<g class="p"><rect x="124" y="46" width="26" height="126" rx="4" fill="{OCH}" stroke="{OCH}" stroke-width="5"/></g>'
                f'<path d="M38 92 l40 -34 l22 14 l44 -44 M144 28 h-18 M144 28 v18" fill="none" stroke="{OCH}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>', True),
    load=_wrap(f'<rect x="52" y="62" width="96" height="96" rx="12" {_L}/><rect x="78" y="88" width="44" height="44" rx="6" {_L}/>'
               f'<g {_L}><path d="M72 62 v-18 M100 62 v-18 M128 62 v-18 M72 158 v18 M100 158 v18 M128 158 v18 M52 82 h-18 M52 110 h-18 M52 138 h-18 M148 82 h18 M148 110 h18 M148 138 h18"/></g>'
               f'<g class="p">{_waves(76, OCH, 40)}</g>', True),
)


def alert(kind, eyebrow, title, text, color=W):
    """Illustration on the left, message on the right."""
    return (f'<div style="display:flex;gap:26px;align-items:center;flex-wrap:wrap">'
            f'<div style="flex:none">{ART[kind]}</div>'
            f'<div style="flex:1;min-width:240px;border-left:1px solid #3A4350;padding-left:26px">'
            f'<div style="font-family:Inter,sans-serif;font-weight:700;letter-spacing:.08em;font-size:15px;color:{color}">{eyebrow}</div>'
            f'<div style="font-family:Inter,sans-serif;font-weight:700;font-size:30px;line-height:1.15;color:#fff;margin:4px 0 8px 0">{title}</div>'
            f'<div style="color:#C3C9D1;font-size:16px;line-height:1.5">{text}</div></div></div>')
