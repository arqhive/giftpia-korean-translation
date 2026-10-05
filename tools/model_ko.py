"""3D 글자 모델 한글화(X1 「ゲームオーバー」→「게임 오버」, X2 「おわり？」→「끝?」). 엄마까투리체 글자를 사다리꼴 삼각형으로 만들어 교체.

  python tools/model_ko.py      → work/model/*.dat + 미리보기 png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hsd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, 'extract', 'dat', 'map', 'worldmap')
OUT = os.path.join(ROOT, 'work', 'model')
FONT = os.path.join(ROOT, 'tools', 'fonts', 'AndongKaturi.ttf')


def slots(h):
    """[(PObj, (sc,tr), 월드 삼각형, 상자)] — 표시 객체가 있는 JObj 마다."""
    out = []
    for depth, j in h.jobjs():
        fl, rot, sc, tr, dob = h.jobj_info(j)
        if not dob:
            continue
        for D in h.dobjs(dob):
            for p in h.pobjs(h.u32(D + 0x0C)):
                vd = h.vtxdesc(p); tris = []
                for op, vs in h.dlist(p):
                    P = [h.read_pos(vd[0], v[0]) for v in vs]
                    P = [(x * sc[0] + tr[0], y * sc[1] + tr[1]) for x, y, *_ in P]
                    if op == 0x90:                                   # 삼각형 목록(새로 만든 글자)
                        tris += [tuple(P[i:i + 3]) for i in range(0, len(P) - 2, 3)]
                    else:                                            # 삼각형 띠(원본)
                        tris += [(P[i], P[i + 1], P[i + 2]) for i in range(len(P) - 2)]
                xs = [q[0] for t in tris for q in t]; ys = [q[1] for t in tris for q in t]
                out.append((p, j, tris, (min(xs), min(ys), max(xs), max(ys)), sum(len(v) for _, v in h.dlist(p))))
    return out


def place(ch, cx, cy, H):
    """글자 ch 를 높이 H, 가운데 (cx,cy) 월드 좌표 삼각형으로."""
    tris, (h, w) = hsd.glyph_mesh(ch, FONT)
    s = H / h
    return [tuple((cx + (x - w / 2) * s, cy + (h / 2 - y) * s) for x, y in t) for t in tris], w * s


def x1():
    src = os.path.join(SRC, 'haraheri_endtxt.dat'); h = hsd.Hsd(src)
    S = sorted(slots(h), key=lambda s: (s[3][0] + s[3][2]) / 2)        # 왼→오: ゲ ー ム オ ー バ ー
    assert len(S) == 7
    y0 = min(s[3][1] for s in S); y1 = max(s[3][3] for s in S); cy = (y0 + y1) / 2; H = (y1 - y0) * 0.92
    x0 = min(s[3][0] for s in S); xe = max(s[3][2] for s in S)
    glyphs = [place(c, 0, cy, H) for c in '게임오버']
    gap, space = H * 0.08, H * 0.45
    total = sum(w for _, w in glyphs) + gap * 2 + space
    x = (x0 + xe) / 2 - total / 2; rep = {}
    for k, (slot, c) in enumerate(zip([0, 2, 3, 5], '게임오버')):     # ゲ→게, ム→임, オ→오, バ→버 (각 글자 관절의 움직임 그대로)
        tris, w = place(c, x + glyphs[k][1] / 2, cy, H)
        rep[S[slot][0]] = tris
        x += w + (space if k == 1 else gap)
    empty = [S[i][0] for i in (1, 4, 6)]                                # ー 세 칸은 비움
    out = os.path.join(OUT, 'haraheri_endtxt.dat')
    print('X1', hsd.rebuild(src, out, rep, empty))


def x2():
    src = os.path.join(SRC, 'dmy_endtxt.dat'); h = hsd.Hsd(src)
    S = [s for s in slots(h) if s[4] > 10]                              # 판 2장(꼭짓점 4개)은 그대로
    S.sort(key=lambda s: s[3][0]); main, q = S[0], S[1]                 # おわり, ？(「？」는 원본 그대로 둠)
    y0, y1 = main[3][1], main[3][3]; cy = (y0 + y1) / 2; H = (y1 - y0) * 0.92
    _, w = place('끝', 0, cy, H)
    kk, _ = place('끝', q[3][0] - H * 0.12 - w / 2, cy, H)            # 「？」 바로 왼쪽에
    out = os.path.join(OUT, 'dmy_endtxt.dat')
    print('X2', hsd.rebuild(src, out, {main[0]: kk}))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    x1(); x2()
