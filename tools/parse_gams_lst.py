"""Parse GAMS listing (.lst) Display blocks into JSON (scalars, vectors, tables)."""
import json, re, sys
from collections import OrderedDict

NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:E[-+]?\d+)?"
NUM_RE = re.compile(NUM)
NAME = r"[A-Za-z_][A-Za-z0-9_]*"
HEAD = re.compile(rf"^----\s+(\d+)\s+(VARIABLE|PARAMETER|SET|EQUATION)\s+({NAME})(?:\.(L|M|LO|UP))?(?=\s|$)\s*(?:=\s*({NUM}))?")
SCAL = re.compile(rf"^\s+(VARIABLE|PARAMETER)\s+({NAME})(?:\.(L|M|LO|UP))?\s*=\s*({NUM})")
TITLE = re.compile(r"^----\s+(\d+)\s+(\S+)\s*$")

def is_num(tok):
    return NUM_RE.fullmatch(tok) is not None

def block_end(ln):
    return ln.startswith("----") or ln.startswith("****") or ln.startswith("EXECUTION TIME") or ln.startswith("GAMS ")

def parse_body(text):
    text = [t for t in text if t.strip()]
    if not text:
        return None
    if "( ALL" in text[0]:
        m = re.search(rf"\(\s*ALL\s+({NUM})\s*\)", text[0])
        return {"ALL": float(m.group(1))} if m else None
    rows = OrderedDict(); vec = OrderedDict(); cols_pos = []; is_table = False
    for raw in text:
        ln = raw.replace(",", " ")
        toks = ln.split()
        if not toks:
            continue
        header = (toks[0] == "+") or all(not is_num(t) for t in toks)
        if header:
            labels = toks[1:] if toks[0] == "+" else toks
            cols_pos = []; pos = 0
            for lab in labels:
                idx = ln.find(lab, pos); pos = idx + len(lab)
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
            # alternating label value pairs
            i = 0
            while i + 1 < len(toks):
                if is_num(toks[i + 1]) and not is_num(toks[i]) or (is_num(toks[i + 1])):
                    vec[toks[i]] = float(toks[i + 1]); i += 2
                else:
                    i += 1
    return rows if is_table else vec

def parse(path):
    lines = open(path, encoding="latin1").read().replace("\r", "").split("\n")
    groups = OrderedDict(); i = 0; cur = None
    while i < len(lines):
        ln = lines[i]
        m = TITLE.match(ln)
        if m and not HEAD.match(ln):
            cur = m.group(1); groups.setdefault(cur, {"title": m.group(2), "symbols": OrderedDict()}); i += 1; continue
        m = HEAD.match(ln)
        if m:
            gno, kind, name, suffix, scal = m.groups(); cur = gno
            g = groups.setdefault(gno, {"title": None, "symbols": OrderedDict()})
            key = name if suffix in (None, "L") else f"{name}.{suffix}"
            j = i + 1
            if scal is not None:
                g["symbols"][key] = float(scal)
                while j < len(lines) and not block_end(lines[j]):
                    ms = SCAL.match(lines[j])
                    if ms:
                        _, n2, s2, v2 = ms.groups(); g["symbols"][n2 if s2 in (None, "L") else f"{n2}.{s2}"] = float(v2)
                    j += 1
            else:
                body = []
                while j < len(lines) and not block_end(lines[j]):
                    body.append(lines[j]); j += 1
                val = parse_body(body)
                if val is not None:
                    g["symbols"][key] = val
            i = j; continue
        i += 1
    return groups

if __name__ == "__main__":
    groups = parse(sys.argv[1])
    json.dump(groups, open(sys.argv[2], "w"), indent=1)
    for gno, g in groups.items():
        print(gno, g["title"], list(g["symbols"].keys())[:8], "...")
