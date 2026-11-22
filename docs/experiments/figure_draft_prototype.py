# 試作（製品の一部ではない）。要求分析 7.2 の案を確かめるために使った。
# 使い方: python docs/experiments/figure_draft_prototype.py migrated/screen-transition [-v]
"""試作: 取り出したデータだけから、Mermaid の図を作る（AI を使わない）。"""
import json, re, sys
PT = 12700
LABEL_LIMIT = 12 * PT     # ラベルと線の距離の上限
HEAD_LIMIT = 6 * PT       # 見出しと囲みの上辺の距離の上限

def seg_rect_distance(p, q, bbox):
    """線分 pq と長方形の距離（交われば 0）。標本点で近似する。"""
    x, y, w, h = bbox; best = None
    for i in range(201):
        t = i / 200; px = p[0] + (q[0]-p[0])*t; py = p[1] + (q[1]-p[1])*t
        dx = max(x - px, 0, px - (x+w)); dy = max(y - py, 0, py - (y+h))
        d = (dx*dx + dy*dy) ** 0.5
        best = d if best is None or d < best else best
    return best

def contains(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[0]+outer[2] >= inner[0]+inner[2] and outer[1]+outer[3] >= inner[1]+inner[3]

def build(sheet):
    shapes = {s["id"]: s for s in sheet["shapes"]}
    notes, arrows = [], []
    ends = {}
    for c in sheet["connectors"]:
        a = c.get("attached_start") or (c.get("near_start") or {}).get("shape")
        b = c.get("attached_end") or (c.get("near_end") or {}).get("shape")
        if a is None or b is None:
            notes.append(f"【要確認: c{c['id']} は、端点の近くに図形がない】"); continue
        if shapes[a]["textbox"] or shapes[b]["textbox"]:
            notes.append(f"- 線（c{c['id']}）: 端点が文字枠（s{a}、s{b}）にあるため、つながりとして書いていない"); continue
        if c["arrow_start"] and not c["arrow_end"]: a, b = b, a
        ends[c["id"]] = (a, b, c["arrow_start"] == c["arrow_end"])
    nodes = {x for a, b, _ in ends.values() for x in (a, b)}
    # ラベル: 文字枠を、最も近い線に付ける
    labels = [s for s in sheet["shapes"] if s["textbox"] and s["text"] and s["id"] not in nodes]
    by_line = {}
    used = set()
    for s in labels:
        dist = sorted((seg_rect_distance(c["start"], c["end"], s["bbox"]), c["id"]) for c in sheet["connectors"] if c["id"] in ends)
        if dist and dist[0][0] <= LABEL_LIMIT:
            if len(dist) > 1 and dist[1][0] <= LABEL_LIMIT and dist[1][0] - dist[0][0] < 2 * PT:
                notes.append(f"【要確認: ラベル s{s['id']}「{s['text']}」は、c{dist[0][1]} と c{dist[1][1]} のどちらの線のものか決められない】"); used.add(s["id"]); continue
            by_line.setdefault(dist[0][1], []).append((dist[0][0], s)); used.add(s["id"])
    for cid, items in by_line.items():
        if len(items) > 1:
            notes.append(f"【要確認: c{cid} の近くにラベルが複数ある（{'、'.join('s'+s['id'] for _, s in items)}）】")
    # 囲み: 文字のない図形で、節点を内側に含むもの。節点ごとに最も小さい囲み
    boxes = [s for s in sheet["shapes"] if not s["text"] and s["id"] not in nodes and any(contains(s["bbox"], shapes[n]["bbox"]) for n in nodes)]
    member = {}
    for n in nodes:
        inside = [b for b in boxes if contains(b["bbox"], shapes[n]["bbox"])]
        if inside: member[n] = min(inside, key=lambda b: b["bbox"][2] * b["bbox"][3])["id"]
    heads = {}
    for b in boxes:
        x, y, w, h = b["bbox"]
        cands = [s for s in sheet["shapes"] if s["text"] and s["id"] not in nodes and s["id"] not in used
                 and x <= s["bbox"][0] + s["bbox"][2] / 2 <= x + w and abs(s["bbox"][1] + s["bbox"][3] - y) <= HEAD_LIMIT + s["bbox"][3]
                 and s["bbox"][1] < y + HEAD_LIMIT and s["bbox"][1] + s["bbox"][3] > y - HEAD_LIMIT]
        if len(cands) == 1: heads[b["id"]] = cands[0]; used.add(cands[0]["id"])
        elif len(cands) > 1: notes.append(f"【要確認: 囲み s{b['id']} の見出しの候補が複数ある】")
    def text(s): return s["text"].replace('"', "#quot;").replace("\n", "<br>")
    def node(n):
        s = shapes[n]
        return f's{n}((" "))' if not s["text"] and s["kind"] == "ellipse" else f's{n}["{text(s)}"]'
    out = ["flowchart LR"]
    for n in sorted(nodes, key=int):
        if n not in member: out.append("    " + node(n))
    for b in boxes:
        ms = [n for n in sorted(nodes, key=int) if member.get(n) == b["id"]]
        if not ms: continue
        title = text(heads[b["id"]]) if b["id"] in heads else " "
        out.append(f'    subgraph s{b["id"]}["{title}"]'); out += ["        " + node(n) for n in ms]; out.append("    end")
    for c in sheet["connectors"]:
        if c["id"] not in ends: continue
        a, b, both = ends[c["id"]]
        items = by_line.get(c["id"], [])
        lab = f'|"{text(items[0][1])}"|' if len(items) == 1 else ""
        out.append(f"    s{a} {'<-->' if both and c['arrow_start'] else '---' if both else '-->'}{lab} s{b}")
        arrows.append((f"s{a}", f"s{b}", text(items[0][1]) if len(items) == 1 else ""))
    rest = [s for s in sheet["shapes"] if s["text"] and s["id"] not in nodes and s["id"] not in used]
    return "\n".join(out), arrows, {f"s{n}": f"s{m}" for n, m in member.items()}, {f"s{b}": f"s{h['id']}" for b, h in heads.items()}, notes, rest

def reference(md, idx):
    m = re.search(r'<!-- figure:begin id="fig-s%d".*?<!-- figure:end -->' % idx, md, re.S)
    mer = "".join(re.findall(r"```mermaid\n(.*?)```", m.group(0), re.S))
    arrows = re.findall(r'(s\d+) -->\|"([^"]*)"\| (s\d+)', mer)
    member, cur = {}, None
    for line in mer.splitlines():
        g = re.match(r'\s*subgraph (s\d+)\["([^"]*)"\]', line)
        if g: cur = g.group(1); continue
        if line.strip() == "end": cur = None; continue
        n = re.match(r"\s*(s\d+)[\[(]", line)
        if n and cur: member[n.group(1)] = cur
    heads = dict(re.findall(r'subgraph (s\d+)\["([^"]*)"\]', mer))
    return [(a, b, l) for a, l, b in arrows], member, heads, m.group(0)

if __name__ == "__main__":
    folder = sys.argv[1]
    e = json.load(open(f"{folder}/extract.json", encoding="utf-8")); md = open(f"{folder}/document.md", encoding="utf-8").read()
    for sheet in e["sheets"]:
        if not sheet["connectors"]: continue
        mer, arrows, member, heads, notes, rest = build(sheet)
        ref_arrows, ref_member, ref_heads, _ = reference(md, sheet["index"])
        shapes = {"s"+s["id"]: s for s in sheet["shapes"]}
        got_heads = {b: shapes[h]["text"].replace("\n", "<br>") for b, h in heads.items()}
        print(f"=== fig-s{sheet['index']}  原本の線 {len(sheet['connectors'])}")
        print("矢印（始点、終点、ラベル）: 試作", len(arrows), "/ 承認待ちの書き起こし", len(ref_arrows))
        print("  一致", len(set(arrows) & set(ref_arrows)), " 試作だけ", sorted(set(arrows) - set(ref_arrows)), " 書き起こしだけ", sorted(set(ref_arrows) - set(arrows)))
        print("囲みの中身: 一致" if member == ref_member else f"囲みの中身: 不一致 {set(member.items()) ^ set(ref_member.items())}")
        print("囲みの見出し: 一致" if got_heads == ref_heads else f"囲みの見出し: 不一致 試作={got_heads} 書き起こし={ref_heads}")
        for n in notes: print("  ", n)
        print("  つながりのない、文字のある図形:", len(rest))
        if "-v" in sys.argv: print(mer)
