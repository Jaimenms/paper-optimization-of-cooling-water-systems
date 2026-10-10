"""Parse the ``Display`` blocks of a GAMS listing (``.lst``) into JSON.

The listings of the original GAMS runs that produced the published results live in
``legacy/gams/``; the values extracted from them are the "original-code" references kept in
``data/reference/d4_*.json`` and used by the tests and by ``coolingnet eval``::

    uv run python scripts/parse_gams_lst.py legacy/gams/coolingnetwork_applied_v21_part3.lst \\
        data/reference/d4_part3.json

Listing -> paper item: ``part2_initial`` / ``part2_actual`` -> Table 8 (initial / current
condition); ``part2_actual_simulation`` -> desired flow rates of Table 12; ``part3`` -> Table 10
(Cases 1 and 2); ``part3_quad_dif`` -> purely hydraulic run (unlimited budget variant);
``part4_case01_redo`` -> one point of the budget sweep (B = 2437.5 USD/y, Figs. 7-8).

Output: ``{display_group: {"title": ..., "symbols": {name: scalar | {index: value} |
{row: {col: value}}}}}``; ``.L`` levels keep the bare symbol name, other suffixes are appended.
"""

from __future__ import annotations

import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:E[-+]?\d+)?"
NUM_RE = re.compile(NUM)
NAME = r"[A-Za-z_][A-Za-z0-9_]*"
HEAD = re.compile(
    rf"^----\s+(\d+)\s+(VARIABLE|PARAMETER|SET|EQUATION)\s+({NAME})(?:\.(L|M|LO|UP))?(?=\s|$)"
    rf"\s*(?:=\s*({NUM}))?"
)
SCAL = re.compile(rf"^\s+(VARIABLE|PARAMETER)\s+({NAME})(?:\.(L|M|LO|UP))?\s*=\s*({NUM})")
TITLE = re.compile(r"^----\s+(\d+)\s+(\S+)\s*$")


def is_num(tok: str) -> bool:
    return NUM_RE.fullmatch(tok) is not None


def block_end(ln: str) -> bool:
    return (
        ln.startswith("----")
        or ln.startswith("****")
        or ln.startswith("EXECUTION TIME")
        or ln.startswith("GAMS ")
    )


def parse_body(text: list[str]):
    text = [t for t in text if t.strip()]
    if not text:
        return None
    if "( ALL" in text[0]:
        m = re.search(rf"\(\s*ALL\s+({NUM})\s*\)", text[0])
        return {"ALL": float(m.group(1))} if m else None
    rows: OrderedDict = OrderedDict()
    vec: OrderedDict = OrderedDict()
    cols_pos: list[tuple[str, int]] = []
    is_table = False
    for raw in text:
        ln = raw.replace(",", " ")
        toks = ln.split()
        if not toks:
            continue
        header = (toks[0] == "+") or all(not is_num(t) for t in toks)
        if header:
            labels = toks[1:] if toks[0] == "+" else toks
            cols_pos = []
            pos = 0
            for lab in labels:
                idx = ln.find(lab, pos)
                pos = idx + len(lab)
                cols_pos.append((lab, pos))
            is_table = True
            continue
        if is_table:
            row = toks[0]
            rowd = rows.setdefault(row, OrderedDict())
            start = ln.find(row) + len(row)
            for mm in NUM_RE.finditer(ln, start):
                end = mm.end()
                best = min(cols_pos, key=lambda cp: abs(cp[1] - end))
                rowd[best[0]] = float(mm.group(0))
        else:
            # alternating label / value pairs
            i = 0
            while i + 1 < len(toks):
                if is_num(toks[i + 1]):
                    vec[toks[i]] = float(toks[i + 1])
                    i += 2
                else:
                    i += 1
    return rows if is_table else vec


def parse(path: str | Path) -> OrderedDict:
    lines = Path(path).read_text(encoding="latin1").replace("\r", "").split("\n")
    groups: OrderedDict = OrderedDict()
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = TITLE.match(ln)
        if m and not HEAD.match(ln):
            groups.setdefault(m.group(1), {"title": m.group(2), "symbols": OrderedDict()})
            i += 1
            continue
        m = HEAD.match(ln)
        if m:
            gno, _kind, name, suffix, scal = m.groups()
            g = groups.setdefault(gno, {"title": None, "symbols": OrderedDict()})
            key = name if suffix in (None, "L") else f"{name}.{suffix}"
            j = i + 1
            if scal is not None:
                g["symbols"][key] = float(scal)
                while j < len(lines) and not block_end(lines[j]):
                    ms = SCAL.match(lines[j])
                    if ms:
                        _, n2, s2, v2 = ms.groups()
                        g["symbols"][n2 if s2 in (None, "L") else f"{n2}.{s2}"] = float(v2)
                    j += 1
            else:
                body = []
                while j < len(lines) and not block_end(lines[j]):
                    body.append(lines[j])
                    j += 1
                val = parse_body(body)
                if val is not None:
                    g["symbols"][key] = val
            i = j
            continue
        i += 1
    return groups


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    groups = parse(argv[0])
    Path(argv[1]).write_text(json.dumps(groups, indent=1), encoding="utf-8")
    for gno, g in groups.items():
        print(gno, g["title"], list(g["symbols"].keys())[:8], "...")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
