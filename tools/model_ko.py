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


GPT = os.path.join(ROOT, 'work', 'GPT', '모델')      # tools/gpt_import.py 가 넣는 GPT 글자 마스크(M1.png·M2.png)


def gpt_masks(name, text):
    """GPT 글자 마스크를 글자별로 나눈다. 없으면 None.
    글자 안에도 빈 세로줄이 있어서(게 = ㄱ|ㅔ) 가장 넓은 틈으로 자르면 틀린다 → 같은 문구를 글꼴로 그렸을 때의
    글자 경계 위치(잉크 폭 비율)를 기준으로, 그 위치에 가장 가까운 빈 세로줄 틈에서 자른다."""
    p = os.path.join(GPT, name + '.png')
    if not os.path.exists(p):
        return None
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    chars = text.replace(' ', ''); n = len(chars)
    a = np.asarray(Image.open(p).convert('L')) >= 128
    xs = np.where(a.any(0))[0]; a = a[:, xs.min():xs.max() + 1]
    if n == 1:
        return [a]
    ft = ImageFont.truetype(FONT, 200); spans = []; x = 0
    for c in text:                                          # 글꼴 기준 글자별 잉크 구간
        l, _, r, _ = ft.getbbox(c)
        if c != ' ':
            spans.append((x + l, x + r))
        x += ft.getlength(c)
    s0, s1 = spans[0][0], spans[-1][1]
    expect = [((spans[i][1] + spans[i + 1][0]) / 2 - s0) / (s1 - s0) * a.shape[1] for i in range(n - 1)]
    col = a.any(0); gaps = []; x = 0
    while x < len(col):
        if not col[x]:
            g0 = x
            while x < len(col) and not col[x]:
                x += 1
            gaps.append((g0 + x) / 2)
        else:
            x += 1
    if len(gaps) < n - 1 and text.endswith('?'):                 # 「？」 없이 「끝」만 그려 온 경우
        return gpt_masks(name, text[:-1])
    assert len(gaps) >= n - 1, '%s: 글자 %d개로 나눌 틈이 부족함(글자끼리 붙어 있음)' % (name, n)
    cuts = []
    for e in expect:
        g = min((g for g in gaps if not cuts or g > cuts[-1]), key=lambda g: abs(g - e))
        cuts.append(g)
    edges = [0] + [int(c) for c in cuts] + [a.shape[1]]
    print('GPT 글자 마스크', name, text, [edges[i + 1] - edges[i] for i in range(n)])
    return [a[:, edges[i]:edges[i + 1]] for i in range(n)]


def place(ch, cx, cy, H, mask=None):
    """글자 ch 를 높이 H, 가운데 (cx,cy) 월드 좌표 삼각형으로(mask 가 있으면 GPT 글자 모양)."""
    tris, (h, w) = hsd.glyph_mesh(ch, FONT, mask=mask)
    s = H / h
    return [tuple((cx + (x - w / 2) * s, cy + (h / 2 - y) * s) for x, y in t) for t in tris], w * s


def x1():
    src = os.path.join(SRC, 'haraheri_endtxt.dat'); h = hsd.Hsd(src)
    S = sorted(slots(h), key=lambda s: (s[3][0] + s[3][2]) / 2)        # 왼→오: ゲ ー ム オ ー バ ー
    assert len(S) == 7
    y0 = min(s[3][1] for s in S); y1 = max(s[3][3] for s in S); cy = (y0 + y1) / 2; H = (y1 - y0) * 0.92
    x0 = min(s[3][0] for s in S); xe = max(s[3][2] for s in S)
    M = gpt_masks('M1', '게임 오버') or [None] * 4
    glyphs = [place(c, 0, cy, H, m) for c, m in zip('게임오버', M)]
    gap, space = H * 0.08, H * 0.45
    total = sum(w for _, w in glyphs) + gap * 2 + space
    x = (x0 + xe) / 2 - total / 2; rep = {}
    for k, (slot, c) in enumerate(zip([0, 2, 3, 5], '게임오버')):     # ゲ→게, ム→임, オ→오, バ→버 (각 글자 관절의 움직임 그대로)
        tris, w = place(c, x + glyphs[k][1] / 2, cy, H, M[k])
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
    m = (gpt_masks('M2', '끝?') or [None])[0]                         # GPT 그림에 「？」가 같이 있어도 「끝」만(？는 원본 모델)
    _, w = place('끝', 0, cy, H, m)
    kk, _ = place('끝', q[3][0] - H * 0.12 - w / 2, cy, H, m)            # 「？」 바로 왼쪽에
    out = os.path.join(OUT, 'dmy_endtxt.dat')
    print('X2', hsd.rebuild(src, out, {main[0]: kk}))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    x1(); x2()
