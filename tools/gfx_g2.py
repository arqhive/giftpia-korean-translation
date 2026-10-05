"""6단계 둘째 묶음(간판·현수막·표지) 지우기·한글 배치.

  python tools/gfx_g2.py preview [번호 ...]   → work/gfx/g2/ 에 결과 PNG + 비교 시트

항목마다 SPEC 에 적는다.
- erase: 'paint'  — 밝기 cut 미만을 글자로 보고(1px 넓힌 칸은 grow 미만), 주변 바탕에서 사방으로 번지게 채운다(가로·세로 음영 판)
         'solid'  — 글자 칸(box) 전체를 가장 흔한 바탕색 하나로 칠한다(무늬 없는 판)
         'rows'   — 글자 픽셀만 골라, 같은 줄의 좌우 바탕색을 직선 보간해 채운다(나뭇결·음영 판)
- box: 지우는 범위(x0, y0, x1, y1), 끝 미포함
- dark: 글자로 볼 밝기 차(줄 바탕보다 이만큼 어두우면 글자)
- text / vertical / font / place: 넣을 한글, 세로쓰기, 글꼴, 배치 범위(원본 글자 잉크 상자에 맞춤)
"""
import csv
import os
import sys
from collections import Counter
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfx_g1 import ROOT, G, FONTS, lum, render_text, ink_box, scale, label, grid  # 첫 묶음 도구 재사용

OUT = os.path.join(ROOT, 'work', 'gfx', 'g2')

SPEC = {
    '2138': dict(text='순찰 중', font='BlackHanSans-Regular.ttf', erase='solid', box=(5, 5, 59, 27)),
    '2155': dict(text='시마우라 입구', font='DoHyeon-Regular.ttf', erase='rows', box=(2, 8, 61, 22), dark=20, inner=(4, 59), margin=3),
    '590': dict(text='입고 대기', font='AndongKaturi.ttf', erase='paint', box=(3, 7, 31, 24), cut=220, grow=232),
    '1569': dict(text='금연', font='BlackHanSans-Regular.ttf', erase='paint', box=(5, 2, 27, 30), cut=150, grow=215, red=30, vertical=True),
    '2043': dict(text='메트', font='AndongKaturi.ttf', erase='paint', box=(5, 8, 30, 92), cut=120, grow=197, grow2=2, vertical=True, vgap=3),
    '2061': dict(text='물 긷는 곳', font='BlackHanSans-Regular.ttf', erase='paint', box=(3, 7, 29, 97), cut=182, grow=205, vertical=True),
}


def rows():
    return {r['n']: r for r in csv.DictReader(open(os.path.join(ROOT, 'translation', 'graphics_list.csv'), encoding='utf-8-sig'))}


def erase(src, sp):
    im = src.copy(); px = im.load()
    x0, y0, x1, y1 = sp['box']
    # 글자 픽셀: 줄 바탕(그 줄 상자 안 밝기의 상위 1/4 지점)보다 dark 이상 어두운 것 / paint 는 고정 밝기 cut 미만
    mask = Image.new('L', im.size, 0); mp = mask.load()
    for y in range(y0, y1):
        ls = sorted(lum(px[x, y]) for x in range(x0, x1))
        bg = ls[len(ls) * 3 // 4]
        for x in range(x0, x1):
            c = px[x, y]
            if 'red' in sp:                                  # 빨간 글자: 빨강이 초록보다 red 이상 큰 픽셀(분홍 번짐 포함)
                hit = c[0] - c[1] > sp['red']
            elif sp['erase'] == 'paint':
                hit = lum(c) < sp['cut']
            else:
                hit = lum(c) < bg - sp.get('dark', 25)
            if hit:
                mp[x, y] = 255
    ink = mask.getbbox()
    # 글자색: 가장 어두운 쪽 픽셀들의 최빈색
    dk = sorted(((lum(px[x, y]), px[x, y]) for y in range(y0, y1) for x in range(x0, x1) if mp[x, y]), key=lambda t: t[0])
    color = Counter(c for _, c in dk[:max(1, len(dk) // 3)]).most_common(1)[0][0][:3]
    n = 0
    if sp['erase'] == 'solid':
        fill = Counter(px[x, y] for y in range(y0, y1) for x in range(x0, x1) if not mp[x, y]).most_common(1)[0][0]
        for y in range(y0, y1):
            for x in range(x0, x1):
                if px[x, y] != fill:
                    px[x, y] = fill; n += 1
    elif sp['erase'] == 'paint':
        import numpy as np
        grow = mask.filter(ImageFilter.MaxFilter(3)).load()
        for y in range(y0, y1):
            for x in range(x0, x1):
                if grow[x, y] and ((px[x, y][0] - px[x, y][1] > sp['red'] // 3) if 'red' in sp else lum(px[x, y]) < sp['grow']):
                    mp[x, y] = 255
        if sp.get('grow2'):                              # 글자 주변 압축 얼룩까지: 색 조건 없이 n칸 더 넓혀 매끈하게 다시 채운다
            g2 = mask
            for _ in range(sp['grow2']):
                g2 = g2.filter(ImageFilter.MaxFilter(3))
            g2p = g2.load()
            for y in range(y0, y1):
                for x in range(x0, x1):
                    if g2p[x, y]:
                        mp[x, y] = 255
        a = np.asarray(src, dtype=np.float64).copy(); m = np.asarray(mask) > 0
        # 시작값: 같은 줄 좌우 바탕 직선 보간, 그 뒤 4방향 평균을 반복(라플라스 채움) → 가로·세로 음영이 이어진다
        for y in range(y0, y1):
            xs = np.where(~m[y, x0:x1])[0] + x0
            if len(xs):
                for k in range(4):
                    a[y, x0:x1, k] = np.where(m[y, x0:x1], np.interp(np.arange(x0, x1), xs, a[y, xs, k]), a[y, x0:x1, k])
        for _ in range(800):
            nb = (np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 4
            a[m] = nb[m]
        out = np.clip(np.round(a), 0, 255).astype(np.uint8)
        n = int(m.sum())
        im = Image.fromarray(out, 'RGBA')
    else:
        # 글자 가장자리 번짐까지 1px 넓혀서 지운다(넓힌 칸은 줄 바탕보다 조금이라도 어두운 것만)
        grow = mask.filter(ImageFilter.MaxFilter(3)).load()
        for y in range(y0, y1):
            ls = sorted(lum(px[x, y]) for x in range(x0, x1))
            bg = ls[len(ls) * 3 // 4]
            for x in range(x0, x1):
                if grow[x, y] and lum(px[x, y]) < bg - 6:
                    mp[x, y] = 255
        orig = src.load()
        for y in range(y0, y1):
            xs = [x for x in range(x0, x1) if mp[x, y]]
            for x in xs:
                lo, hi = sp.get('inner', (x0 - 1, x1))         # 보간 끝점은 판 안쪽(가장자리 짙은 띠 제외)에서만 고른다
                l = next((i for i in range(x - 1, lo - 1, -1) if i >= 0 and not mp[i, y]), None)
                r = next((i for i in range(x + 1, hi + 1) if i < im.width and not mp[i, y]), None)
                if l is None and r is None:
                    continue
                if l is None: c = orig[r, y]
                elif r is None: c = orig[l, y]
                else:
                    t = (x - l) / (r - l)
                    c = tuple(round(orig[l, y][k] * (1 - t) + orig[r, y][k] * t) for k in range(4))
                px[x, y] = c; n += 1
    return im, n, ink, color


def fit(t, maxw, maxh, squeeze=0.85):
    if t.width > maxw:                                  # 가로 압축(기본 최대 85%), 그래도 넘치면 축소
        t = t.resize((max(maxw, round(t.width * squeeze)), t.height), Image.LANCZOS)
        if t.width > maxw:
            t = t.resize((maxw, max(1, round(t.height * maxw / t.width))), Image.LANCZOS)
    if t.height > maxh:
        t = t.resize((max(1, round(t.width * maxh / t.height)), maxh), Image.LANCZOS)
    return t


def place(clean, sp, ink, color):
    im = clean.copy()
    font = os.path.join(FONTS, sp['font'])
    ix0, iy0, ix1, iy1 = ink
    iw, ih = ix1 - ix0, iy1 - iy0
    if not sp.get('vertical'):
        mg = sp.get('margin', 0)                         # 판 가장자리와 띄울 여백(좌우)
        ix0, ix1 = ix0 + mg, ix1 - mg; iw = ix1 - ix0
        t = render_text(sp['text'], font, ih, color)
        t = fit(t.crop(ink_box(t)), iw, ih)
        im.alpha_composite(t, (ix0 + (iw - t.width) // 2, round((iy0 + iy1) / 2 - t.height / 2)))
        return im
    # 세로: 음절마다 따로 그려 가운데 세로줄에 맞추고, 원본 잉크 위·아래 끝 사이에 같은 간격으로(띄어쓰기는 간격 두 배)
    if sp.get('cells'):                                  # 원본처럼 한 글자씩 같은 칸: 잉크 범위를 글자 수만큼 등분, 글자마다 같은 높이로
        chars = sp['text'].replace(' ', ''); k = len(chars); gap = sp.get('cgap', 2)
        ch_h = (ih - gap * (k - 1)) / k; cx = (ix0 + ix1) / 2
        for j, ch in enumerate(chars):
            g = render_text(ch, font, iw, color); g = g.crop(ink_box(g))
            h = round(ch_h); w = min(round(iw * sp.get('vw', 1.0)), round(g.width * h / g.height))
            g = g.resize((w, h), Image.LANCZOS)
            im.alpha_composite(g, (round(cx - w / 2), round(iy0 + j * (ch_h + gap))))
        return im
    words = sp['text'].split(' ')
    cells, gaps_after = [], []
    for wi, w in enumerate(words):
        for ci, ch in enumerate(w):
            g = render_text(ch, font, round(iw * sp.get('vw', 1.0)), color); g = g.crop(ink_box(g))
            cells.append(g); gaps_after.append(2 if ci == len(w) - 1 and wi < len(words) - 1 else 1)
    gaps_after[-1] = 0
    units = sum(gaps_after)
    total = sum(c.height for c in cells)
    if total > ih - units * 2:                           # 칸에 넘치면 전체 축소
        k = (ih - units * 2) / total
        cells = [c.resize((max(1, round(c.width * k)), max(1, round(c.height * k))), Image.LANCZOS) for c in cells]
        total = sum(c.height for c in cells)
    gap = (ih - total) / units if units else 0
    y = iy0; cx = (ix0 + ix1) / 2
    if 'vgap' in sp:                                     # 글자 사이를 고정 간격으로 붙이고, 원본 잉크 세로 가운데에 맞춘다
        gap = sp['vgap']; y = (iy0 + iy1) / 2 - (total + gap * units) / 2
    for c, gu in zip(cells, gaps_after):
        im.alpha_composite(c, (round(cx - c.width / 2), round(y)))
        y += c.height + gap * gu
    return im


def changed_outside(src, out, box):
    a, b = src.load(), out.load(); x0, y0, x1, y1 = box
    return sum(1 for y in range(src.height) for x in range(src.width)
               if a[x, y] != b[x, y] and not (x0 <= x < x1 and y0 <= y < y1))


def preview(ids):
    R = rows(); os.makedirs(OUT, exist_ok=True); cells = []
    for i in ids:
        sp = SPEC[i]
        src = Image.open(os.path.join(G, R[i]['png'])).convert('RGBA')
        clean, n, ink, color = erase(src, sp)
        out = place(clean, sp, ink, color)
        clean.save(os.path.join(OUT, '%s_clean.png' % i)); out.save(os.path.join(OUT, '%s_ko.png' % i))
        bad = changed_outside(src, out, sp['box'])
        k = max(2, min(8, 384 // max(src.size)))
        cells += [label(scale(src, k), '#%s 원본' % i), label(scale(clean, k), '지운 뒤 (%d px)' % n),
                  label(scale(out, k), '한글: %s · 칸 밖 변경 %d' % (sp['text'], bad))]
        print(i, '지운 픽셀', n, '원본 잉크', ink, '글자색', color, '칸 밖 변경', bad)
    for j, i in enumerate(ids):
        grid(cells[j * 3:j * 3 + 3], 3).save(os.path.join(OUT, 'sheet_%s.png' % i))





# ── 개별 처리(규칙으로 묶기 어려운 디자인) ──
def _gold(text, font, h, outline=(69, 20, 49), top=(255, 236, 110), bottom=(236, 150, 24), stroke=2):
    """금색 세로 그러데이션 글자 + 테두리(#156 문장)."""
    o = render_text(text, font, h, outline, stroke=stroke)
    m = render_text(text, font, h, (255, 255, 255))
    grad = Image.new('RGBA', m.size)
    gp = grad.load()
    for y in range(m.height):
        t = y / max(1, m.height - 1)
        c = tuple(round(top[k] * (1 - t) + bottom[k] * t) for k in range(3)) + (255,)
        for x in range(m.width):
            gp[x, y] = c
    grad.putalpha(m.getchannel('A'))
    o.alpha_composite(grad, ((o.width - m.width) // 2, (o.height - m.height) // 2))
    return o.crop(ink_box(o, 10))


def custom_156(src):
    """村 문장: 고리 안쪽 원(반지름 약 24)을 바탕 자주색으로 칠하고 「마을」을 금색으로."""
    im = src.copy(); px = im.load(); n = 0
    fill = (69, 20, 49, 255); cx, cy = 31.5, 31.5
    for y in range(64):
        for x in range(64):
            r2 = (x - cx) ** 2 + (y - cy) ** 2
            c = px[x, y]
            goldish = c[0] > 90 and c[0] > c[2] + 40 and c[1] > 40          # 금색·주황 번짐(고리는 회보라라 해당 없음)
            if (r2 <= 24.5 ** 2 or (r2 <= 27.5 ** 2 and goldish)) and c != fill:
                px[x, y] = fill; n += 1
    clean = im.copy()
    t = _gold('마을', os.path.join(FONTS, 'BlackHanSans-Regular.ttf'), 21)
    t = fit(t, 42, 26)
    im.alpha_composite(t, (round(cx - t.width / 2 + 0.5), round(cy - t.height / 2 + 0.5)))
    return clean, im, n, (3, 3, 61, 61)


def custom_1686(src):
    """구름 간판: 노란 글자와 짙은 초록 테두리만 흰색으로 지우고, 두 줄 한글을 같은 색·테두리로."""
    im = src.copy(); px = im.load(); w, h = im.size
    # 구름 바깥(투명)에서 시작해 투명·민트 테두리 픽셀로만 퍼져 나가고, 닿지 않은 안쪽 전부를 흰색으로 칠한다
    edge = lambda c: c[3] < 128 or (c[1] > 200 and c[2] > 140 and c[0] < 230 and c[:3] != (255, 255, 255))
    seen = set((x, y) for x in range(w) for y in (0, h - 1)) | set((x, y) for y in range(h) for x in (0, w - 1))
    stack = [p for p in seen if edge(px[p])]; seen = set(stack)
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and edge(px[nx, ny]):
                seen.add((nx, ny)); stack.append((nx, ny))
    # 원본 테두리: 바깥에서 1~2칸 민트(95,255,166), 3칸째 옅은 민트(205,255,227). 글자 테두리가 구름 끝에 닿아
    # 민트가 없던 곳은 지운 뒤 같은 규칙으로 테두리를 되살린다(지우는 픽셀에만 적용)
    shape = Image.new('L', (w, h), 0); sp_ = shape.load()
    for y in range(h):
        for x in range(w):
            if px[x, y][3] >= 128:
                sp_[x, y] = 255
    e1 = shape.filter(ImageFilter.MinFilter(3)); e2 = e1.filter(ImageFilter.MinFilter(3)); e3 = e2.filter(ImageFilter.MinFilter(3))
    e1, e2, e3 = e1.load(), e2.load(), e3.load()
    white = (255, 255, 255, 255); n = 0
    for y in range(h):
        for x in range(w):
            if (x, y) not in seen:
                c = (95, 255, 166, 255) if not e2[x, y] else ((205, 255, 227, 255) if not e3[x, y] else white)
                if px[x, y] != c:
                    px[x, y] = c; n += 1
    clean = im.copy()
    font = os.path.join(FONTS, 'AndongKaturi.ttf'); fillc, edge = (255, 232, 31), (0, 160, 30)   # 엄마까투리체(사용자 지정)
    # 원본 두 줄(테두리 포함) 잉크 범위: 1줄 y13~27·x28~98, 2줄 y31~45·x4~117
    # → 줄마다 윗끝을 원본과 같게, 높이도 같게(15px), 가로는 원본 줄 가운데에 맞춘다(폭은 원본 줄 폭 이내)
    for line, (y0, y1), (x0, x1) in [('어서 오이소', (13, 28), (28, 99)), ('텐진 랜드로', (31, 46), (4, 118))]:
        t = crisp_outline(line, font, y1 - y0 - 2, fillc, edge, stroke=1, aa=True)   # 원본 초록 테두리 약 1px
        if t.height != y1 - y0:
            t = t.resize((round(t.width * (y1 - y0) / t.height), y1 - y0), Image.NEAREST)
        t = fit(t, x1 - x0, y1 - y0)
        im.alpha_composite(t, (round((x0 + x1) / 2 - t.width / 2), y0 + 2))   # 사용자 지시: 원본보다 2px 아래
    return clean, im, n, (0, 0, 128, 64)


def fill_small_holes(g, color, maxarea=12, thr=128):
    """글자 안에 갇힌 작은 빈칸(테두리를 그려도 메워지지 않는 획 사이 틈)을 테두리색으로 메운다."""
    w, h = g.size; px = g.load(); seen = set()
    for sy in range(h):
        for sx in range(w):
            if (sx, sy) in seen or px[sx, sy][3] >= thr:
                continue
            comp, stack, edge = [], [(sx, sy)], False; seen.add((sx, sy))
            while stack:
                x, y = stack.pop(); comp.append((x, y))
                if x in (0, w - 1) or y in (0, h - 1):
                    edge = True
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and px[nx, ny][3] < thr:
                        seen.add((nx, ny)); stack.append((nx, ny))
            if not edge and len(comp) <= maxarea:
                for x, y in comp:
                    px[x, y] = color + (255,)
    return g


def crisp_outline(text, font, h, fillc, edgec, stroke=2, aa=False):
    """도트 그림처럼 또렷한 테두리: 최종 크기에서 글자 모양(알파≥128)을 잡고, stroke 칸만큼 넓힌 부분을 테두리색으로 칠한다.
    획 사이 틈이 좁아도 테두리가 끊기거나 분홍빛으로 번지지 않는다."""
    g = render_text(text, font, h, fillc)
    pad = stroke + 1
    m = Image.new('L', (g.width + pad * 2, g.height + pad * 2), 0)
    m.paste(g.getchannel('A').point(lambda v: 255 if v >= (80 if aa else 128) else 0), (pad, pad))
    # 안쪽 틈(획 사이·받침 안)은 1칸 테두리만, 글자 바깥쪽 둘레만 stroke 칸으로 두껍게 → 작은 크기에서도 획이 뭉개지지 않는다
    d1 = m.filter(ImageFilter.MaxFilter(3))
    o = d1
    if stroke > 1:
        w, h = m.size; mp = m.load(); outside = Image.new('L', m.size, 0); op = outside.load()
        stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
        for x, y in stack: op[x, y] = 255
        while stack:
            x, y = stack.pop()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and not op[nx, ny] and not mp[nx, ny]:
                    op[nx, ny] = 255; stack.append((nx, ny))
        # 바깥 영역 = 테두리 밖에서 이어진 빈칸 중, 1칸 테두리를 지나서도 바깥과 이어진 곳
        dk = m
        for _ in range(stroke):
            dk = dk.filter(ImageFilter.MaxFilter(3))
        out1 = Image.new('L', m.size, 0); o1 = out1.load(); d1p = d1.load()
        stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
        for x, y in stack: o1[x, y] = 255
        while stack:
            x, y = stack.pop()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and not o1[nx, ny] and not d1p[nx, ny]:
                    o1[nx, ny] = 255; stack.append((nx, ny))
        # 두꺼운 테두리는 바깥쪽에서 이어진 빈칸(out1)에 닿는 부분에만 더한다
        near = out1.filter(ImageFilter.MaxFilter(3))
        from PIL import ImageChops
        o = ImageChops.lighter(d1, ImageChops.multiply(dk, ImageChops.multiply(near, out1.point(lambda v: 255))))
    out = Image.new('RGBA', m.size, (0, 0, 0, 0))
    out.paste(Image.new('RGBA', m.size, edgec + (255,)), (0, 0), o)
    if aa:                                                # 글자 속은 부드럽게(둥근 획 유지), 테두리만 또렷하게
        soft = Image.new('L', m.size, 0); soft.paste(g.getchannel('A'), (pad, pad))
        out.paste(Image.new('RGBA', m.size, fillc + (255,)), (0, 0), soft)
    else:
        out.paste(Image.new('RGBA', m.size, fillc + (255,)), (0, 0), m)
    return out.crop(out.getbbox())


def custom_569(src):
    """복권 간판: 그림 전체가 흰 바탕 + 글자라 전부 흰색으로 칠하고, 「복」 크게·「권」 조금 작고 낮게(원본 宝·くじ 배치)."""
    im = Image.new('RGBA', src.size, (255, 255, 255, 255))
    n = sum(1 for y in range(src.height) for x in range(src.width) if src.getpixel((x, y)) != (255, 255, 255, 255))
    clean = im.copy()
    font = os.path.join(FONTS, 'Jua.ttf'); red, edge = (240, 0, 0), (60, 0, 4)   # 블랙한산스는 이 크기에서 획이 뭉쳐 주아로
    a = crisp_outline('복', font, 32, red, edge)
    b = crisp_outline('권', font, 25, red, edge)
    im.alpha_composite(a, (1, 1)); im.alpha_composite(b, (min(64 - b.width - 1, 1 + a.width + 1), 48 - b.height - 1))
    return clean, im, n, (0, 0, 64, 48)


CUSTOM = {'156': ('마을', custom_156), '1686': ('어서 오이소 / 텐진 랜드로', custom_1686), '569': ('복권', custom_569)}


def preview_custom(ids):
    R = rows(); os.makedirs(OUT, exist_ok=True)
    for i in ids:
        text, fn = CUSTOM[i]
        src = Image.open(os.path.join(G, R[i]['png'])).convert('RGBA')
        clean, out, n, box = fn(src)
        clean.save(os.path.join(OUT, '%s_clean.png' % i)); out.save(os.path.join(OUT, '%s_ko.png' % i))
        bad = changed_outside(src, out, box)
        k = max(2, min(8, 384 // max(src.size)))
        grid([label(scale(src, k), '#%s 원본' % i), label(scale(clean, k), '지운 뒤 (%d px)' % n),
              label(scale(out, k), '한글: %s · 칸 밖 변경 %d' % (text, bad))], 3).save(os.path.join(OUT, 'sheet_%s.png' % i))
        print(i, '지운 픽셀', n, '칸 밖 변경', bad)


def inpaint(src, box, is_text, grow_ok, iters=800):
    """box 안에서 is_text 픽셀(+1px 넓힌 칸 중 grow_ok)을 주변 바탕이 사방으로 번지게(라플라스) 채운다."""
    import numpy as np
    x0, y0, x1, y1 = box; px = src.load()
    mask = Image.new('L', src.size, 0); mp = mask.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            if is_text(px[x, y]):
                mp[x, y] = 255
    ink = mask.getbbox()
    grow = mask.filter(ImageFilter.MaxFilter(3)).load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            if grow[x, y] and grow_ok(px[x, y]):
                mp[x, y] = 255
    a = np.asarray(src, dtype=np.float64).copy(); m = np.asarray(mask) > 0
    for y in range(y0, y1):
        xs = np.where(~m[y, x0:x1])[0] + x0
        if len(xs):
            for k in range(4):
                a[y, x0:x1, k] = np.where(m[y, x0:x1], np.interp(np.arange(x0, x1), xs, a[y, xs, k]), a[y, x0:x1, k])
    for _ in range(iters):
        nb = (np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 4
        a[m] = nb[m]
    return Image.fromarray(np.clip(np.round(a), 0, 255).astype(np.uint8), 'RGBA').copy(), int(m.sum()), ink


def put(im, text, font, color, ink, valign='center', squeeze=0.85):
    """원본 잉크 상자(ink) 안에 한글을 맞춰 넣는다(높이 = 상자 높이, 넘치면 가로 압축·축소, 가운데)."""
    x0, y0, x1, y1 = ink
    t = render_text(text, os.path.join(FONTS, font), y1 - y0, color); t = fit(t.crop(ink_box(t)), x1 - x0, y1 - y0, squeeze)
    im.alpha_composite(t, (round((x0 + x1) / 2 - t.width / 2), round((y0 + y1) / 2 - t.height / 2)))


def custom_571(src):
    """매트 「いらっしゃいませ」: 리본 위 흰 글자(밝기 185 초과)를 지우고 리본 색을 번지게 채운 뒤 「어서 오세요」."""
    box = (16, 18, 112, 46)
    clean, n, ink = inpaint(src, box, lambda c: lum(c) > 185, lambda c: lum(c) > 158)
    im = clean.copy(); put(im, '어서 오세요', 'AndongKaturi.ttf', (230, 226, 222), ink)   # 엄마까투리체(사용자 지정)
    return clean, im, n, box


def custom_846(src):
    """경고 띠 「キケン注意!」: 위아래 줄무늬 사이(4~11줄), 양끝 세로 막대(x6~8·x55~58)는 두고 노란 글자만 지운다."""
    box = (9, 4, 55, 12)
    # 청록 바탕은 늘 파랑 > 빨강 → 빨강이 파랑보다 큰(-10 여유) 픽셀은 노란 글자나 그 번짐.
    # 바탕 청록이 거의 고르고 오른쪽 끝이 노란 막대라 보간하면 노랗게 번짐 → 줄마다 청록 중앙값으로 채운다
    import statistics
    clean = src.copy(); px = clean.load(); n = 0; x0, y0, x1, y1 = box
    for y in range(y0, y1):
        teal = [px[x, y] for x in range(0, 64) if px[x, y][2] > px[x, y][0] + 40]
        fill = tuple(int(statistics.median(c[k] for c in teal)) for k in range(4))
        for x in range(x0, x1):
            if px[x, y][0] > px[x, y][2] - 10:
                px[x, y] = fill; n += 1
    im = clean.copy(); put(im, '위험 주의', 'BlackHanSans-Regular.ttf', (252, 210, 72), (11, 4, 53, 12))
    return clean, im, n, box


def custom_2050(src):
    """현수막 「安全 ✚ 第一」: 짙은 글자만 지우고 가운데 초록 십자는 둔다 → 「안전 ✚ 제일」."""
    # 글자: 짙고(밝기 150 미만) 초록 기운(G≥R)이 있는 것. 자주색 테두리(R>G)·초록 십자(G≫R)는 제외
    dark = lambda c: lum(c) < 150 and c[1] >= c[0] and not (c[1] > c[0] + 50)
    ok = lambda c: lum(c) < 215 and c[1] >= c[0] and not (c[1] > c[0] + 40)
    clean, n1, ink1 = inpaint(src, (9, 4, 57, 28), dark, ok)
    clean, n2, ink2 = inpaint(clean, (72, 4, 119, 28), dark, ok)
    # 원본 글자 잉크 상자는 확실히 짙은 픽셀(밝기 60 미만)로만 잰다(바탕 회색 음영이 끼어 상자가 부풀지 않게)
    px = src.load()
    def strong(b):
        pts = [(x, y) for y in range(b[1], b[3]) for x in range(b[0], b[2]) if lum(px[x, y]) < 60]
        return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts) + 1, max(p[1] for p in pts) + 1)
    ink1, ink2 = strong((9, 4, 57, 28)), strong((72, 4, 119, 28))
    print('2050 원본 잉크', ink1, ink2)
    im = clean.copy()
    put(im, '안전', 'BlackHanSans-Regular.ttf', (0, 16, 0), ink1)
    put(im, '제일', 'BlackHanSans-Regular.ttf', (0, 16, 0), ink2)
    return clean, im, n1 + n2, (9, 4, 119, 28)


def custom_2099(src):
    """포클 문패: 판이 위(6~14줄, 밝기 약 65)·경계(15~16줄)·아래(17~22줄, 약 110) 세 띠.
    위 띠는 글자 없는 7줄의 같은 열 색, 아래 띠는 20줄의 같은 열 색을 복사하고, 경계 줄은 그 줄 좌우 판 색으로 보간."""
    im = src.copy(); px = im.load(); o = src.load(); n = 0
    # 판은 줄마다 거의 단색 → 글자 픽셀(위 띠 밝기<62, 아래 띠<105)은 그 줄 판 색의 최빈값으로 채운다
    for y in list(range(6, 15)) + list(range(17, 23)):
        cut = 62 if y <= 14 else 105
        plate = Counter(o[x, y] for x in range(12, 52) if lum(o[x, y]) >= cut)
        if not plate:
            continue
        fill = plate.most_common(1)[0][0]
        for x in range(12, 52):
            if lum(o[x, y]) < cut:
                px[x, y] = fill; n += 1
    for y in (15, 16):
        xs = [x for x in range(12, 52) if lum(o[x, y]) < 75]
        if not xs:
            continue
        a, b = o[11, y], o[52, y]
        for x in xs:
            t = (x - 11) / 41
            px[x, y] = tuple(round(a[k] * (1 - t) + b[k] * t) for k in range(4)); n += 1
    clean = im.copy()
    put(im, '포클', 'AndongKaturi.ttf', (32, 16, 24), (15, 8, 50, 21))
    return clean, im, n, (12, 6, 52, 23)


def custom_2165(src):
    """타오 문패: 나무판(139,101,57)에 짙은 글자. 나뭇결 짙은 선은 1px 두께라, 위나 아래로도 짙은(두께 2px 이상) 픽셀만 글자로 본다.
    글자 자리는 그 줄 나무색(짙지 않은 픽셀)의 중앙값으로 채운다."""
    import statistics
    im = src.copy(); px = im.load(); o = src.load(); x0, y0, x1, y1 = 4, 2, 60, 30
    dk = lambda x, y: lum(o[x, y]) < 70
    mask = Image.new('L', src.size, 0); mp = mask.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            if dk(x, y) and (dk(x, y - 1) or dk(x, y + 1)):
                mp[x, y] = 255
    ink = mask.getbbox()
    grow = mask.filter(ImageFilter.MaxFilter(3)).load(); n = 0
    for y in range(y0, y1):
        wood = [o[x, y] for x in range(x0, x1) if lum(o[x, y]) >= 95]
        fill = tuple(int(statistics.median(c[k] for c in wood)) for k in range(4))
        for x in range(x0, x1):
            if mp[x, y] or (grow[x, y] and lum(o[x, y]) < 95):
                px[x, y] = fill; n += 1
    # 글자 범위 ±2칸 안에 남은 짙은 점(두께 판정에서 빠진 획 끝·잘린 나뭇결 조각)도 모두 나무색으로
    for y in range(max(y0, ink[1] - 2), min(y1, ink[3] + 2)):
        wood = [o[x, y] for x in range(x0, x1) if lum(o[x, y]) >= 95]
        fill = tuple(int(statistics.median(c[k] for c in wood)) for k in range(4))
        for x in range(max(x0, ink[0] - 2), min(x1, ink[2] + 2)):
            c = px[x, y]
            # 짙은 점, 또는 그 줄 나무색과 색 차(RGB 차 합)가 8 넘는 얼룩 → 글자 범위 안은 나무색 하나로(사용자 지시: 잔여 픽셀 제거)
            if c != fill and (lum(c) < 100 or sum(abs(c[k] - fill[k]) for k in range(3)) > 8):
                px[x, y] = fill; n += 1
    clean = im.copy()
    put(im, '타오', 'AndongKaturi.ttf', (41, 16, 41), (ink[0] - 1, ink[1], ink[2] - 1, ink[3]))   # 사용자 지시: 왼쪽으로 1px
    return clean, im, n, (x0, y0, x1, y1)


def custom_2040(src):
    """메트 간판: 청록 금속판에 밝은 베이지 글자 → 밝은 픽셀을 지우고 주변 금속색이 번지게 채운다."""
    box = (6, 5, 58, 27)
    # 청록 바탕은 파랑이 빨강보다 훨씬 큼(약 +80), 베이지 글자는 거의 같음 → 색으로 가른다(테두리 자주색은 어두워서 제외)
    clean, n, ink = inpaint(src, box, lambda c: c[2] - c[0] < 45 and lum(c) > 90, lambda c: c[2] - c[0] < 62 and lum(c) > 85)
    im = clean.copy(); put(im, '메트', 'AndongKaturi.ttf', (148, 153, 139), ink)
    return clean, im, n, box


def _row_mode_fill(src, box, is_text):
    """box 안을 줄마다 그 줄의 가장 흔한(글자 아닌) 색으로 칠한다. 원본 글자 잉크 상자와 지운 수를 돌려준다."""
    im = src.copy(); px = im.load(); o = src.load(); x0, y0, x1, y1 = box; n = 0
    pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if is_text(o[x, y])]
    ink = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts) + 1, max(p[1] for p in pts) + 1)
    for y in range(y0, y1):
        fill = Counter(o[x, y] for x in range(x0, x1) if not is_text(o[x, y])).most_common(1)[0][0]
        for x in range(x0, x1):
            if px[x, y] != fill:
                px[x, y] = fill; n += 1
    return im, n, ink


def custom_1378(src):
    """발밑 주의(세로): 빨간 판 안쪽(x4~27, y2~62)을 판 빨강으로 칠하고, 흰 글자를 세로로."""
    box = (4, 2, 28, 63)
    clean, n, ink = _row_mode_fill(src, box, lambda c: lum(c) > 150)
    im = clean.copy()
    sp = dict(text='발밑주의', font='BlackHanSans-Regular.ttf', vertical=True, vw=0.85, cells=True)   # 원본처럼 띄어쓰기 없이 한 글자씩 같은 크기
    return clean, place(clean, sp, ink, (255, 255, 255)), n, box


def _label(src, text, squeeze=0.85):
    """원숭이·불량배 경고판 아래 흰 라벨(x5~58, y72~88): 줄마다 라벨색으로 칠하고 남색 글자."""
    box = (5, 72, 59, 89)
    clean, n, ink = _row_mode_fill(src, box, lambda c: lum(c) < 185)
    im = clean.copy(); put(im, text, 'BlackHanSans-Regular.ttf', (24, 20, 120), (ink[0], ink[1], ink[2], ink[3]), squeeze=squeeze)
    return clean, im, n, box


def custom_1544(src):
    """방 이름판 세 칸(노랑·흰·흰): 칸마다 줄별 최빈색으로 칠하고 「촌장실 / 자료실 / 전망대」."""
    im = src.copy(); px = im.load(); n = 0; inks = []
    for box in ((4, 4, 60, 28), (3, 36, 60, 60), (3, 68, 60, 92)):
        x0, y0, x1, y1 = box
        pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if lum(px[x, y]) < 150]
        inks.append((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts) + 1, max(p[1] for p in pts) + 1))
        # 칸 몸통은 단색 → 칸 전체 최빈색 하나로(줄별로 하면 가로획이 줄을 덮은 줄에서 줄무늬가 남음)
        fill = Counter(px[x, y] for y in range(y0, y1) for x in range(x0, x1)).most_common(1)[0][0]
        for y in range(y0, y1):
            for x in range(x0, x1):
                if px[x, y] != fill:
                    px[x, y] = fill; n += 1
    clean = im.copy()
    # 세 칸 같은 글자 크기: 원본 세 줄 잉크 높이·폭 중 가장 작은 것에 맞춘 한 크기로, 칸마다 원본 잉크 가운데에
    hh = min(i[3] - i[1] for i in inks[1:]); ww = min(i[2] - i[0] for i in inks[1:])   # 자료실·전망대 크기에 촌장실을 맞춘다
    # 칸 안쪽(테두리 제외) 가로·세로 가운데에 맞춘다(사용자 지시)
    plates = ((3, 2, 61, 29), (2, 35, 61, 62), (2, 67, 61, 94))   # 칸 안쪽 실측(노랑 x3~60·y2~28, 흰 x2~60·y35~61, y67~93)
    for text, ink, col, pl in zip(('촌장실', '자료실', '전망대'), inks, ((96, 64, 16), (0, 0, 0), (0, 0, 0)), plates):
        cx, cy = (pl[0] + pl[2]) / 2, (pl[1] + pl[3]) / 2
        put(im, text, 'DoHyeon-Regular.ttf', col, (round(cx - ww / 2), round(cy - hh / 2), round(cx + ww / 2), round(cy + hh / 2)))
    return clean, im, n, (2, 4, 61, 92)


def _kochira(im, src_box, bg_text, col, edge=None):
    """깃발 아래 「◀コチラ」: ◀(x6~15)는 두고 コチラ 자리(x16~45)만 줄별 바탕색으로 칠한 뒤 「이쪽」."""
    im, n, ink = _row_mode_fill(im, src_box, bg_text)
    f = os.path.join(FONTS, 'Galmuri9.ttf')
    t = crisp_outline('이쪽', f, ink[3] - ink[1] - 2, col, edge, stroke=1, aa=False) if edge else render_text('이쪽', f, ink[3] - ink[1], col)
    t = t.crop(ink_box(t, 100))
    # 세로: 왼쪽 ◀ 화살표(x6~15의 밝은 픽셀)의 세로 가운데에 「이쪽」 가운데를 맞춘다(사용자 지시)
    px = im.load()
    ay = [y for y in range(src_box[1], src_box[3]) for x in range(6, 16) if lum(px[x, y]) > 200]
    cy = (min(ay) + max(ay) + 1) / 2 if ay else (ink[1] + ink[3]) / 2
    im.alpha_composite(t, (src_box[0] + 1, round(cy - t.height / 2)))
    return im, n


def custom_2281(src):
    """찻집 깃발(초록): 노란 원 안의 초록 「茶」 → 「차」, 아래 コチラ → 이쪽."""
    # 원 안 글자는 초록(G>R), 노란 바탕·주황 테두리는 R>G → 색으로 가른다
    # 원(중심 25,52 반지름 11.5) 안만 지운다 — 원 밖 초록 바탕까지 지우면 노란 번짐이 생김
    inc = {(x, y) for y in range(39, 65) for x in range(11, 39) if (x - 25) ** 2 + (y - 52) ** 2 <= 11.5 ** 2}
    o = src.load(); pos = {}
    def is_t(c, _o=o):
        return c[1] > c[0] + 10
    tmp = src.copy(); tp = tmp.load()
    for y in range(39, 65):
        for x in range(11, 39):
            if (x, y) not in inc:
                tp[x, y] = (238, 190, 98, 255)                     # 원 밖은 원 테두리 주황으로(R>G라 글자 아님, 채울 때 경계색도 자연스럽게)
    clean_c, n, ink = inpaint(tmp, (11, 39, 39, 65), is_t, lambda c: c[1] > c[0] - 25 and lum(c) < 215)
    # 2차: 원 안에 남은 번짐(빨강이 초록보다 12 미만 큰 올리브빛, 밝기 180 미만 얼룩)을 다시 지운다. 원래 반짝이(255,242,148)는 남김
    clean_c = clean_c.copy(); tc = clean_c.load()
    for y in range(39, 65):
        for x in range(11, 39):
            if (x, y) not in inc:
                tc[x, y] = (238, 190, 98, 255)
    clean_c, n2, _ = inpaint(clean_c, (11, 39, 39, 65), lambda c: c[0] - c[1] < 12 or lum(c) < 180, lambda c: False)
    n += n2
    clean = src.copy(); cp = clean.load(); cc = clean_c.load()
    for (x, y) in inc:
        cp[x, y] = cc[x, y]
    clean2, n2 = _kochira(clean.copy(), (16, 110, 46, 122), lambda c: lum(c) > 120, (255, 255, 255))
    im = clean2.copy()
    # 「차」를 약간 기울인다(사용자 지시): 시계 방향 10°, 원본 잉크 가운데에 맞춤
    x0, y0, x1, y1 = ink
    t = render_text('차', os.path.join(FONTS, 'SongMyung-Regular.ttf'), y1 - y0, (0, 89, 0)); t = t.crop(ink_box(t))
    t = fit(t, x1 - x0, y1 - y0).rotate(-10, resample=Image.BICUBIC, expand=True)
    t = t.crop(ink_box(t, 20))
    if t.width > x1 - x0 + 2 or t.height > y1 - y0 + 2:
        k = min((x1 - x0 + 2) / t.width, (y1 - y0 + 2) / t.height); t = t.resize((round(t.width * k), round(t.height * k)), Image.LANCZOS)
    im.alpha_composite(t, (round((x0 + x1) / 2 - t.width / 2) - 1, round((y0 + y1) / 2 - t.height / 2) + 1))   # 사용자 지시: 왼쪽 아래로 1px
    # 「이쪽」은 _kochira 안에서 이미 그려 넣었으므로, 지운 그림(clean)에는 글자 없는 상태를 따로 남긴다
    c3, _, _ = _row_mode_fill(clean, (16, 110, 46, 122), lambda c: lum(c) > 120)
    return c3, im, n + n2, (11, 39, 46, 122)


def custom_2283(src):
    """염색 깃발(남색): 흰 「染めます」(짙은 남색 테두리) → 「염색합니다」 세로, 아래 コチラ → 이쪽."""
    body = (2, 4, 46, 96)
    o = src.load()
    edge = Counter(o[x, y][:3] for y in range(4, 96) for x in range(2, 46) if 40 < lum(o[x, y]) < 62).most_common(1)[0][0]
    clean, n, ink = _row_mode_fill(src, body, lambda c: abs(lum(c) - 68) > 5)
    clean, n2 = _kochira(clean, (16, 110, 46, 121), lambda c: abs(lum(c) - 68) > 5, (255, 255, 255))   # 작은 글씨는 테두리 없이(테두리를 넣으면 획이 깨짐)
    c_only, _, _ = _row_mode_fill(clean, (16, 110, 46, 121), lambda c: abs(lum(c) - 68) > 5)
    im = clean.copy()
    # 세로 다섯 글자: 원본 잉크 범위를 다섯 칸으로 나눠 같은 크기, 흰 글자 + 짙은 남색 1px 테두리
    ix0, iy0, ix1, iy1 = ink; k = 5; gap = 1; ch_h = (iy1 - iy0 - gap * (k - 1)) / k; cx = (ix0 + ix1) / 2
    # 다섯 글자를 같은 글자 크기·같은 확대 비율로(글자마다 따로 늘리면 크기가 들쭉날쭉) → 가장 큰 글자가 칸에 들도록 한 배율을 모두에 적용
    gs = [crisp_outline(ch, os.path.join(FONTS, 'AndongKaturi.ttf'), round(ch_h), (255, 255, 255), edge, stroke=1, aa=True) for ch in '염색합니다']
    ky = ch_h / max(g.height for g in gs); kx = min(ky * 1.6, (ix1 - ix0) / max(g.width for g in gs))   # 깃발 폭을 채우되 가로는 세로의 1.6배까지
    gs = [g.resize((max(1, round(g.width * kx)), max(1, round(g.height * ky))), Image.LANCZOS) for g in gs]
    # 깃발 몸통(위 테두리 아래 y4 ~ 줄무늬 위 y96) 세로 가운데에 다섯 글자 묶음을 놓는다(사용자 지시)
    total = sum(g.height for g in gs) + gap * (k - 1); y = (4 + 96) / 2 - total / 2
    cx = (2 + 46) / 2                                    # 가로도 깃발 몸통(x2~45) 가운데(원본 잉크는 그림자 때문에 한쪽으로 치우침)
    for g in gs:
        im.alpha_composite(g, (round(cx - g.width / 2), round(y))); y += g.height + gap
    return c_only, im, n + n2, (2, 4, 46, 121)


def _protected(x, y, protect):
    """protect: 사각형 (x0,y0,x1,y1) 목록 또는 픽셀 좌표 집합(set)."""
    if isinstance(protect, set):
        return (x, y) in protect
    return any(a0 <= x < a1 and b0 <= y < b1 for a0, b0, a1, b1 in protect)


def deco_pixels(src, pred, seeds, pad=1):
    """장식(꺾쇠 등) 덩어리의 실제 픽셀 + pad 칸을 집합으로(사각형으로 보호하면 옆 글자 꼬리까지 막힘)."""
    px = src.load(); w, h = src.size; out = set()
    for sd in seeds:
        stack = [sd]; seen = {sd}
        while stack:
            x, y = stack.pop()
            for dx in range(-pad, pad + 1):
                for dy in range(-pad, pad + 1):
                    out.add((x + dx, y + dy))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    if 0 <= n[0] < w and 0 <= n[1] < h and n not in seen and pred(px[n]):
                        seen.add(n); stack.append(n)
    return out


def comp_erase(src, pred, boxes, grow_pred, iters=800, grow_n=1, protect=(), seeds=(), bg=None, cols=False):
    """pred 를 만족하는 픽셀 덩어리 중 boxes(덩어리 bbox 목록) 안에 든 것만 지우고(+1px 번짐) 주변 색을 사방으로 번지게 채운다."""
    import numpy as np
    w, h = src.size; px = src.load()
    mask = Image.new('L', src.size, 0); mp = mask.load()
    if seeds:                                            # 씨앗 점에서 이어진 덩어리만(사각형 범위로 잡으면 옆 장식까지 먹힘)
        stack = [p for p in seeds if pred(px[p])]
        for p in stack: mp[p] = 255
        while stack:
            x, y = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not mp[nx, ny] and pred(px[nx, ny]):
                        mp[nx, ny] = 255; stack.append((nx, ny))
    for (x0, y0, x1, y1) in boxes:
        for y in range(y0, y1):
            for x in range(x0, x1):
                if pred(px[x, y]):
                    mp[x, y] = 255
    ink = mask.getbbox()
    g = mask
    for _ in range(grow_n):                              # 글자 둘레 압축 번짐 폭만큼 넓힌다(grow_pred 만족하는 것만)
        g = g.filter(ImageFilter.MaxFilter(3))
    grow = g.load()
    for y in range(h):
        for x in range(w):
            if grow[x, y] and grow_pred(px[x, y]) and not _protected(x, y, protect):
                mp[x, y] = 255
    a = np.asarray(src, dtype=np.float64).copy(); m = np.asarray(mask) > 0
    keep = a.copy()
    if bg is not None:                                   # 채우는 동안만, 지우지 않는 밝은 장식(꺾쇠 등)을 바탕색으로 보고 번짐을 막는다
        deco = np.zeros(m.shape, bool)
        for y in range(h):
            for x in range(w):
                if not m[y, x] and pred(px[x, y]):
                    deco[y, x] = True
        a[deco] = bg
    if cols:                                             # 세로 주름 천: 열마다 위·아래 바탕을 직선 보간(주름 줄무늬가 이어짐), 번짐 채우기는 생략
        for x in range(w):
            if m[:, x].any():
                ys = np.where(~m[:, x])[0]
                for k in range(4):
                    a[:, x, k] = np.where(m[:, x], np.interp(np.arange(h), ys, a[ys, x, k]), a[:, x, k])
        for _ in range(cols if isinstance(cols, int) and cols > 1 else 6):   # 열마다 튀는 줄을 가로로만 살짝 고르게(지운 칸 안에서만)
            nb = (np.roll(a, 1, 1) + 2 * a + np.roll(a, -1, 1)) / 4
            a[m] = nb[m]
        iters = 0
    for y in range(h):
        if not cols and m[y].any():
            xs = np.where(~m[y])[0]
            if len(xs):
                for k in range(4):
                    a[y, :, k] = np.where(m[y], np.interp(np.arange(w), xs, a[y, xs, k]), a[y, :, k])
    for _ in range(iters):
        nb = (np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 4
        a[m] = nb[m]
    keep[m] = a[m]                                       # 지운 칸만 바꾸고 나머지(장식 포함)는 원본 그대로
    return Image.fromarray(np.clip(np.round(keep), 0, 255).astype(np.uint8), 'RGBA').copy(), int(m.sum()), ink


def _tea(im, ink, color, font='SongMyung-Regular.ttf'):
    """「차」 한 글자를 원본 잉크 상자 가운데에(2281 찻집 깃발과 같은 송명)."""
    put(im, '차', font, color, ink)


def custom_1824(src):
    """찻집 남색 포렴: 흰 「茶」만 지우고(「 」 꺾쇠와 「。」는 둠) 천 주름 음영으로 채운 뒤 흰 「차」."""
    # 꺾쇠 두 개·「。」(덩어리 bbox ±1)는 지우지 않게 보호
    o = src.load()
    seed = next((x, y) for y in range(40, 70) for x in range(40, 60) if lum(o[x, y]) > 150)   # 「茶」 가운데쯤 흰 점
    clean, n, ink = comp_erase(src, lambda c: lum(c) > 150, [], lambda c: lum(c) > 58, grow_n=6,
                               protect=deco_pixels(src, lambda c: lum(c) > 150, [(85, 26), (16, 92), (93, 83)]), seeds=[seed], cols=True,
                               bg=Counter(o[x, y] for y in range(10, 120) for x in range(5, 110) if 40 <= lum(o[x, y]) <= 50).most_common(1)[0][0])
    im = clean.copy(); _tea(im, ink, (238, 238, 246)); return clean, im, n, (ink[0] - 7, ink[1] - 7, ink[2] + 7, ink[3] + 7)   # 지운 범위(글자 ±6칸)


def custom_1828(src):
    """찻집 양산: 크림색 삼각형 위 초록 「茶」만 지우고(「。」는 둠) 초록 「차」."""
    # 크림 바탕도 G가 R보다 최대 4 높음 → G가 R보다 6 넘게 높은 초록 번짐을 2칸까지 지운다(「。」 덩어리는 보호)
    clean, n, ink = comp_erase(src, lambda c: c[1] > c[0] + 20, [(22, 43, 40, 59), (40, 43, 44, 54)], lambda c: c[1] > c[0] + 6,
                               grow_n=2, protect=deco_pixels(src, lambda c: c[1] > c[0] + 20, [(42, 56)]))
    # 지운 칸은 사방 번짐 채우기 때문에 옅은 얼룩이 남는다 → 양산 가운데는 거의 단색 크림이라, 지운 픽셀마다
    # 같은 줄에서 지우지 않은 픽셀(x20~46)의 최빈 크림색으로 다시 칠한다(사용자 지시: 차 옆 잔여 정리)
    cp = clean.load(); op = src.load()
    creams = [(255, 255, 205, 255), (255, 250, 205, 255)]   # 양산 가운데 크림 두 가지(위쪽·아래쪽)
    dot = deco_pixels(src, lambda c: c[1] > c[0] + 20, [(42, 56)], pad=1)
    fm = Image.new('L', src.size, 0); fp = fm.load()
    for y in range(36, 64):
        for x in range(16, 50):
            c = op[x, y]
            if c[1] > c[0] + 6 and (x, y) not in dot:
                fp[x, y] = 255
    for _ in range(3):
        fm = fm.filter(ImageFilter.MaxFilter(3))
    fp = fm.load(); foot = {(x, y) for y in range(src.height) for x in range(src.width) if fp[x, y]}
    for y in range(40, 62):
        row = Counter(op[x, y] for x in list(range(16, 20)) + list(range(45, 49)) if op[x, y] in creams)
        row.update(op[x, y] for x in range(20, 45) if op[x, y] in creams)
        cream_r = row.most_common(1)[0][0] if row else creams[0]
        # 원본 「茶」 모양(초록 기운 픽셀)을 3칸 넓힌 자리만 그 줄 크림 하나로(사각형 전체를 칠하면 옆 음영과 경계가 보임)
        for x in range(18, 48):
            if (x, y) in foot and (x, y) not in dot and cp[x, y] != cream_r:
                cp[x, y] = cream_r
    # 「。」 바로 위(x36~46, y47~53)에 남은 밝은·초록빛 점(원본 글자 번짐)을 그 자리 크림색 최빈값으로(사용자 지시)
    area = [(x, y) for y in range(47, 54) for x in range(36, 47)]
    cream = Counter(cp[p] for p in area).most_common(1)[0][0]
    for p in area:
        if sum(abs(cp[p][k] - cream[k]) for k in range(3)) > 8:
            cp[p] = cream; n += 1
    im = clean.copy(); _tea(im, ink, (99, 154, 8)); return clean, im, n, (13, 33, 53, 65)   # 글자 모양 ±3칸까지 다시 칠한 범위


def custom_251(src):
    """차 아가씨 로봇 옷의 「お茶」(빨간 바탕 흰 세로 두 글자) → 「차」 한 글자를 가운데 크게."""
    clean, n, ink = comp_erase(src, lambda c: lum(c) > 150, [(0, 0, 32, 32)], lambda c: lum(c) > 105)
    im = clean.copy(); _tea(im, (6, 6, 26, 27), (255, 245, 245)); return clean, im, n, (0, 0, 32, 32)


def custom_1985(src):
    """복권 현수막: 빨간 「発売中!」·파란 「ナナシ島宝くじ」만 지우고 크림으로 → 「발매 중!」(빨강) / 「나나시섬 복권」(파랑). 마스코트·야자는 둠."""
    red = lambda c: c[0] - c[1] > 60 and c[0] > 150
    blue = lambda c: c[2] - c[0] > 60
    o = src.load()
    def ink_of(pred, box):
        pts = [(x, y) for y in range(box[1], box[3]) for x in range(box[0], box[2]) if pred(o[x, y])]
        return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts) + 1, max(p[1] for p in pts) + 1)
    i1 = ink_of(red, (30, 0, 100, 16)); i2 = ink_of(blue, (30, 14, 120, 32))
    # 글자: 빨강(R-G>40) 또는 파랑 기운(B-R>12, 옅은 가장자리 포함). 1칸 넓힌 곳은 조금이라도 파랑·빨강 기운이면 지움
    # 크림(255,245,210)은 파랑이 빨강보다 45 낮음 → 파랑이 빨강에 가까운(회색 그림자·파란 글자) 픽셀, 또는 빨간 글자를 지운다.
    # 야자 잎(초록)·열매·줄기(갈색)는 해당 없음. 「じ」 끝(x~118)까지 포함
    leaf = lambda c: c[1] > c[2] + 10 and c[1] > c[0] - 10      # 야자 잎: 초록이 파랑보다 확실히 큼
    notcream = lambda c: (c[2] > c[0] - 25 and not leaf(c)) or c[0] - c[1] > 40
    # 지우는 범위는 자주색 테두리(y0~1, y30~31) 안쪽만 — 테두리도 「크림 아님」이라 범위에 넣으면 같이 지워진다
    clean, n, _ = comp_erase(src, notcream, [(30, 2, 100, 16), (30, 14, 120, 30)], lambda c: c[2] > c[0] - 38 and not leaf(c), grow_n=1,
                             protect=[(0, 0, 128, 2), (0, 30, 128, 32)])
    im = clean.copy()
    put(im, '발매 중!', 'AndongKaturi.ttf', (255, 0, 0), i1)   # 엄마까투리체(사용자 지정)
    put(im, '나나시섬 복권', 'AndongKaturi.ttf', (38, 52, 204), i2)
    return clean, im, n, (28, 2, 122, 30)


def custom_1986(src):
    """복권 날짜판 6칸: 칸 안을 그 칸 크림색으로 칠하고, 빨간 글자에 원본처럼 옅은 그림자(오른쪽 아래 1px)."""
    texts = ['5일 남음', '4일 남음', '3일 남음', '2일 남음', '내일 발표', '오늘 발표']
    o = src.load(); w, h = src.size
    sep = lambda c: c[1] < 235 and c[0] - c[1] < 60            # 칸 경계선·그림자(216,207,175 계열)
    # 칸 경계: 위 칸(y0~14)에서 거의 전부 경계색인 열
    cols = [x for x in range(w) if sum(1 for y in range(0, 15) if sep(o[x, y])) >= 13]
    xs = [0] + [x for i, x in enumerate(cols) if i == 0 or x != cols[i - 1] + 1] + [w]
    cells = []
    for (y0, y1) in ((0, 15), (16, 32)):
        edges = sorted(set(cols))
        starts = [0] + [x + 1 for x in edges]
        bounds = []
        for st in starts:
            en = next((x for x in edges if x >= st), w)
            if en - st >= 20:
                bounds.append((st, en))
        for (x0, x1) in bounds:
            cells.append((x0, y0, x1, y1))
    im = src.copy(); px = im.load(); n = 0; inks = []
    for (x0, y0, x1, y1) in cells:
        pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if o[x, y][0] - o[x, y][1] > 60]
        inks.append((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts) + 1, max(p[1] for p in pts) + 1))
        fill = Counter(o[x, y] for y in range(y0, y1) for x in range(x0, x1) if o[x, y][1] >= 235).most_common(1)[0][0]
        for y in range(y0, y1):
            for x in range(x0, x1):
                if px[x, y] != fill:
                    px[x, y] = fill; n += 1
    clean = im.copy()
    hh = min(i[3] - i[1] for i in inks)
    for t, (x0, y0, x1, y1), ink in zip(texts, cells, inks):
        cy = (ink[1] + ink[3]) / 2; box = (x0 + 2, round(cy - hh / 2), x1 - 3, round(cy + hh / 2))
        g = render_text(t, os.path.join(FONTS, 'DoHyeon-Regular.ttf'), hh, (255, 0, 0)); g = fit(g.crop(ink_box(g)), box[2] - box[0], hh)
        sh = render_text(t, os.path.join(FONTS, 'DoHyeon-Regular.ttf'), hh, (216, 207, 175)); sh = fit(sh.crop(ink_box(sh)), box[2] - box[0], hh)
        gx = round((x0 + x1) / 2 - g.width / 2); gy = round(cy - g.height / 2)
        im.alpha_composite(sh, (gx + 1, gy + 1)); im.alpha_composite(g, (gx, gy))
    return clean, im, n, (0, 0, w, h)


def custom_2154(src):
    """나나시 관광 이정표: 나무판 테두리 안·마스코트 왼쪽(x3~37)의 크림 글자와 자주색 테두리만 지우고 나무색으로.
    「나나시」(작게)·「관광」(크게), 크림 글자 + 자주색 1px 테두리."""
    box = (3, 3, 37, 29); o = src.load()
    txt = lambda c: c[0] - c[2] < 70                    # 나무(주황)는 R-B가 크다(120 이상), 글자·테두리·번짐은 색이 옅어 R-B가 작다
    pts1 = [(x, y) for y in range(3, 14) for x in range(3, 30) if lum(o[x, y]) > 200]
    pts2 = [(x, y) for y in range(14, 29) for x in range(3, 37) if lum(o[x, y]) > 200]
    bb = lambda pts: (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts) + 1, max(p[1] for p in pts) + 1)
    i1, i2 = bb(pts1), bb(pts2)
    clean, n, _ = comp_erase(src, txt, [box], lambda c: lum(c) < 120 or lum(c) > 185, grow_n=1, iters=0)
    # 나무판은 가로 판자라 줄마다 거의 같은 색 → 지운 칸을 그 줄 나무색(밝기 120~190, 글자·마스코트 제외)의 최빈값으로
    cp = clean.load()
    for y in range(box[1] - 1, box[3] + 1):
        wood = Counter(o[x, y] for x in range(2, 40) if 120 <= lum(o[x, y]) <= 190 and cp[x, y] == o[x, y])
        if not wood:
            continue
        f = wood.most_common(1)[0][0]
        for x in range(box[0] - 1, box[2] + 1):
            if cp[x, y] != o[x, y]:
                cp[x, y] = f
    im = clean.copy(); f = os.path.join(FONTS, 'DoHyeon-Regular.ttf')
    for t, ink in (('나나시', i1), ('관광', i2)):
        g = crisp_outline(t, f, ink[3] - ink[1], (238, 234, 222), (74, 20, 49), stroke=1, aa=True)
        g = fit(g, ink[2] - ink[0] + 2, ink[3] - ink[1] + 2)
        im.alpha_composite(g, (round((ink[0] + ink[2]) / 2 - g.width / 2), round((ink[1] + ink[3]) / 2 - g.height / 2)))
    return clean, im, n, (box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1)


def _ink(src, pred, box):
    o = src.load(); pts = [(x, y) for y in range(box[1], box[3]) for x in range(box[0], box[2]) if pred(o[x, y])]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts) + 1, max(p[1] for p in pts) + 1)


def custom_2032(src):
    """메이어 문패(작은 금색 판): 짙은 글자만 지우고 판 색을 번지게 채운 뒤 「메이어」(엄마까투리체, 원본 글자색)."""
    box = (70, 44, 104, 58); dark = lambda c: lum(c) < 125
    ink = _ink(src, dark, box)
    col = Counter(src.getpixel(p)[:3] for p in [(x, y) for y in range(box[1], box[3]) for x in range(box[0], box[2])] if lum(src.getpixel(p)) < 105).most_common(1)[0][0]
    clean, n, _ = comp_erase(src, dark, [box], lambda c: lum(c) < 142, grow_n=1)
    im = clean.copy(); put(im, '메이어', 'AndongKaturi.ttf', col, ink)
    return clean, im, n, (69, 43, 105, 59)


def custom_1871(src):
    """사진 피규어 기계 「取出口」: 흰 글자·분홍빛 그림자를 지우고 판 색을 번지게 채운 뒤 「꺼내는 곳」(흰 글자 + 그림자). 아래 EE는 둠."""
    box = (11, 16, 53, 36); lt = lambda c: lum(c) > 125
    ink = _ink(src, lambda c: lum(c) > 200, box)
    clean, n, _ = comp_erase(src, lt, [box], lambda c: lum(c) > 113, grow_n=1, iters=0)
    # 판은 위쪽 자주색과 아래 짙은 사다리꼴(윗변 y29, 가운데는 평평) 두 단색 → 지운 칸을 줄 단위로 위·아래 색으로 칠한다
    o = src.load(); cp = clean.load()
    upper = Counter(o[x, y] for y in range(12, 16) for x in range(4, 60)).most_common(1)[0][0]
    lower = Counter(o[x, y] for y in range(37, 41) for x in range(8, 56)).most_common(1)[0][0]
    for y in range(box[1] - 1, box[3] + 1):
        side = Counter(o[x, y] for x in list(range(4, 10)) + list(range(55, 60)) if cp[x, y] == o[x, y] and lum(o[x, y]) > 105)
        top = side.most_common(1)[0][0] if (y <= 28 and side) else upper
        for x in range(box[0], box[2]):                    # 글자 칸 전체를 그 줄 색으로(글자 기준에 못 미친 옅은 점까지 정리)
            c = top if y <= 28 else lower
            if cp[x, y] != c:
                cp[x, y] = c
        for x in (box[0] - 1, box[2]):                      # 1칸 넓혀 지운 가장자리
            if cp[x, y] != o[x, y]:
                cp[x, y] = top if y <= 28 else lower
    im = clean.copy(); f = os.path.join(FONTS, 'DoHyeon-Regular.ttf'); x0, y0, x1, y1 = ink
    g = fit(render_text('꺼내는 곳', f, y1 - y0, (250, 222, 250)), x1 - x0, y1 - y0)
    sh = fit(render_text('꺼내는 곳', f, y1 - y0, (150, 110, 140)), x1 - x0, y1 - y0)
    gx = round((x0 + x1) / 2 - g.width / 2); gy = round((y0 + y1) / 2 - g.height / 2)
    im.alpha_composite(sh, (gx + 1, gy + 1)); im.alpha_composite(g, (gx, gy))
    return clean, im, n, (box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1)   # 1칸 넓혀 지운 범위


def custom_1875(src):
    """사진 피규어 기계 「準備中」: 왼쪽 흰 칸(x0~127)을 흰색으로 칠하고 검은 「준비 중」. 오른쪽 그림은 둠."""
    box = (0, 0, 128, 128); ink = _ink(src, lambda c: lum(c) < 128, box)
    im = src.copy(); px = im.load(); n = 0
    for y in range(128):
        for x in range(128):
            if px[x, y] != (255, 255, 255, 255):
                px[x, y] = (255, 255, 255, 255); n += 1
    clean = im.copy(); put(im, '준비 중', 'BlackHanSans-Regular.ttf', (0, 0, 0), ink)   # 블랙한산스(사용자 지정)
    return clean, im, n, box


def _bg_fill_rows(src, box, is_text):
    """box 안 글자 픽셀(+1칸 번짐 중 바탕과 다른 것)을 그 줄 바탕(글자 아닌 픽셀) 최빈색으로."""
    im = src.copy(); px = im.load(); o = src.load(); x0, y0, x1, y1 = box; n = 0
    mask = Image.new('L', src.size, 0); mp = mask.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            if is_text(o[x, y]):
                mp[x, y] = 255
    ink = mask.getbbox()
    g = mask.filter(ImageFilter.MaxFilter(3)).load()
    for y in range(y0, y1):
        bgc = Counter(o[x, y] for x in range(x0, x1) if not g[x, y]).most_common(1)
        if not bgc:
            bgc = Counter(o[x, y] for x in range(x0, x1) if not mp[x, y]).most_common(1)
        if not bgc:                                          # 줄 전체가 글자 기준에 걸리면(테두리 줄 등) 손대지 않는다
            continue
        f = bgc[0][0]
        for x in range(x0, x1):
            if g[x, y] and px[x, y] != f and (mp[x, y] or sum(abs(o[x, y][k] - f[k]) for k in range(3)) > 12):
                px[x, y] = f; n += 1
    return im, n, ink


def custom_2176(src):
    """로프웨이 매표기: 「きっぷ販売機」 → 「승차권 / 판매기」, 분홍 「こども」 → 「어린이」, 하늘 「おとな」 → 「어른」. NANASHI ROPEWAY는 둠."""
    o = src.load(); im = src.copy(); n = 0; jobs = []
    for box, text, isx, font in (((15, 11, 51, 29), '승차권|판매기', lambda c: lum(c) < 170, 'Galmuri11-Bold.ttf'),
                                 ((97, 64, 125, 92), '어린이', lambda c: lum(c) < 200 and c[0] > c[2] - 10, 'AndongKaturi.ttf'),
                                 ((97, 97, 125, 125), '어른', lambda c: lum(c) < 225 and c[2] > c[0], 'AndongKaturi.ttf')):
        dk = sorted((lum(o[x, y]), o[x, y][:3]) for y in range(box[1], box[3]) for x in range(box[0], box[2]) if isx(o[x, y]))
        col = Counter(c for _, c in dk[:max(1, len(dk) // 3)]).most_common(1)[0][0]
        im, k, ink = _bg_fill_rows(im, box, isx); n += k; jobs.append((text, font, col, ink))
    clean = im.copy()
    # 분홍·하늘 타일(어린이·어른)은 같은 글자 크기로: 둘 다 같은 높이로 그리고, 더 넓은 「어린이」가 칸에 들어가는 배율을 둘에 똑같이
    tiles = jobs[1:]; f = os.path.join(FONTS, 'AndongKaturi.ttf')
    hh = min(i[3] - i[1] for _, _, _, i in tiles)
    gs = [render_text(t, f, hh, c) for t, _, c, _ in tiles]; gs = [g.crop(ink_box(g)) for g in gs]
    k = min(1.0, min((i[2] - i[0]) / g.width for g, (_, _, _, i) in zip(gs, tiles)))
    for g, (_, _, _, i) in zip(gs, tiles):
        g = g.resize((max(1, round(g.width * k)), max(1, round(g.height * k))), Image.LANCZOS)
        im.alpha_composite(g, (round((i[0] + i[2]) / 2 - g.width / 2), round((i[1] + i[3]) / 2 - g.height / 2)))
    jobs = jobs[:1]
    for text, font, col, ink in jobs:
        if '|' in text:                                     # 두 줄: 원본 잉크를 위아래 반으로 나눠 한 줄씩
            a, b = text.split('|'); mid = (ink[1] + ink[3]) // 2
            put(im, a, font, col, (ink[0], ink[1], ink[2], mid - 1)); put(im, b, font, col, (ink[0], mid + 1, ink[2], ink[3]))
        else:
            put(im, text, font, col, ink)
    return clean, im, n, (0, 0, 128, 128)


def custom_2189(src):
    """쓰레기통 초록 띠 「ビューティフル・ナナシ」 → 「뷰티풀 나나시」(원본 옅은 글자색)."""
    box = (4, 47, 60, 57); isx = lambda c: lum(c) > 110
    o = src.load(); col = Counter(o[x, y][:3] for y in range(box[1], box[3]) for x in range(box[0], box[2]) if isx(o[x, y])).most_common(1)[0][0]
    clean, n, ink = _bg_fill_rows(src, box, isx)
    # 도트 글꼴은 원래 크기에서 번짐 없이(1비트) 그린다 — 줄이면 뭉개져 안 읽힘
    f = ImageFont.truetype(os.path.join(FONTS, 'Galmuri7.ttf'), 8)
    t = Image.new('RGBA', (80, 16), (0, 0, 0, 0)); d = ImageDraw.Draw(t); d.fontmode = '1'
    d.text((1, 1), '뷰티풀 나나시', font=f, fill=col + (255,)); t = t.crop(t.getbbox())
    im = clean.copy(); im.alpha_composite(t, (round((box[0] + box[2]) / 2 - t.width / 2), round((box[1] + box[3]) / 2 - t.height / 2)))
    return clean, im, n, box


def custom_1379(src):
    """로프웨이 환영 현수막(바탕 투명): 글자(초록·주황 + 복숭아빛 테두리)를 투명으로 지우고(양끝 꽃은 둠),
    「나나시 로프웨이에」(주황) + 「어서 오세요」(초록), 주아 + 복숭아빛 1px 테두리."""
    im = src.copy(); px = im.load(); n = 0
    box = (45, 5, 212, 23)                               # x200~210 초록 조각까지 지운다(사용자 지시), 오른쪽 꽃은 x213부터
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            if px[x, y][3] > 0:
                px[x, y] = (255, 215, 195, 0); n += 1
    clean = im.copy(); o = src.load()
    green = Counter(o[x, y][:3] for y in range(7, 21) for x in range(46, 90) if o[x, y][3] > 200 and o[x, y][1] > o[x, y][0]).most_common(1)[0][0]
    orange = (255, 167, 0); peach = (255, 215, 195); f = os.path.join(FONTS, 'Jua.ttf')
    x0, y0, x1, y1 = 46, 7, 210, 21; hgt = y1 - y0 - 2
    f = os.path.join(FONTS, 'AndongKaturi.ttf')         # 엄마까투리체(사용자 지정)
    a_ = crisp_outline('나나시 로프웨이에', f, hgt, orange, peach, stroke=1, aa=True)
    b_ = crisp_outline('어서 오세요', f, hgt, green, peach, stroke=1, aa=True)
    sp = round(hgt * 0.35); total = a_.width + sp + b_.width
    if total > x1 - x0:                                  # 가로 압축(최대 85%), 그래도 넘치면 축소
        kx = max((x1 - x0) / total, 0.85)
        a_ = a_.resize((round(a_.width * kx), a_.height), Image.LANCZOS); b_ = b_.resize((round(b_.width * kx), b_.height), Image.LANCZOS)
        total = a_.width + sp + b_.width
        if total > x1 - x0:
            k2 = (x1 - x0) / total
            a_ = a_.resize((round(a_.width * k2), round(a_.height * k2)), Image.LANCZOS); b_ = b_.resize((round(b_.width * k2), round(b_.height * k2)), Image.LANCZOS)
            sp = round(sp * k2); total = a_.width + sp + b_.width
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; x = round(cx - total / 2)
    im.alpha_composite(a_, (x, round(cy - a_.height / 2))); im.alpha_composite(b_, (x + a_.width + sp, round(cy - b_.height / 2)))
    return clean, im, n, box


def custom_2081(src):
    """어른식 현수막(평평): 회색 「ナナシ島・村役場公認」·초록 「ポックルくんの大人式」 → 「나나시섬・마을 사무소 공인」 / 「포클 군의 어른식」.
    양끝 꽃(분홍)·자주색 테두리는 둔다."""
    o = src.load()
    grey = lambda c: sum(c[:3]) < 560 and abs(c[0] - c[1]) < 40 and not (c[1] > c[0] + 30)
    green = lambda c: c[1] > c[0] + 30
    g1 = _ink(src, grey, (15, 5, 113, 14)); g2 = _ink(src, green, (5, 15, 123, 29))
    cg = Counter(o[x, y][:3] for y in range(5, 14) for x in range(15, 113) if sum(o[x, y][:3]) < 380).most_common(1)[0][0]
    cgr = Counter(o[x, y][:3] for y in range(15, 29) for x in range(5, 123) if o[x, y][1] > o[x, y][0] + 60).most_common(1)[0][0]
    clean, n, _ = comp_erase(src, lambda c: grey(c) or green(c), [(15, 5, 113, 14), (5, 15, 123, 29)],
                             lambda c: sum(c[:3]) < 700 and not (c[0] - c[1] > 40), grow_n=2)
    im = clean.copy()
    put(im, '나나시섬 마을 사무소 공인', 'DoHyeon-Regular.ttf', cg, g1)   # 도현엔 「・」 글리프가 없어 띄어쓰기로
    put(im, '포클 군의 어른식', 'AndongKaturi.ttf', cgr, g2)   # 엄마까투리체(사용자 지정)
    return clean, im, n, (4, 4, 124, 30)


def custom_1692(src):
    """찢어진 어른식 현수막(조각 둘, 기울어짐): 조각마다 초록·회색 글자를 지우고 종이색으로 채운 뒤,
    한글을 일자로 그려 조각 기울기(왼쪽 8.9°, 오른쪽 -4.7°)만큼 줄째로 돌려 원래 글자 가운데에 놓는다."""
    import math
    o = src.load()
    green = lambda c: c[3] > 128 and c[1] > c[0] + 30
    grey = lambda c: c[3] > 128 and abs(c[0] - c[1]) < 8 and abs(c[1] - c[2]) < 8 and sum(c[:3]) < 560
    clean, n, _ = comp_erase(src, lambda c: green(c) or grey(c), [(8, 2, 62, 30), (62, 2, 115, 30)],
                             lambda c: c[3] > 128 and (c[1] > c[0] + 5 or (abs(c[0] - c[1]) < 12 and abs(c[1] - c[2]) < 12 and sum(c[:3]) < 640)), grow_n=1)
    im = clean.copy()
    cgr = Counter(o[x, y][:3] for y in range(32) for x in range(128) if o[x, y][3] > 200 and o[x, y][1] > o[x, y][0] + 60).most_common(1)[0][0]
    cg = (110, 110, 110)
    def cen(pred, x0, x1):
        pts = [(x, y) for x in range(x0, x1) for y in range(32) if pred(o[x, y])]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), pts
    for (x0, x1, ang, big, small) in ((8, 62, 8.9, '포클 군의', '(마을 사무소'), (62, 115, -4.7, '어른식', '공인)')):
        gx, gy, gp = cen(green, x0, x1); sx, sy, spt = cen(grey, x0, x1)
        width = max(p[0] for p in gp) - min(p[0] for p in gp)
        gh = 9                                            # 원본 가나 높이(두 조각 모두 약 9px)
        for text, f, col, cx, cy, h, wmax in ((big, 'AndongKaturi.ttf', cgr, gx, gy, gh, width),   # 엄마까투리체(사용자 지정)
                                              (small, 'DoHyeon-Regular.ttf', cg, sx, sy, 5, width * 0.8)):
            t = render_text(text, os.path.join(FONTS, f), h, col); t = fit(t.crop(ink_box(t)), round(wmax), h)
            t = t.rotate(-ang, resample=Image.BICUBIC, expand=True); t = t.crop(ink_box(t, 20))
            im.alpha_composite(t, (round(cx - t.width / 2), round(cy - t.height / 2)))
    return clean, im, n, (7, 1, 116, 31)


def custom_1670(src):
    """로프웨이 타는 곳(1670·1678 같은 그림): 위 짙은 띠 「ロープウェイ」·아래 밝은 띠 「のりば」를 줄별 띠 색으로 칠하고
    「로프웨이」(작게, 원본 옅은 색) / 「타는 곳」(흰색). 가운데 족자 작은 글씨는 판독 불가라 둠."""
    im = src.copy(); px = im.load(); o = src.load(); n = 0; inks = []
    for (y0, y1) in ((9, 16), (17, 28)):
        pts = []
        for y in range(y0, y1):
            # 띠 색은 글자 없는 양옆(x33~41, x82~93)에서만 잰다 — 글자가 줄을 덮으면 최빈색이 글자색이 됨
            mode = Counter(o[x, y] for x in list(range(33, 42)) + list(range(82, 94))).most_common(1)[0][0]
            for x in range(40, 84):
                if sum(abs(o[x, y][k] - mode[k]) for k in range(3)) > 10:
                    pts.append((x, y)); px[x, y] = mode; n += 1
        inks.append((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts) + 1, max(p[1] for p in pts) + 1))
    clean = im.copy()
    put(im, '로프웨이', 'DoHyeon-Regular.ttf', (170, 196, 196), inks[0])
    put(im, '타는 곳', 'Jua.ttf', (255, 255, 238), inks[1])
    return clean, im, n, (40, 9, 84, 28)


def custom_1045(src):
    """칭칭로리 「親」 표지(초록 바탕 크림 원): 원 안 검은 글자를 크림으로 칠하고 「선」(칭칭로리 용어와 같게)."""
    im = src.copy(); px = im.load(); o = src.load(); n = 0
    cream = Counter(o[x, y] for y in range(64) for x in range(64) if lum(o[x, y]) > 240).most_common(1)[0][0]
    ink = _ink(src, lambda c: lum(c) < 120, (8, 8, 56, 56))
    for y in range(64):
        for x in range(64):
            if (x - 31.5) ** 2 + (y - 31.5) ** 2 <= 26.5 ** 2 and lum(o[x, y]) < 245 and o[x, y] != cream and not (o[x, y][1] > o[x, y][0] + 40):
                px[x, y] = cream; n += 1
    clean = im.copy()
    # 송명(사용자 결정), 크림 원 정중앙(32,32)에서 왼쪽으로 3px(사용자 지시)
    h = ink[3] - ink[1]; t = render_text('선', os.path.join(FONTS, 'SongMyung-Regular.ttf'), h, (0, 0, 0))
    t = fit(t.crop(ink_box(t)), ink[2] - ink[0], h)
    im.alpha_composite(t, (round(32 - t.width / 2) - 3, round(32 - t.height / 2)))   # 왼쪽 5px → 오른쪽 2px 되돌림 = 왼쪽 3px
    return clean, im, n, (4, 4, 60, 60)


def _vbanner(src, box, text, font, dark_thr=60, keep=()):
    """세로 현수막 가운데 큰 글자 줄만 바탕 단색으로 칠하고(양옆 작은 부제는 둠),
    한글을 한 글자씩 같은 칸·같은 크기로 세로로(원본 잉크 위아래 범위를 글자 수만큼 나눔)."""
    o = src.load(); x0, y0, x1, y1 = box
    bg = Counter(o[x, y] for y in range(y0, y1) for x in range(x0, x1) if lum(o[x, y]) > 180).most_common(1)[0][0]   # 바탕은 밝은 색(글자가 줄을 덮으면 최빈색이 글자색이 됨)
    diff = lambda c: sum(abs(c[k] - bg[k]) for k in range(3))
    ink = _ink(src, lambda c: diff(c) > 120, box)
    col = Counter(o[x, y][:3] for y in range(y0, y1) for x in range(x0, x1) if diff(o[x, y]) > 200).most_common(1)[0][0]
    im = src.copy(); px = im.load(); n = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if px[x, y] != bg and diff(px[x, y]) > 12 and not any(a <= x < c and b <= y < d for a, b, c, d in keep):
                px[x, y] = bg; n += 1
    clean = im.copy()
    chars = text.replace(' ', ''); k = len(chars); gap = 1; ix0, iy0, ix1, iy1 = ink
    ch_h = (iy1 - iy0 - gap * (k - 1)) / k; cx = (x0 + x1) / 2
    # 글자마다 잉크 가운데로 맞추면 획 모양 따라 좌우로 흔들린다 → 글꼴 글자 칸(advance 폭) 기준으로 가로를 맞추고, 세로만 잉크로 자른다
    ss = 4; fsz = round(ch_h * ss); fnt = ImageFont.truetype(os.path.join(FONTS, font), fsz); gs = []
    for ch in chars:
        adv = round(fnt.getlength(ch)); asc, desc = fnt.getmetrics()
        cv = Image.new('RGBA', (adv + 2 * ss, asc + desc + 2 * ss), (0, 0, 0, 0))
        ImageDraw.Draw(cv).text((ss, ss), ch, font=fnt, fill=col + (255,))
        bb = ink_box(cv); cv = cv.crop((0, bb[1], cv.width, bb[3]))
        gs.append(cv.resize((max(1, round(cv.width / ss)), max(1, round(cv.height / ss))), Image.LANCZOS))
    # 크기 한도는 실제 잉크 폭으로(글자 칸 폭엔 좌우 여백이 있어 작아짐), 글자 칸 가운데 기준 배치는 그대로
    inkw = max((lambda b: b[2] - b[0])(g.getchannel('A').getbbox()) for g in gs) + 1   # 옅은 가장자리까지 + 축소 반올림 여유
    ky = ch_h / max(g.height for g in gs); kx = min(ky, (x1 - x0 - 1) / inkw)
    for j, g in enumerate(gs):
        g = g.resize((max(1, round(g.width * kx)), max(1, round(g.height * ky))), Image.LANCZOS)
        gx = round(cx - g.width / 2); b = g.getchannel("A").getbbox()   # 옅은 가장자리(알파 1 이상)까지 포함
        if gx + b[0] < x0: gx = x0 - b[0]                 # 잉크가 줄 칸을 벗어나는 글자만 최소한으로 안으로
        if gx + b[2] > x1: gx = x1 - b[2]
        im.alpha_composite(g, (gx, round(iy0 + j * (ch_h + gap) + (ch_h - g.height) / 2)))
    return clean, im, n, box


def custom_76(src):
    """낚시꾼 연어 표지(빨간 판): 별 아래 「鮭」를 판 빨강으로 칠하고 「연어」(송명, 가로 두 글자, 원본 글자색)."""
    box = (5, 45, 43, 74); o = src.load(); red = (213, 40, 41, 255)   # 45줄: 鮭 윗머리 점(별 아래 끝은 44줄까지)
    ink = _ink(src, lambda c: lum(c) < 90, box)
    col = Counter(o[x, y][:3] for y in range(46, 74) for x in range(5, 43) if lum(o[x, y]) < 70).most_common(1)[0][0]
    im = src.copy(); px = im.load(); n = 0
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            if px[x, y] != red:
                px[x, y] = red; n += 1
    clean = im.copy(); put(im, '연어', 'SongMyung-Regular.ttf', col, ink)
    return clean, im, n, box


def _board_title(src, box, text, is_text, erase_pred=None):
    """안내판(나무판) 아래 제목만: 줄별 나무색으로 칠하고 엄마까투리체로 원본 글자색. 작은 머리말·본문·마스코트는 둠."""
    o = src.load()
    col = Counter(o[x, y][:3] for y in range(box[1], box[3]) for x in range(box[0], box[2]) if is_text(o[x, y])).most_common(1)[0][0]
    ink = _ink(src, is_text, box)
    clean, n, _ = _bg_fill_rows(src, box, erase_pred or is_text)   # 지우기는 옅은 번짐까지(erase_pred), 글자 범위는 진한 글자로
    im = clean.copy(); put(im, text, 'AndongKaturi.ttf', col, ink)
    return clean, im, n, box


_green = lambda c: c[1] > c[0] + 30
_navy = lambda c: c[2] > c[0] + 40 and sum(c[:3]) < 300


def custom_1041(src):
    """헬멧 경고문(종이, 붉은 손글씨 두 줄 세로): 오른쪽 줄 「ヘルメット」→「헬멧착용」, 왼쪽 줄 「着用忘れずに」→「잊지말것」.
    네 귀퉁이 압정은 둠. 종이 음영을 번지게 채우고, 나눔손글씨 붓으로 한 글자씩 같은 칸."""
    redp = lambda c: c[0] - c[1] > 25
    o = src.load(); col = Counter(o[x, y][:3] for y in range(4, 60) for x in range(4, 29) if o[x, y][0] - o[x, y][1] > 60).most_common(1)[0][0]
    rink = _ink(src, redp, (18, 4, 29, 42)); link = _ink(src, redp, (4, 4, 17, 60))
    clean, n, _ = inpaint(src, (4, 4, 29, 60), redp, lambda c: c[0] - c[1] > 10)
    im = clean.copy(); f = os.path.join(FONTS, 'AndongKaturi.ttf')   # 11px 줄 폭에선 붓글씨가 뭉개져 엄마까투리체로
    # 두 줄을 같은 글자 크기로: 더 좁은 줄(오른쪽 x18~28)과 칸 높이에 맞는 크기 하나를 둘 다에 적용
    # 사용자 지시: 오른쪽 줄 「헬멧」(ヘルメット), 왼쪽 줄 「착용잊지말것」(着用忘れずに) — 왼쪽 줄 여섯 글자가 칸에 들어가는 크기로 둘 다
    cols = (('헬멧', rink, (18, 29)), ('착용잊지말것', link, (4, 17)))
    size = min(min((iy1 - iy0 - (len(t) - 1)) / len(t), xr[1] - xr[0] - 1) for t, (ix0, iy0, ix1, iy1), xr in cols)
    # 모든 글자를 같은 글꼴 크기로 그리고 같은 배율 하나로 줄인다(글자마다 따로 맞추면 크기가 들쭉날쭉 — 사용자 지적)
    fnt = ImageFont.truetype(f, 64); allg = {}
    for text, _, _ in cols:
        for ch in text:
            g = Image.new('RGBA', (96, 96), (0, 0, 0, 0)); ImageDraw.Draw(g).text((16, 8), ch, font=fnt, fill=col + (255,))
            allg[ch] = g.crop(g.getchannel('A').getbbox())
    sc = min(size / max(g.height for g in allg.values()), min(xb - xa - 1 for _, _, (xa, xb) in cols) / max(g.width for g in allg.values()))
    for text, (ix0, iy0, ix1, iy1), (xa, xb) in cols:
        cx = (xa + xb) / 2; y = iy0
        for ch in text:
            g = allg[ch]; g = g.resize((max(1, round(g.width * sc)), max(1, round(g.height * sc))), Image.LANCZOS)
            im.alpha_composite(g, (round(cx - g.width / 2), round(y + (size - g.height) / 2))); y += size + 1
    return clean, im, n, (4, 4, 29, 60)


def custom_1689(src):
    """메카 텐진 현수막: 검은 손글씨 「テンジンランド」를 지우고(로봇 자주 윤곽선은 둠), 지운 칸은 가장 가까운 원래 색으로
    (줄무늬·로봇 경계가 번지지 않게) → 「텐진 랜드」(나눔손글씨 펜, 검정, 획 굵게)."""
    import numpy as np
    from scipy import ndimage
    a = np.asarray(src).copy(); s3 = a[..., :3].astype(int).sum(2)
    r, g_, b = a[..., 0].astype(int), a[..., 1].astype(int), a[..., 2].astype(int)
    maroon = (r > g_ + 40) & (b > g_ + 15)
    core = s3 < 60
    region = np.zeros_like(core); region[160:250, 5:250] = True
    core &= region
    lowsat = (a[..., :3].max(2).astype(int) - a[..., :3].min(2).astype(int)) < 40   # 검정 번짐(회색) — 흰 줄무늬(합 765)·노랑·하늘색은 해당 없음
    grow = ndimage.binary_dilation(core, iterations=5) & ((s3 < 420) | (lowsat & (s3 < 700))) & ~maroon & region
    m = ndimage.binary_dilation(core | grow, iterations=1) & region   # 가장자리 1칸 여유
    # LaMa(PC 공용 설치, %LOCALAPPDATA%\lama)로 지운 자리를 복원 — 줄무늬·로봇 다리를 이어 그린다(사용자 지시)
    sys.path.insert(0, os.path.expandvars(r'%LOCALAPPDATA%\lama'))
    from lama_inpaint import inpaint as lama
    rgb = lama(a[..., :3].copy(), (m * 255).astype(np.uint8))
    out = a.copy(); out[..., :3] = rgb
    # 로봇(좌우 대칭, 축 x=130) 몸통 가려진 곳: 맞은편 같은 줄이 보이면 그 색을 거울로 가져온다(LaMa는 직선·V자 구조를 못 그림, 사용자 지적)
    # 가운데 줄무늬(x129~133)는 위(191줄)에서 곧게 이어 내린다
    for y in range(140, 221):
        for x in range(96, 171):
            if not m[y, x]:
                continue
            if 122 <= x <= 139 and 192 <= y <= 207:          # 가운데 판(윤곽·줄무늬 모두 세로로 곧음): 191줄에서 그대로 내림
                out[y, x] = a[191, x]
                continue
            sx = 260 - x
            if 0 <= sx < 256 and not m[y, sx] and not core[y, sx]:
                out[y, x] = a[y, sx]
    clean = Image.fromarray(out, 'RGBA'); n = int(m.sum())
    ys, xs = np.where(core); ink = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    im = clean.copy(); f = os.path.join(FONTS, 'NanumPenScript-Regular.ttf')
    t = render_text('텐진 랜드', f, ink[3] - ink[1], (0, 0, 0), stroke=3, stroke_color=(0, 0, 0)); t = fit(t.crop(ink_box(t)), ink[2] - ink[0], ink[3] - ink[1])
    im.alpha_composite(t, (round((ink[0] + ink[2]) / 2 - t.width / 2), round((ink[1] + ink[3]) / 2 - t.height / 2)))
    return clean, im, n, (5, 160, 250, 250)


CUSTOM.update({'2290': ('꽃밭', lambda s: _board_title(s, (44, 46, 74, 61), '꽃밭', lambda c: c[0] > c[1] + 80 and c[1] < 80, lambda c: c[1] < 118 and c[0] > c[1] + 50)),   # 나무(G≈150)는 제외, 짙은 빨강·번짐만
               '1041': ('헬멧 / 착용잊지말것', custom_1041), '1689': ('텐진 랜드', custom_1689),
               '1890': ('명소 발견!', lambda s: _board_title(s, (38, 48, 91, 61), '명소 발견!', _green, lambda c: c[1] > c[0] + 4)),
               '1891': ('낚시터', lambda s: _board_title(s, (43, 48, 81, 61), '낚시터', _green, lambda c: c[1] > c[0] + 4)),
               '2274': ('요노하테', lambda s: _board_title(s, (41, 47, 84, 60), '요노하테', _navy)),
               '2239': ('섬안클린업주간', lambda s: _vbanner(s, (8, 5, 21, 111), '섬안클린업주간', 'DoHyeon-Regular.ttf')),   # x20 잔여까지 지움(사용자 지시)
               '2240': ('바른예절은모두의매너', lambda s: _vbanner(s, (9, 3, 26, 110), '바른예절은모두의매너', 'AndongKaturi.ttf')),   # 엄마까투리체(사용자 지정)
               '76': ('연어', custom_76), '1670': ('로프웨이 / 타는 곳', custom_1670), '1678': ('로프웨이 / 타는 곳', custom_1670), '1045': ('선', custom_1045), '1692': ('포클 군의 어른식 (찢어진 현수막)', custom_1692), '2081': ('나나시섬 마을 사무소 공인 / 포클 군의 어른식', custom_2081), '2176': ('승차권 판매기 / 어린이 / 어른', custom_2176), '2189': ('뷰티풀 나나시', custom_2189),
               '1379': ('나나시 로프웨이에 어서 오세요', custom_1379), '2032': ('메이어', custom_2032), '1871': ('꺼내는 곳', custom_1871), '1875': ('준비 중', custom_1875), '1985': ('발매 중! / 나나시섬 복권', custom_1985), '1986': ('5일 남음 … 오늘 발표', custom_1986),
               '2154': ('나나시 / 관광', custom_2154), '1824': ('차', custom_1824), '1828': ('차', custom_1828), '251': ('차', custom_251), '1544': ('촌장실 / 자료실 / 전망대', custom_1544), '2281': ('차 / 이쪽', custom_2281),
               '2283': ('염색합니다 / 이쪽', custom_2283), '1378': ('발밑주의', custom_1378),
               '2320': ('원숭이 주의', lambda s: _label(s, '원숭이 주의')),
               '2322': ('양아치 앉기 주의', lambda s: _label(s, '양아치 앉기 주의', squeeze=0.7)),
               '2165': ('타오', custom_2165), '2040': ('메트', custom_2040), '2099': ('포클', custom_2099), '571': ('어서 오세요', custom_571), '846': ('위험 주의', custom_846), '2050': ('안전 제일', custom_2050)})


if __name__ == '__main__':
    ids = sys.argv[2:] or list(SPEC)
    preview([i for i in ids if i in SPEC]) if any(i in SPEC for i in ids) else None
    preview_custom([i for i in ids if i in CUSTOM])
