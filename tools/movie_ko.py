"""오프닝 영상(mov/opening.thp) 자막 한글화.

자막 카드마다 정지 프레임 R 에서 일본어를 지운 바탕(LaMa 4배) + 한글 = K 를 만들고,
프레임마다 원본 글자의 진하기 w(획과 바로 옆 바탕의 밝기 차 ÷ R 에서의 차)를 재서 F' = F + w·(K - R) (글자 상자 안만).
크로스페이드·다른 자막과의 겹침이 그대로 따라온다.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thp

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, 'extract', 'gift', 'mov', 'opening.thp')
OUT = os.path.join(ROOT, 'work', 'movie')
FONTS = os.path.join(ROOT, 'tools', 'fonts')
sys.path.insert(0, os.path.expandvars(r'%LOCALAPPDATA%\lama'))


def lines_of(ink):
    prof = ink.sum(1); out = []; on = False
    for y, v in enumerate(list(prof) + [0]):
        if v > 0 and not on:
            on = True; a = y
        if v == 0 and on:
            on = False
            if y - a > 3:
                xs = np.where(ink[a:y].any(0))[0]; out.append((a, y, int(xs.min()), int(xs.max()) + 1))
    return out


def clean_bg(R, ink, k=4):
    from lama_inpaint import inpaint
    m = ndimage.binary_dilation(ink, iterations=3)
    h, w = m.shape
    big = np.asarray(Image.fromarray(R.astype(np.uint8)).resize((w * k, h * k), Image.NEAREST))
    bm = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((w * k, h * k), Image.NEAREST))
    r = inpaint(big.copy(), bm)
    sm = np.asarray(Image.fromarray(r).resize((w, h), Image.BOX)).astype(int)
    out = R.copy(); out[m] = sm[m]
    return out, m


def render_line(txt, font, h, color=(20, 14, 10)):
    """글자 높이 h(한글 잉크 높이)로 그린 L 마스크(4배로 그려 줄임)."""
    ss = 4; size = h * ss
    for _ in range(4):
        f = ImageFont.truetype(font, size); l, t, r, b = f.getbbox('한글'); size = max(4, round(size * h * ss / (b - t)))
    f = ImageFont.truetype(font, size); l, t, r, b = f.getbbox(txt)
    im = Image.new('L', (r - l + 4 * ss, b - t + 4 * ss)); ImageDraw.Draw(im).text((-l + 2 * ss, -t + 2 * ss), txt, font=f, fill=255)
    return im.resize((im.width // ss, im.height // ss), Image.LANCZOS)


def split_lines(ink, n):
    """잉크를 n 줄로 나눈다: 기울기 θ 를 바꿔 가며 y' = y + x·tanθ 로 투영해, 빈 띠(n-1개)가 가장 넓게 생기는 θ 를 고른다.
    반환: [(줄 마스크, 각도(도, 오른쪽이 올라가면 +), (y0,y1,x0,x1))] 위→아래."""
    ys, xs = np.where(ink); best = None
    for a in np.linspace(-0.25, 0.25, 51):
        yp = ys + xs * np.tan(a); h = np.bincount((yp - yp.min()).astype(int))
        zero = h == 0
        gaps = []; g0 = None                                   # 빈 띠 (시작, 길이)
        for i, z in enumerate(zero):
            if z and g0 is None:
                g0 = i
            if not z and g0 is not None:
                gaps.append((i - g0, g0, i)); g0 = None
        if len(gaps) < n - 1:
            continue
        gaps.sort(reverse=True); score = gaps[n - 2][0] if n > 1 else 1
        if best is None or score > best[0]:
            best = (score, a, sorted(gaps[:n - 1], key=lambda g: g[1]), yp.min())
    _, a, gaps, ymin = best
    yp = ys + xs * np.tan(a) - ymin; cuts = [(g[1] + g[2]) / 2 for g in gaps]
    out = []
    for k in range(n):
        lo = cuts[k - 1] if k else -1e9; hi = cuts[k] if k < n - 1 else 1e9
        sel = (yp >= lo) & (yp < hi); m = np.zeros(ink.shape, bool); m[ys[sel], xs[sel]] = True
        yy, xx = ys[sel], xs[sel]
        A = np.polyfit(xx, yy, 1)[0] if xx.max() - xx.min() > 20 else 0.0      # 줄의 실제 기울기(잉크 회귀)
        out.append((m, float(-np.degrees(np.arctan(A))), (int(yy.min()), int(yy.max()) + 1, int(xx.min()), int(xx.max()) + 1)))
    return out


REFS = [360, 720, 870, 1505, 1866, 2226, 2585, 4070, 4185, 4780, 4890, 5070]   # 자막 카드별 정지 프레임
FONT = os.path.join(FONTS, 'AndongKaturi.ttf')


def line_angle(ink, y0, y1, x0, x1):
    """줄 기울기(도): 왼쪽 1/3·오른쪽 1/3 의 잉크 무게중심 높이 차."""
    sub = ink[y0:y1, x0:x1]; w = x1 - x0
    ys = []
    for a, b in ((0, w // 3), (w - w // 3, w)):
        yy, xx = np.where(sub[:, a:b])
        ys.append((yy.mean() if len(yy) else 0, (a + b) / 2))
    (ya, xa), (yb, xb) = ys
    return float(np.degrees(np.arctan2(ya - yb, xb - xa)))       # 오른쪽이 올라가면 +


def make_card(t, k, ko_lines):
    """k 번째 자막: (원본 R, 한글 카드 K, 일본어 잉크 마스크, 영향 상자) — 모두 float."""
    R = np.asarray(t.image(REFS[k])).astype(float)
    ink = R.sum(2) < 200
    L = split_lines(ink, len(ko_lines))
    bg, m = clean_bg(R.astype(int), ink)
    col = np.median(R[R.sum(2) < 120], 0)                          # 원본 먹색
    K = Image.fromarray(bg.astype(np.uint8)).convert('RGBA'); kmask = np.zeros(ink.shape, bool)
    hs = [(y1 - y0) - abs(np.tan(np.radians(ang))) * (x1 - x0) for lm, ang, (y0, y1, x0, x1) in L]
    H = min(int(max(hs) * 0.95), 31)                              # 한 자막 안에서는 글자 크기 통일(원본처럼), 기울기로 커진 줄 높이는 뺌, 11번 큰 「？」 때문에 상한 31
    for (lm, ang, (y0, y1, x0, x1)), txt in zip(L, ko_lines):
        g = render_line(txt, FONT, max(12, H))
        g = g.point(lambda v: int(255 * (v / 255) ** 0.6))           # 가장자리만 살짝 진하게(획 사이는 막지 않음)
        if abs(ang) > 0.8:
            g = g.rotate(ang, resample=Image.BICUBIC, expand=True)  # 줄 전체를 원본 각도로
        lay = Image.new('RGBA', g.size, tuple(int(c) for c in col) + (0,)); lay.putalpha(g)
        cy = (y0 + y1) / 2; px = x0 - 2
        if px + g.width > 500:
            px = 500 - g.width
        K.alpha_composite(lay, (px, round(cy - g.height / 2)))
        ga = np.zeros(ink.shape, bool); gy, gx = round(cy - g.height / 2), px
        sub = np.asarray(g) > 10; hh, ww = sub.shape
        ys, ye = max(gy, 0), min(gy + hh, ink.shape[0]); xs, xe = max(gx, 0), min(gx + ww, ink.shape[1])
        ga[ys:ye, xs:xe] = sub[ys - gy:ye - gy, xs - gx:xe - gx]; kmask |= ga
    K = np.asarray(K.convert('RGB')).astype(float)
    area = ndimage.binary_dilation(m | kmask, iterations=4)
    return R, K, ink, area


def weight(F, R, ink):
    """프레임 F 에서 원본 글자 진하기(정지 프레임 R 대비 0~1)."""
    core = ink & (R.sum(2) < 150)
    ring = ndimage.binary_dilation(ink, iterations=3) & ~ndimage.binary_dilation(ink, iterations=1)
    f = F.sum(2); r = R.sum(2)
    den = r[ring].mean() - r[core].mean()
    return float(np.clip((f[ring].mean() - f[core].mean()) / den, 0, 1.2))


def active_weights(k):
    """카드 k 의 프레임별 진하기: 3프레임 중앙값으로 튀는 값 제거 → 정지 프레임을 포함한 연속 구간(w>0.04)만 남김."""
    import json
    ws = {int(a): b for a, b in json.load(open(os.path.join(OUT, 'card%02d_w.json' % (k + 1)))).items()}
    xs = sorted(ws); v = np.array([ws[i] for i in xs])
    v = ndimage.median_filter(v, size=3, mode='nearest')
    r = xs.index(REFS[k]); a = r; b = r
    while a > 0 and v[a - 1] > 0.04:
        a -= 1
    while b < len(v) - 1 and v[b + 1] > 0.04:
        b += 1
    return {xs[i]: float(min(v[i], 1.0)) for i in range(a, b + 1)}


def apply(F, card, w):
    R, K, area = card['R'], card['K'], card['area']
    out = F.astype(float).copy()
    out[area] += w * (K[area] - R[area])
    return np.clip(out, 0, 255)


def build(out=os.path.join(OUT, 'opening.thp')):
    """확정한 자막 12장을 모두 적용해 THP 를 다시 만든다. 자막이 걸친 프레임만 다시 압축(원본 영상 크기 이하·프레임 한도 이하가 되게 품질 조정)."""
    import json
    t = thp.Thp(SRC)
    C = [dict(np.load(os.path.join(OUT, 'card%02d.npz' % (k + 1)))) for k in range(12)]
    Ws = [active_weights(k) for k in range(12)]
    frames = sorted(set(i for W in Ws for i in W))
    rep = {}; qs = []; log = []
    for i in frames:
        F = np.asarray(t.image(i)).astype(float)
        for c, W in zip(C, Ws):
            if i in W:
                F = apply(F, c, W[i])
        o, sz, vs, aus = t.frames[i]
        limit = min(int(vs * 1.10), t.maxbuf - 16 - aus - 31)          # 원본 영상 크기의 110% 와 프레임 한도 안
        j, q = thp.encode(Image.fromarray(F.round().astype(np.uint8)), limit)
        rep[i] = j; qs.append(q); log.append((i, vs, len(j), q))
    maxbuf = thp.rebuild(t, out, rep)
    json.dump({'frames': len(frames), 'range': [frames[0], frames[-1]], 'maxbuf': maxbuf, 'orig_maxbuf': t.maxbuf,
               'q_min': min(qs), 'q_max': max(qs), 'log': log}, open(os.path.join(OUT, 'build_log.json'), 'w'))
    return len(frames), maxbuf, min(qs), max(qs)


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'build':
    print(build())
