#!/usr/bin/env python3
"""
Check the profile artwork renders safely as a GitHub README image.

For every profile/assets/*.svg: it must parse as XML; use no <text> (all copy is outlined), no
<script>, <foreignObject>, <image> or @import; reference nothing outside the file; stop its motion
under prefers-reduced-motion if it animates; stay under the size budget; and have a dark and a
light version.

    python scripts/check_svg.py
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "profile" / "assets"
BUDGET = 60 * 1024
FORBIDDEN = {"text", "tspan", "script", "foreignObject", "image", "iframe"}


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def check(path: Path) -> list[str]:
    problems = []
    raw = path.read_text(encoding="utf-8")
    if path.stat().st_size > BUDGET:
        problems.append(f"{path.stat().st_size} bytes, over the {BUDGET} byte budget")
    if "<!DOCTYPE" in raw or "<!ENTITY" in raw:
        return ["declares a DOCTYPE or ENTITY (not needed, and not parsed here)"]
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as err:
        return [f"invalid XML: {err}"]
    for el in root.iter():
        name = local(el.tag)
        if name in FORBIDDEN:
            problems.append(f"uses <{name}>")
        for attr, value in el.attrib.items():
            if local(attr) == "href" and not value.startswith("#"):
                problems.append(f"external reference {value!r}")
            if local(attr).startswith("on"):
                problems.append(f"event handler {attr}")
    if "@import" in raw:
        problems.append("uses @import")
    if re.search(r"url\((?!#)", raw):
        problems.append("uses url() to something outside the file")
    if ("animation" in raw or "<animate" in raw) and "prefers-reduced-motion:reduce" not in raw.replace(" ", ""):
        problems.append("animates without a prefers-reduced-motion: reduce rule")
    return problems


def main() -> int:
    files = sorted(ASSETS.glob("*.svg"))
    failed = False
    for f in files:
        problems = check(f)
        status = "ok" if not problems else "FAIL"
        print(f"{status:4} {f.name:28} {f.stat().st_size / 1024:5.1f} kB")
        for p in problems:
            print(f"     - {p}")
        failed |= bool(problems)
    names = {f.name for f in files}
    for f in files:
        for a, b in (("-dark.svg", "-light.svg"), ("-light.svg", "-dark.svg")):
            if f.name.endswith(a) and f.name.replace(a, b) not in names:
                print(f"FAIL {f.name}: no {b[1:-4]} version")
                failed = True
    print("SVG check:", "failed" if failed else f"all {len(files)} files pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
