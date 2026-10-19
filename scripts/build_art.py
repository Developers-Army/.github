#!/usr/bin/env python3
"""
Build the organisation profile artwork: profile/assets/*-dark.svg and *-light.svg.

GitHub serves README images as <img> through an image proxy. An SVG loaded that way cannot use
web fonts or any other outside resource, so every word in the artwork is outlined here, glyph by
glyph, from the fonts in scripts/fonts (all SIL Open Font License, notices alongside). Each glyph is
stored once in <defs> and placed with <use>, which keeps the files small.

Colours come from the brand's OKLCH primitives (the website's tokens.css), converted to sRGB hex
below, so the two themes match the site: "ink" (dark) and "paper" (light).

Motion is CSS inside each SVG. Every file stops all motion under prefers-reduced-motion, and every
element's resting style is its final state, so a still frame is always complete.

Needs Python 3.10+ with fontTools and brotli (for woff2). No network access.

    python scripts/build_art.py
"""
from __future__ import annotations

import math
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "scripts" / "fonts"
OUT = ROOT / "profile" / "assets"


# --------------------------------------------------------------------------------------------
# Colour: OKLCH primitives -> sRGB hex
# --------------------------------------------------------------------------------------------

def oklch(l_pct: float, c: float, h: float) -> str:
    L = l_pct / 100
    a = c * math.cos(math.radians(h))
    b = c * math.sin(math.radians(h))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )

    def encode(v: float) -> int:
        v = min(1.0, max(0.0, v))
        v = 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        return round(v * 255)

    return "#" + "".join(f"{encode(v):02x}" for v in rgb)


PRIM = {
    "ink-1000": oklch(13, 0.008, 100),
    "ink-950": oklch(16, 0.01, 100),
    "ink-900": oklch(19, 0.012, 100),
    "ink-850": oklch(22.5, 0.013, 100),
    "ink-800": oklch(27, 0.014, 100),
    "ink-700": oklch(33, 0.014, 100),
    "ink-600": oklch(42, 0.015, 100),
    "bone-100": oklch(93, 0.02, 95),
    "bone-300": oklch(80, 0.022, 95),
    "bone-400": oklch(70, 0.02, 95),
    "bone-500": oklch(52, 0.018, 95),
    "bone-600": oklch(42, 0.016, 100),
    "bone-700": oklch(34, 0.014, 100),
    "paper-0": oklch(98.5, 0.008, 95),
    "paper-50": oklch(95.5, 0.016, 95),
    "paper-100": oklch(92.5, 0.02, 95),
    "paper-200": oklch(87, 0.022, 95),
    "paper-300": oklch(79, 0.022, 95),
    "signal-400": oklch(82, 0.17, 115),
    "signal-500": oklch(74, 0.17, 115),
    "signal-700": oklch(46, 0.12, 118),
    "signal-800": oklch(38, 0.1, 118),
    "khaki-300": oklch(76, 0.055, 92),
    "khaki-400": oklch(68, 0.06, 90),
    "khaki-700": oklch(46, 0.05, 88),
}

# Semantic roles, mirroring the site's Tier 2 colour tokens.
THEMES = {
    "dark": {
        "bg": PRIM["ink-950"],
        "sunken": PRIM["ink-1000"],
        "surface": PRIM["ink-900"],
        "raised": PRIM["ink-850"],
        "border_subtle": PRIM["ink-800"],
        "border": PRIM["ink-700"],
        "border_strong": PRIM["ink-600"],
        "text": PRIM["bone-100"],
        "muted": PRIM["bone-300"],
        "subtle": PRIM["bone-400"],
        "accent": PRIM["signal-400"],
        "accent_text": PRIM["signal-400"],
        "accent_quiet": (PRIM["signal-400"], 0.14),
        "on_accent": PRIM["ink-950"],
        "secondary_text": PRIM["khaki-300"],
        "secondary_quiet": (PRIM["khaki-400"], 0.16),
        "unit": PRIM["bone-500"],
        "reserve": PRIM["ink-700"],
        "duty": PRIM["signal-400"],
        "mark_lead": PRIM["signal-400"],
        "line": PRIM["signal-400"],  # accent drawn as a thin line or outline
    },
    "light": {
        "bg": PRIM["paper-50"],
        "sunken": PRIM["paper-100"],
        "surface": PRIM["paper-0"],
        "raised": PRIM["paper-0"],
        "border_subtle": PRIM["paper-200"],
        "border": PRIM["paper-300"],
        "border_strong": PRIM["bone-500"],
        "text": PRIM["ink-950"],
        "muted": PRIM["bone-700"],
        "subtle": PRIM["bone-600"],
        "accent": PRIM["signal-400"],
        "accent_text": PRIM["signal-800"],
        "accent_quiet": (PRIM["signal-500"], 0.22),
        "on_accent": PRIM["ink-950"],
        "secondary_text": PRIM["khaki-700"],
        "secondary_quiet": (PRIM["khaki-400"], 0.22),
        "unit": PRIM["paper-300"],
        "reserve": PRIM["paper-300"],
        "duty": PRIM["signal-700"],
        "mark_lead": PRIM["signal-800"],
        "line": PRIM["signal-700"],
    },
}

# Motion tokens from the site.
EASE_OUT = "cubic-bezier(.23,1,.32,1)"
EASE_IN_OUT = "cubic-bezier(.77,0,.175,1)"
EASE_SPRING = (
    "linear(0,.051,.167,.31,.454,.586,.699,.79,.86,.913,.951,.977,.993,1.003,1.009,1.011,"
    "1.011,1.01,1.009,1.007,1.006,1.004,1.003,1.002,1)"
)
REDUCED = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


def num(v: float) -> str:
    """Compact number: one decimal at most, no trailing zeros."""
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# --------------------------------------------------------------------------------------------
# Fonts: instance, kern, outline
# --------------------------------------------------------------------------------------------

class Face:
    def __init__(self, key: str, file: str, wght: float):
        font = TTFont(FONTS / file)
        if "fvar" in font:
            axes = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
            axes["wght"] = wght
            font = instancer.instantiateVariableFont(font, axes)
        self.key = key
        self.font = font
        self.upem = font["head"].unitsPerEm
        self.cmap = font.getBestCmap()
        self.glyphs = font.getGlyphSet()
        self.hmtx = font["hmtx"]
        self._paths: dict[str, str] = {}
        self._kern_cache: dict[tuple[str, str], int] = {}
        self._pair_tables = self._load_pair_tables()
        bp = BoundsPen(self.glyphs)
        self.glyphs[self.cmap[ord("H")]].draw(bp)
        self.cap = bp.bounds[3] / self.upem  # cap height, in em

    def _load_pair_tables(self):
        if "GPOS" not in self.font:
            return []
        gpos = self.font["GPOS"].table
        indices = set()
        for rec in gpos.FeatureList.FeatureRecord:
            if rec.FeatureTag == "kern":
                indices.update(rec.Feature.LookupListIndex)
        tables = []
        for i in sorted(indices):
            lookup = gpos.LookupList.Lookup[i]
            for st in lookup.SubTable:
                if lookup.LookupType == 9:
                    if st.ExtensionLookupType != 2:
                        continue
                    st = st.ExtSubTable
                elif lookup.LookupType != 2:
                    continue
                cover = {g: n for n, g in enumerate(st.Coverage.glyphs)}
                tables.append((st, cover))
        return tables

    def kern(self, left: str, right: str) -> int:
        key = (left, right)
        if key in self._kern_cache:
            return self._kern_cache[key]
        value = 0
        for st, cover in self._pair_tables:
            if left not in cover:
                continue
            if st.Format == 1:
                found = False
                for rec in st.PairSet[cover[left]].PairValueRecord:
                    if rec.SecondGlyph == right:
                        value = getattr(rec.Value1, "XAdvance", 0) or 0
                        found = True
                        break
                if found:
                    break
            else:
                c1 = st.ClassDef1.classDefs.get(left, 0)
                c2 = st.ClassDef2.classDefs.get(right, 0)
                rec = st.Class1Record[c1].Class2Record[c2]
                value = getattr(rec.Value1, "XAdvance", 0) or 0
                break
        self._kern_cache[key] = value
        return value

    def layout(self, text: str, size: float, track: float = 0.0):
        """Glyph names with x offsets in font units, plus the run's width in px."""
        x = 0.0
        prev = None
        out = []
        for ch in text:
            g = self.cmap.get(ord(ch))
            if g is None:
                raise SystemExit(f"{self.key}: no glyph for {ch!r}")
            if prev is not None:
                x += self.kern(prev, g)
            out.append((g, x))
            x += self.hmtx[g][0] + track * self.upem
            prev = g
        width = (x - track * self.upem) * size / self.upem if out else 0.0
        return out, width

    def width(self, text: str, size: float, track: float = 0.0) -> float:
        return self.layout(text, size, track)[1]

    def path(self, g: str) -> str:
        if g not in self._paths:
            pen = SVGPathPen(self.glyphs, ntos=lambda v: str(round(v)))
            self.glyphs[g].draw(pen)
            self._paths[g] = pen.getCommands()
        return self._paths[g]

    def gid(self, g: str) -> str:
        return f"{self.key}{self.font.getGlyphID(g)}"

    def wrap(self, text: str, size: float, max_width: float) -> list[str]:
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if line and self.width(trial, size) > max_width:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        return lines


DISPLAY = Face("a", "archivo-v25-latin-wdth125-wght800-900.woff2", 900)
BODY = Face("i", "instrument-sans-latin-wght-normal.woff2", 400)
BODY_STRONG = Face("s", "instrument-sans-latin-wght-normal.woff2", 600)
MONO = Face("m", "jetbrains-mono-latin-wght-normal.woff2", 500)

TRACK_LABEL = 0.14   # --tracking-label
TRACK_DISPLAY = -0.02


# --------------------------------------------------------------------------------------------
# SVG document
# --------------------------------------------------------------------------------------------

class Svg:
    def __init__(self, w: int, h: int, title: str, theme: str):
        self.w, self.h, self.title = w, h, title
        self.c = THEMES[theme]
        self.defs: dict[str, str] = {}
        self.body: list[str] = []
        self.css: list[str] = []

    def paint(self, role: str) -> str:
        """fill/stroke value plus optional opacity for a colour role."""
        return self.c[role]

    def add(self, markup: str) -> None:
        self.body.append(markup)

    def text(self, face: Face, text: str, x: float, y: float, size: float, color: str,
             track: float = 0.0, anchor: str = "start", cls: str | None = None) -> float:
        """Outlined text with its baseline at y. Returns the run's width in px."""
        glyphs, width = face.layout(text, size, track)
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
        uses = []
        for g, gx in glyphs:
            d = face.path(g)
            if not d:
                continue
            gid = face.gid(g)
            self.defs.setdefault(gid, d)
            uses.append(f'<use href="#{gid}" x="{round(gx)}"/>' if round(gx) else f'<use href="#{gid}"/>')
        s = size / face.upem
        attr = f' class="{cls}"' if cls else ""
        self.add(
            f'<g{attr} fill="{color}" transform="translate({num(x)} {num(y)}) scale({s:.5f} {-s:.5f})">'
            + "".join(uses) + "</g>"
        )
        return width

    def mark(self, x: float, y: float, size: float, intro: bool = False) -> None:
        """The DA mark: two rank chevrons, the lead one in the accent."""
        s = size / 24
        lead = ' class="lead"' if intro else ""
        rank = ' class="rank"' if intro else ""
        self.add(
            f'<g transform="translate({num(x)} {num(y)}) scale({s:.4f})">'
            f'<path{lead} fill="{self.c["mark_lead"]}" d="M2 11.5 12 3l10 8.5v4.6L12 7.6 2 16.1z"/>'
            f'<path{rank} fill="{self.c["text"]}" d="M2 18.4 12 9.9l10 8.5V23l-10-8.5L2 23z"/>'
            "</g>"
        )
        if intro:
            self.css.append(
                ".lead,.rank{transform-box:fill-box;transform-origin:center}"
                f"@media (prefers-reduced-motion:no-preference){{"
                f".rank{{animation:rise .56s {EASE_OUT} backwards}}"
                f".lead{{animation:drop .56s {EASE_OUT} .14s backwards}}}}"
                "@keyframes rise{from{opacity:0;transform:translateY(60%)}}"
                "@keyframes drop{from{opacity:0;transform:translateY(-60%)}}"
            )

    def panel(self, fill: str = "bg", stroke: str = "border_subtle", dash: str | None = None,
              radius: float = 8) -> None:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(
            f'<rect x=".5" y=".5" width="{self.w - 1}" height="{self.h - 1}" rx="{num(radius)}" '
            f'fill="{self.c[fill]}" stroke="{self.c[stroke]}"{dash_attr}/>'
        )

    def tag(self, x: float, y: float, label: str, tone: str = "accent", dot_cls: str | None = None,
            size: float = 14, anchor: str = "start") -> float:
        """The site's Tag: mono caps, a square dot, a quiet fill and hairline border. y is the top."""
        fg = self.c["accent_text"] if tone == "accent" else self.c["secondary_text"]
        quiet, alpha = self.c["accent_quiet"] if tone == "accent" else self.c["secondary_quiet"]
        pad, dot, gap = 10, 7, 8
        h = round(size * 2.1)
        w = pad + dot + gap + MONO.width(label, size, TRACK_LABEL) + pad
        if anchor == "end":
            x -= w
        dot_attr = f' class="{dot_cls}"' if dot_cls else ""
        self.add(
            f'<rect x="{num(x + .5)}" y="{num(y + .5)}" width="{num(w - 1)}" height="{h - 1}" rx="2" '
            f'fill="{quiet}" fill-opacity="{alpha}" stroke="{fg}" stroke-opacity=".45"/>'
            f'<rect{dot_attr} x="{num(x + pad)}" y="{num(y + (h - dot) / 2)}" width="{dot}" height="{dot}" fill="{fg}"/>'
        )
        baseline = y + h / 2 + MONO.cap * size / 2
        self.text(MONO, label, x + pad + dot + gap, baseline, size, fg, TRACK_LABEL)
        return w

    def render(self) -> str:
        defs = "".join(f'<path id="{k}" d="{v}"/>' for k, v in self.defs.items())
        css = "".join(self.css)
        style = f"<style>{css}</style>" if css else ""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="t">'
            f'<title id="t">{self.title}</title>{style}<defs>{defs}</defs>'
            + "".join(self.body) + "</svg>\n"
        )


# --------------------------------------------------------------------------------------------
# Artwork
# --------------------------------------------------------------------------------------------

def mulberry32(seed: int):
    """The website's seeded PRNG, bit for bit, so the banner scatters like the site's hero."""
    a = seed & 0xFFFFFFFF

    def imul(x: int, y: int) -> int:
        return (x * y) & 0xFFFFFFFF

    def rand() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = imul(a ^ (a >> 15), 1 | a)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return rand


PLATOONS, COLS, ROWS = 3, 4, 9
ON_DUTY = {"0-1-2", "0-5-0", "1-0-1", "1-3-3", "1-7-2", "2-2-0", "2-6-3"}
RESERVE = {"0-8-3", "1-8-0", "1-8-3", "2-8-1", "2-8-2", "2-7-0", "0-7-3"}


def formation(svg: Svg, x0: float, y0: float, unit: float, gap: float, pgap: float) -> None:
    """Units scatter in, settle into three ranked platoons; units on duty breathe in the accent."""
    rand = mulberry32(7)
    pw = COLS * unit + (COLS - 1) * gap
    parts = []
    for p in range(PLATOONS):
        for i in range(ROWS * COLS):
            row, col = divmod(i, COLS)
            key = f"{p}-{row}-{col}"
            fx = (rand() - 0.5) * 360
            fy = (rand() - 0.5) * 300 - 40
            fr = (rand() - 0.5) * 180
            delay = 0.35 + row * 0.07 + p * 0.04 + rand() * 0.12
            pulse = round(rand() * 2400)
            x = x0 + p * (pw + pgap) + col * (unit + gap)
            y = y0 + row * (unit + gap)
            style = f"--x:{num(fx)}px;--y:{num(fy)}px;--r:{num(fr)}deg;--d:{delay:.2f}s"
            if key in ON_DUTY:
                cls, paint = "u duty", f'fill="{svg.c["duty"]}"'
                style += f";--p:{(1.8 + pulse / 1000):.2f}s"
            elif key in RESERVE:
                cls, paint = "u", f'fill="none" stroke="{svg.c["reserve"]}" stroke-width="1.5"'
                x, y, size = x + .75, y + .75, unit - 1.5
                parts.append(
                    f'<rect class="{cls}" style="{style}" x="{num(x)}" y="{num(y)}" '
                    f'width="{num(size)}" height="{num(size)}" rx="2" {paint}/>'
                )
                continue
            else:
                cls, paint = "u", f'fill="{svg.c["unit"]}"'
            parts.append(
                f'<rect class="{cls}" style="{style}" x="{num(x)}" y="{num(y)}" '
                f'width="{num(unit)}" height="{num(unit)}" rx="2" {paint}/>'
            )
    svg.add("<g>" + "".join(parts) + "</g>")
    svg.css.append(
        ".u{transform-box:fill-box;transform-origin:center}"
        "@media (prefers-reduced-motion:no-preference){"
        f".u{{animation:enter .9s {EASE_SPRING} var(--d) backwards,fade .3s {EASE_OUT} var(--d) backwards}}"
        f".duty{{animation:enter .9s {EASE_SPRING} var(--d) backwards,fade .3s {EASE_OUT} var(--d) backwards,"
        f"duty 2.4s {EASE_IN_OUT} var(--p) infinite}}}}"
        "@keyframes enter{from{transform:translate(var(--x),var(--y)) rotate(var(--r)) scale(.6)}}"
        "@keyframes fade{from{opacity:0}}"
        "@keyframes duty{0%,100%{opacity:1}50%{opacity:.4}}"
    )


def banner(theme: str) -> str:
    W, H, PAD = 1280, 400, 64
    svg = Svg(W, H, "Developers Army. An AI company that ships products.", theme)
    c = svg.c
    svg.panel("bg", "border_subtle", radius=10)

    # Brand row: mark and wordmark, top left.
    mark = 30
    svg.mark(PAD, PAD - 8, mark, intro=True)
    word_size = 17
    base = PAD - 8 + mark / 2 + DISPLAY.cap * word_size / 2
    w = svg.text(DISPLAY, "DEVELOPERS", PAD + mark + 14, base, word_size, c["text"], 0.02)
    svg.text(DISPLAY, " ARMY", PAD + mark + 14 + w, base, word_size, c["subtle"], 0.02)

    # Formation, right.
    unit, gap, pgap = 20, 7, 22
    fw = PLATOONS * (COLS * unit + (COLS - 1) * gap) + (PLATOONS - 1) * pgap
    fh = ROWS * unit + (ROWS - 1) * gap
    fx = W - PAD - fw
    fy = PAD - 8
    formation(svg, fx, fy, unit, gap, pgap)
    svg.text(MONO, "FIG. 01 · AGENTS IN FORMATION", fx, fy + fh + 36, 14, c["subtle"], TRACK_LABEL)

    # Headline, bottom left, sized to the space left of the formation.
    lines = ["An AI company", "that ships products."]
    max_w = fx - PAD - 56
    size = 76.0
    while max(DISPLAY.width(l, size, -0.03) for l in lines) > max_w:
        size -= 0.5
    last = H - PAD - 6
    first = last - size * 0.98
    svg.text(DISPLAY, lines[0], PAD, first, size, c["text"], -0.03)
    svg.text(DISPLAY, lines[1], PAD, last, size, c["text"], -0.03)

    # Eyebrow above the headline: a unit on duty, then the category.
    eb = first - DISPLAY.cap * size - 30
    svg.add(f'<rect x="{PAD}" y="{num(eb - 10)}" width="10" height="10" rx="1" fill="{c["duty"]}"/>')
    svg.text(MONO, "AI COMPANY · PRODUCT INCUBATOR", PAD + 22, eb, 15, c["accent_text"], TRACK_LABEL)

    svg.css.append(REDUCED)
    return svg.render()


def console(svg: Svg, x: float, y: float, w: float, h: float) -> None:
    """An invented-looking console glimpse, shapes only: projects down the side, one view at a time."""
    c = svg.c
    out = [f'<rect x="{num(x + .5)}" y="{num(y + .5)}" width="{num(w - 1)}" height="{num(h - 1)}" rx="6" '
           f'fill="{c["sunken"]}" stroke="{c["border_subtle"]}"/>']
    bar = 38
    out.append(f'<path d="M{num(x)} {num(y + bar)}h{num(w)}" stroke="{c["border_subtle"]}"/>')
    out.append(f'<rect x="{num(x + 16)}" y="{num(y + 15)}" width="64" height="8" rx="2" fill="{c["unit"]}"/>')
    for k in range(2):
        out.append(f'<rect x="{num(x + w - 30 - k * 18)}" y="{num(y + 14)}" width="10" height="10" rx="2" '
                   f'fill="none" stroke="{c["border"]}" stroke-width="1.5"/>')

    # Sidebar: five projects, one selected.
    side = 132
    out.append(f'<path d="M{num(x + side)} {num(y + bar)}v{num(h - bar)}" stroke="{c["border_subtle"]}"/>')
    row_h, top = 32, y + bar + 14
    out.append(f'<g class="sel"><rect x="{num(x + 8)}" y="{num(top)}" width="{side - 16}" height="{row_h - 6}" '
               f'rx="3" fill="{c["raised"]}"/><rect x="{num(x + 8)}" y="{num(top)}" width="3" height="{row_h - 6}" '
               f'fill="{c["accent"]}"/></g>')
    lengths = [62, 48, 70, 54, 40]
    dots = ["duty", "duty", "secondary_text", "duty", "unit"]
    for r in range(5):
        ry = top + r * row_h + (row_h - 6) / 2
        out.append(f'<rect x="{num(x + 20)}" y="{num(ry - 3.5)}" width="7" height="7" fill="{c[dots[r]]}"/>')
        out.append(f'<rect x="{num(x + 34)}" y="{num(ry - 3)}" width="{lengths[r]}" height="6" rx="2" fill="{c["unit"]}"/>')

    # Main view: three tiles, then a list of work items with their state.
    mx, my, mw = x + side + 16, y + bar + 16, w - side - 32
    tw = (mw - 2 * 10) / 3
    for t in range(3):
        tx = mx + t * (tw + 10)
        out.append(f'<rect x="{num(tx + .5)}" y="{num(my + .5)}" width="{num(tw - 1)}" height="63" rx="4" '
                   f'fill="{c["surface"]}" stroke="{c["border_subtle"]}"/>')
        out.append(f'<rect x="{num(tx + 12)}" y="{num(my + 14)}" width="{num(tw * .42)}" height="5" rx="2" fill="{c["unit"]}"/>')
        out.append(f'<rect x="{num(tx + 12)}" y="{num(my + 32)}" width="{num(tw * (.3 + .12 * t))}" height="16" rx="2" '
                   f'fill="{c["text"] if t else c["accent_text"]}" fill-opacity="{1 if t == 0 else .8}"/>')
    ly = my + 64 + 18
    states = ["duty", "secondary_text", "duty", "unit"]
    widths = [.56, .44, .62, .38]
    for r in range(4):
        ry = ly + r * 34
        out.append(f'<path d="M{num(mx)} {num(ry + 30)}h{num(mw)}" stroke="{c["border_subtle"]}"/>')
        out.append(f'<rect x="{num(mx + 2)}" y="{num(ry + 9)}" width="8" height="8" fill="{c[states[r]]}"/>')
        out.append(f'<rect x="{num(mx + 22)}" y="{num(ry + 10)}" width="{num(mw * widths[r])}" height="6" rx="2" fill="{c["muted"]}" fill-opacity=".55"/>')
        out.append(f'<rect x="{num(mx + mw - 56)}" y="{num(ry + 8)}" width="56" height="10" rx="2" fill="none" stroke="{c["border"]}"/>')
    svg.add("<g>" + "".join(out) + "</g>")
    # The selection steps through the projects: one console, several projects.
    stops = []
    for k in range(4):
        a, b = k * 25, k * 25 + 21
        stops.append(f"{a}%,{b}%{{transform:translateY({k * row_h}px)}}")
    svg.css.append(
        "@media (prefers-reduced-motion:no-preference){"
        f".sel{{animation:sel 10s {EASE_OUT} 1.5s infinite}}}}"
        "@keyframes sel{" + "".join(stops) + "100%{transform:translateY(0)}}"
    )


def sightline(theme: str) -> str:
    W, H, PAD = 960, 400, 48
    svg = Svg(W, H, "Sightline, live: a multi-project ops console for running several projects from one place.", theme)
    c = svg.c
    svg.panel("surface", "border")
    tw = svg.tag(PAD, PAD, "LIVE", "accent", dot_cls="live")
    svg.text(MONO, "OPS CONSOLE", PAD + tw + 16, PAD + 15 + MONO.cap * 14 / 2, 14, c["subtle"], TRACK_LABEL)
    svg.text(DISPLAY, "Sightline", PAD - 2, 168, 58, c["text"], TRACK_DISPLAY)
    lines = BODY.wrap("A multi-project ops console for running several projects from one place.", 30, 392)
    for n, line in enumerate(lines):
        svg.text(BODY, line, PAD, 228 + n * 40, 30, c["muted"])
    console(svg, 456, PAD - 8, W - 456 - PAD + 8, H - 2 * PAD + 16)
    svg.css.append(
        "@media (prefers-reduced-motion:no-preference){"
        f".live{{animation:pulse 2.4s {EASE_IN_OUT} infinite}}}}"
        "@keyframes pulse{50%{opacity:.35}}"
        + REDUCED
    )
    return svg.render()


def in_the_works(theme: str) -> str:
    W, H, PAD = 960, 170, 44
    svg = Svg(W, H, "Three more products in the works. We name them when they ship.", theme)
    c = svg.c
    svg.panel("bg", "border", dash="6 6")
    size, gap = 26, 9
    top = (H - size) / 2
    for k in range(3):
        svg.add(f'<rect class="slot s{k}" x="{num(PAD + k * (size + gap) + .75)}" y="{num(top + .75)}" '
                f'width="{num(size - 1.5)}" height="{num(size - 1.5)}" rx="2" fill="none" '
                f'stroke="{c["border_strong"]}" stroke-width="1.5"/>')
    tx = PAD + 3 * size + 2 * gap + 34
    svg.text(DISPLAY, "Three more in the works.", tx, 80, 40, c["text"], TRACK_DISPLAY)
    svg.text(BODY, "We name them when they ship.", tx, 124, 30, c["muted"])
    # The empty slots light up one after another: work under way, nothing named yet.
    svg.css.append(
        "@media (prefers-reduced-motion:no-preference){"
        f".slot{{animation:slot 3.6s {EASE_IN_OUT} infinite}}"
        ".s1{animation-delay:.4s}.s2{animation-delay:.8s}}"
        f"@keyframes slot{{0%,60%,100%{{stroke:{c['border_strong']}}}30%{{stroke:{c['secondary_text']}}}}}"
        + REDUCED
    )
    return svg.render()


def agent_loop(theme: str) -> str:
    W, H = 960, 300
    svg = Svg(W, H, "How a piece of work ships: Brief, Agent, Pull request, Review, Ship. "
                    "At Review, changes requested go back to the agent.", theme)
    c = svg.c
    svg.panel("bg", "border_subtle")
    steps = ["Brief", "Agent", "Pull request", "Review", "Ship"]
    xs = [96 + i * 192 for i in range(5)]
    rail = 180
    node = 14

    # The "changes requested" arc, Review back to Agent, with its label above.
    ax0, ax1, top = xs[3], xs[1], rail - 16
    arc = f"M{ax0} {top}C{ax0} 64 {ax1} 64 {ax1} {top}"
    head = f"M{ax1 - 7} {top - 9}L{ax1} {top}L{ax1 + 7} {top - 9}"
    svg.add(f'<path d="{arc}" fill="none" stroke="{c["border"]}" stroke-width="1.5" stroke-dasharray="4 6"/>')
    svg.add(f'<path class="arc" d="{arc}" pathLength="1" fill="none" stroke="{c["line"]}" stroke-width="2" '
            f'stroke-dasharray="1 1"/>')
    svg.add(f'<path d="{head}" fill="none" stroke="{c["border"]}" stroke-width="1.5"/>')
    svg.add(f'<path class="head" d="{head}" fill="none" stroke="{c["line"]}" stroke-width="2"/>')
    label = "CHANGES REQUESTED · BACK TO THE AGENT"
    svg.text(MONO, label, W / 2, 72, 15, c["subtle"], TRACK_LABEL, anchor="middle")
    svg.text(MONO, label, W / 2, 72, 15, c["accent_text"], TRACK_LABEL, anchor="middle", cls="lbl")

    # Rail, progress fill, nodes, marker.
    svg.add(f'<path d="M{xs[0]} {rail}H{xs[-1]}" stroke="{c["border"]}" stroke-width="2"/>')
    svg.add(f'<rect class="fill" x="{xs[0]}" y="{rail - 1}" width="{xs[-1] - xs[0]}" height="2" fill="{c["line"]}"/>')
    for i, x in enumerate(xs):
        svg.add(f'<rect class="n n{i}" x="{x - node / 2}" y="{rail - node / 2}" width="{node}" height="{node}" '
                f'rx="2" fill="{c["duty"]}"/>')
    svg.add(f'<g class="mk"><rect x="{xs[-1] - 17}" y="{rail - 17}" width="34" height="34" rx="4" '
            f'fill="{c["line"]}" fill-opacity=".18"/><rect x="{xs[-1] - 9}" y="{rail - 9}" width="18" '
            f'height="18" rx="3" fill="none" stroke="{c["line"]}" stroke-width="2"/></g>')

    for i, (x, name) in enumerate(zip(xs, steps)):
        svg.text(MONO, f"{i + 1:02d}", x, rail + 42, 14, c["subtle"], TRACK_LABEL, anchor="middle")
        svg.text(BODY_STRONG, name, x, rail + 80, 28, c["text"], anchor="middle")

    # One pass every 10 s: Brief, Agent, Pull request, Review; a pause while the arc draws back to
    # the agent; then Ship. Resting state (no animation) is the finished pass.
    step = 192
    hold = f"animation-timing-function:{EASE_IN_OUT}"
    pos = [(0, 0, 0), (4, 0, 1), (10, 0, 1), (20, 1, 1), (30, 2, 1), (40, 3, 1), (62, 3, 1),
           (76, 4, 1), (92, 4, 1), (97, 4, 0), (100, 4, 0)]
    mk = "".join(f"{p}%{{transform:translateX({(n - 4) * step}px);opacity:{o};{hold}}}" for p, n, o in pos)
    fill = "".join(f"{p}%{{transform:scaleX({n / 4});opacity:{o};{hold}}}" for p, n, o in pos)
    reach = [4, 20, 30, 40, 76]
    node_css = ""
    for i, t in enumerate(reach):
        node_css += (f"@keyframes n{i}{{0%,{t - .5}%{{fill:{c['unit']}}}{t}%,92%{{fill:{c['duty']}}}"
                     f"97%,100%{{fill:{c['unit']}}}}}.n{i}{{animation-name:n{i}}}")
    svg.css.append(
        ".fill{transform-box:fill-box;transform-origin:0 50%}"
        ".lbl{opacity:0}"
        "@media (prefers-reduced-motion:no-preference){"
        ".mk{animation:mk 10s infinite}"
        ".fill{animation:fill 10s infinite}"
        ".n{animation-duration:10s;animation-iteration-count:infinite;animation-timing-function:step-end}"
        f".arc{{animation:arc 10s {EASE_OUT} infinite}}"
        ".head{animation:head 10s infinite}"
        ".lbl{animation:lbl 10s infinite}"
        + node_css + "}"
        f"@keyframes mk{{{mk}}}"
        f"@keyframes fill{{{fill}}}"
        "@keyframes arc{0%,44%{stroke-dashoffset:1;opacity:1}58%,92%{stroke-dashoffset:0;opacity:1}"
        "97%,100%{stroke-dashoffset:0;opacity:0}}"
        "@keyframes head{0%,55%{opacity:0}58%,92%{opacity:1}97%,100%{opacity:0}}"
        "@keyframes lbl{0%,44%{opacity:0}48%,62%{opacity:1}66%,100%{opacity:0}}"
        + REDUCED
    )
    return svg.render()


def button(theme: str, label: str, primary: bool, title: str, arrow: bool = False) -> str:
    size, pad, h = 16, 20, 44
    face = BODY_STRONG
    tw = face.width(label, size)
    aw = 22 if arrow else 0
    W = round(pad + tw + aw + pad)
    svg = Svg(W, h, title, theme)
    c = svg.c
    if primary:
        svg.add(f'<rect width="{W}" height="{h}" rx="4" fill="{c["accent"]}"/>')
        fg = c["on_accent"]
    else:
        svg.add(f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="4" fill="{c["surface"]}" '
                f'stroke="{c["border_strong"]}"/>')
        fg = c["text"]
    base = h / 2 + face.cap * size / 2
    svg.text(face, label, pad, base, size, fg)
    if arrow:
        ax = pad + tw + 10
        svg.add(f'<path d="M{num(ax)} {h / 2}h12M{num(ax + 7)} {h / 2 - 5}l5 5-5 5" fill="none" '
                f'stroke="{fg}" stroke-width="1.75" stroke-linecap="square"/>')
    return svg.render()


def rule(theme: str) -> str:
    W, H, m = 960, 40, 28
    svg = Svg(W, H, "Developers Army", theme)
    c = svg.c
    gap = 26
    svg.add(f'<path d="M0 {H / 2}H{W / 2 - m / 2 - gap}M{W / 2 + m / 2 + gap} {H / 2}H{W}" stroke="{c["border"]}"/>')
    svg.mark(W / 2 - m / 2, (H - m) / 2, m)
    return svg.render()


ART = {
    "banner": banner,
    "sightline": sightline,
    "in-the-works": in_the_works,
    "agent-loop": agent_loop,
    "button-website": lambda t: button(t, "Visit the website", True, "Visit the website", arrow=True),
    "button-email": lambda t: button(t, "info@developersarmy.com", False, "Email info@developersarmy.com"),
    "rule": rule,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, build in ART.items():
        for theme in THEMES:
            path = OUT / f"{name}-{theme}.svg"
            path.write_text(build(theme), encoding="utf-8", newline="\n")
            print(f"{path.relative_to(ROOT).as_posix():40} {path.stat().st_size / 1024:6.1f} kB")


if __name__ == "__main__":
    main()
