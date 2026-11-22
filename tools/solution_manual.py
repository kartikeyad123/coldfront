"""Build the COLDFRONT solution manual. Every answer and number comes from the
work orders themselves (their reference solutions) run through the model here,
so the manual cannot drift from the game.
Run from the repo root:  python tools/solution_manual.py"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from coldfront import contracts as C   # noqa: E402

OUT = os.path.join(ROOT, "report", "guide")


def tex(s):
    return (s.replace("$", r"\$").replace("%", r"\%").replace("≤", r"$\le$").replace(" °C", r"\,°C")
            .replace("×", r"$\times$").replace("m³", r"m\textsuperscript{3}").replace("_", r"\_"))


PHRASE = dict(
    T_chws_C=lambda v: f"water supply {v:g}\\,°C", dT_chw=lambda v: f"rise {v:g}\\,°C",
    rejection=lambda v: "dry cooler" if v == "dry" else "cooling tower",
    tank=lambda v: "tank on", tank_MWh=lambda v: f"capacity {v:g}\\,MWh", tank_rate_MW=lambda v: f"rate {v:g}\\,MW",
    price_charge=lambda v: f"charge at or below \\${v:g}", price_discharge=lambda v: f"discharge at or above \\${v:g}")


def say(step):
    return ", ".join(PHRASE[k](v) for k, v in step.items()) if step else "change nothing"


def play(o, steps):
    m = C.run_order(o, C.plans_for(o, steps)).metrics
    return C.evaluate(o, m)[0], m


def fmt(t, v):
    s = f"{v:,.{t.nd}f}"
    return ("\\$" + s) if t.unit == "$" else s


# Wrong answers worth seeing, on set A. (label, steps)
TRAPS = dict(
    first_shift=[("20\\,°C: too warm (20 + 8 = 28\\,°C at the racks)", (dict(T_chws_C=20.0),))],
    heatwave=[("Tower all day: over the water permit", ()),
              ("Tower first, dry cooler in the heat: backwards", (dict(rejection="tower"), dict(rejection="dry")))],
    chiller_down=[("16\\,°C at the trip: not warm enough", ({}, dict(T_chws_C=16.0))),
                  ("20\\,°C at the trip: racks pass 27\\,°C", ({}, dict(T_chws_C=20.0)))],
    price_spike=[("Charge at \\$95 from midnight: fills on dearer power", (dict(price_charge=95.0), {}))],
    not_a_drop=[("Warmest water only, no rise, no tank", "cap")],
    blackwell=[("20\\,°C: chillers still needed, and two are gone", (dict(T_chws_C=20.0),)),
               ("25\\,°C: compressors still run", (dict(T_chws_C=25.0),))])

SAY = dict(
    first_shift="Colder water isn't safer, it just costs more. I raised it until the servers were near their limit.",
    heatwave="I had water for half a day, so I spent it in the afternoon, where each cubic metre saves the most work.",
    chiller_down="I couldn't add a chiller, so I made the night air do the work.",
    price_spike="The tank is a transient control volume. I made the cold water on the cheapest power and spent it "
                "in the most expensive hours.",
    not_a_drop="No single control fixes a dry cooler in the desert. Three small gains add up: warm water, less "
               "pumping, and cold made at night.",
    blackwell="With warm-water liquid cooling the chillers stop entirely, so losing two of them doesn't matter.")


def section(key):
    sets = C.VARIANTS[key]
    o = sets[0]
    stages = ["Before you start"] + [f"At the {int(t):02d}:{int(t % 1 * 60):02d} pause" for t in o.pauses]
    todo = " & ".join(["Set"] + stages) + r" \\ \midrule" + "\n"
    for i, v in enumerate(sets):
        steps = list(v.solution) + [{}] * (len(stages) - len(v.solution))
        todo += " & ".join([f"\\textbf{{{C.SETS[i]}}}"] + [say(s) for s in steps]) + r" \\" + "\n"
    head = " & ".join(["Set", "Play", "Grade"] + ["\\shortstack[r]{" + tex(t.label).replace(" ", "\\\\", 1) + (f" [{tex(t.unit)}]" if t.unit else "") + "}"
                                               for t in o.targets])
    body = ""
    for i, v in enumerate(sets):
        rows = [("\\textit{limit / for an A}", None), ("do nothing", ()), ("\\textbf{answer}", v.solution)]
        if v.passing != v.solution:
            rows.insert(2, ("pass, not A: " + "; then ".join(say(s) for s in v.passing), v.passing))
        if i == 0:
            for label, steps in TRAPS[key]:
                if steps == "cap":
                    steps = (dict(T_chws_C=v.limits["T_chws_C"][1]),)
                rows.append((label, steps))
        for label, steps in rows:
            if steps is None:
                cells = [f"$\\le$ {fmt(t, t.limit)}" + (f" / {fmt(t, t.a_level)}" if t.a_level is not None else "")
                         for t in v.targets]
                body += " & ".join([C.SETS[i], label, ""] + cells) + r" \\" + "\n"
            else:
                g, m = play(v, steps)
                if label == "\\textbf{answer}":
                    assert g == "A", (key, i, g)
                body += " & ".join(["", label, f"\\textbf{{{g}}}"] + [fmt(t, m[t.metric]) for t in v.targets]) + r" \\" + "\n"
        body += r"\midrule" + "\n" if i < 2 else ""
    differ = "; ".join(f"{C.SETS[i]}: {tex(v.client)}" + (f", {tex(v.events[0].title)}" if v.events else "")
                       for i, v in enumerate(sets))
    return rf"""
\section*{{{o.number}\quad {tex(o.title)}}}
\lab{{The problem (set A)}}{tex(o.brief)}

\lab{{The control that matters}}{tex(o.lever)}.

\begin{{qbox}}{{What to do}}
\small\begin{{tabular}}{{@{{}}l {'p{%.2f\\linewidth} ' % (0.86 / len(stages)) * len(stages)}@{{}}}}
{todo}\end{{tabular}}
\end{{qbox}}

\lab{{Why it works}}{tex(o.lesson)}

\begin{{center}}\footnotesize\setlength{{\tabcolsep}}{{4pt}}
\begin{{tabular}}{{@{{}}l p{{{0.42 if len(o.targets) < 4 else 0.33}\linewidth}} c {'r ' * len(o.targets)}@{{}}}}
\toprule
{head} \\
\midrule
{body}\bottomrule
\end{{tabular}}
\end{{center}}
{{\footnotesize\color{{cfgrey}}The sets differ in: {differ}.}}

\begin{{saybox}}{SAY[key]}\end{{saybox}}
"""


PRE = r"""\documentclass[11pt,letterpaper]{article}
\usepackage[margin=0.9in]{geometry}
\usepackage{fontspec}
\usepackage{unicode-math}
\setmainfont{TeX Gyre Termes}
\setmathfont{TeX Gyre Termes Math}
\usepackage{microtype}
\usepackage{amsmath}
\usepackage{booktabs}
\usepackage{array}
\usepackage{xcolor}
\usepackage[most]{tcolorbox}
\usepackage{fancyhdr}
\usepackage[hidelinks]{hyperref}
\hypersetup{pdftitle={COLDFRONT Solution Manual}, pdfauthor={Kartikeya Daiya}}
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}
\linespread{1.12}
\raggedbottom
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\small COLDFRONT solution manual}\fancyhead[R]{\small K.~Daiya}
\fancyfoot[C]{\small\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\definecolor{cfblue}{RGB}{26,77,158}
\definecolor{cfgrey}{RGB}{90,90,90}
\newtcolorbox{qbox}[1]{enhanced, colback=cfblue!4, colframe=cfblue!70, coltitle=white,
  fonttitle=\bfseries, title={#1}, left=6pt, right=6pt, top=4pt, bottom=4pt, boxrule=0.6pt, arc=2pt}
\newtcolorbox{keybox}{enhanced, colback=black!3, colframe=black!45, left=6pt, right=6pt,
  top=4pt, bottom=4pt, boxrule=0.5pt, arc=2pt}
\newtcolorbox{saybox}{enhanced, colback=green!4, colframe=green!40!black, left=6pt, right=6pt,
  top=4pt, bottom=4pt, boxrule=0.5pt, arc=2pt, title={Say it like this}, fonttitle=\bfseries\small, coltitle=white}
\newcommand{\lab}[1]{\textbf{\color{cfblue}#1}\quad}
\begin{document}
\begin{center}
{\LARGE\bfseries COLDFRONT Solution Manual\par}
\vspace{4pt}{\large Six problems, three sets of numbers each: the answer, and why it works\par}
\vspace{4pt}{\normalsize Kartikeya Daiya \quad$\cdot$\quad coldfront.streamlit.app\par}
\end{center}
\vspace{2pt}\hrule\vspace{8pt}

Every result here was produced by running the work order through the model. Settings not mentioned stay at
their defaults. ``Rise'' is the slider \emph{How much the water warms up in the hall}. Each problem has three
sets of numbers (A, B, C); press \textbf{New numbers} in the game to switch. The method is the same for all
three sets, only the values change.

\begin{keybox}
\textbf{Each problem is about a different control.}\\[2pt]
\begin{tabular}{@{}lll@{}}
01 First Shift & chilled-water temperature & the lift \\
02 Heatwave & tower or dry cooler, switched in the day & water against energy \\
03 Chiller Down & free cooling & capacity from the night air \\
04 Price Spike & when the tank charges & a transient control volume \\
05 Not a Drop & rise and a night-charged tank & make cold when the lift is small \\
06 Blackwell Retrofit & facility water for liquid cooling & no refrigeration cycle at all \\
\end{tabular}
\[
\mathrm{COP}_\mathrm{Carnot} = \frac{T_L}{T_H - T_L}
\qquad\qquad
\mathrm{PUE} = \frac{P_\mathrm{total}}{P_\mathrm{IT}}
\]
where $T_L$ and $T_H$ are the evaporating and condensing temperatures in kelvin, and PUE is total facility
power divided by computer power (lower is better). The lift is $T_H - T_L$. Almost every answer below
makes the lift smaller, or does the work in the hours when it is smaller.
\end{keybox}

\textbf{Grades.} A: every target met and the efficiency target beaten by a margin. B: every target met.
C: servers safe but an efficiency target missed. D: a safety limit crossed.
"""

if __name__ == "__main__":
    doc = PRE + "\n\\newpage\n".join([""] + [section(k) for k in C.VARIANTS]) + "\n\\end{document}\n"
    path = os.path.join(OUT, "COLDFRONT_Solution_Manual.tex")
    open(path, "w").write(doc)
    for _ in range(2):
        subprocess.run(["xelatex", "-interaction=nonstopmode", "COLDFRONT_Solution_Manual.tex"], cwd=OUT,
                       stdout=subprocess.DEVNULL, check=False)
    print("wrote", path)
