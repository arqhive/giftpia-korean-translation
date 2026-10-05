"""6단계 첫 묶음(메뉴 탭 12장 + 타이틀 로고 「ギフトピア」 8장) 지우기·한글 배치.

  python tools/gfx_g1.py preview   → work/gfx/g1/ 에 안별 결과 PNG + 비교 시트

- 탭: 글자 상자 안에서 바탕보다 밝은 픽셀(글자)만 그 줄의 바탕색으로 채운 뒤, 같은 왼쪽 시작점에 한글을 그린다.
- 로고: 「ギフトピア」 영역(™ 왼쪽, y≥95)만 투명으로 지우고, 글자별 원래 색 + 자주색 테두리로 「기프트피아」를 그린다.
"""
import csv
import os
import statistics
from collections import Counter
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
G = os.path.join(ROOT, 'work', 'gfx_survey')
OUT = os.path.join(ROOT, 'work', 'gfx', 'g1')
FONTS = os.path.join(ROOT, 'tools', 'fonts')
TAB_FONT = 'Jua.ttf'                      # 주아(사용자 결정 10/1, OFL)
LOGO_FONT = 'TmoneyRoundWindExtraBold.ttf'  # 티머니 둥근바람(사용자 지정)

TABS = {  # id: (번역, 밝음?)
    '2377': ('최근', 1), '2378': ('먹을 것', 1), '2379': ('쓸 것', 1), '2380': ('그 밖', 1), '2381': ('소원 구슬', 1), '2382': ('사진', 1),
    '2383': ('최근', 0), '2384': ('먹을 것', 0), '2385': ('쓸 것', 0), '2386': ('그 밖', 0), '2387': ('소원 구슬', 0), '2388': ('사진', 0),
}
# 밝은 탭 108x32 / 어두운 탭 91x25: 글자 상자(x0, y0, x1, y1), 글자 색, 글자로 볼 밝기 하한, 글자 높이(px)
TAB_BOX = {1: ((6, 3, 96, 24), (255, 255, 255), 120, 17), 0: ((6, 5, 78, 20), (148, 149, 148), 100, 12)}
TAB_ANCHOR = {1: (15.0, 12), 0: (12.0, 10)}   # (잉크 세로 가운데, 잉크 왼쪽 x)
LOGOS = ['2513', '2517', '2518', '2519', '2520', '2521', '2522', '2523']
LOGO_BOX = (138, 95, 343, 137)
TM = (340, 123)                         # ™: x≥340 이면서 y≥123 은 남긴다
KANA_COLORS = [(222, 36, 41), (255, 230, 74), (180, 218, 57), (139, 214, 230), (156, 109, 180)]
OUTLINE = (69, 18, 49)


def rows():
    return {r['n']: r for r in csv.DictReader(open(os.path.join(ROOT, 'translation', 'graphics_list.csv'), encoding='utf-8-sig'))}


def lum(p):
    return (p[0] * 3 + p[1] * 6 + p[2]) / 10


def render_text(text, font, height_px, color, ss=4, stroke=0, stroke_color=None):
    """한글 글자 높이(받침 포함 실제 잉크 높이)가 height_px 가 되도록 크기를 맞춰 RGBA 로 그린다(4배로 그려 축소)."""
    size = height_px * ss
    for _ in range(4):
        f = ImageFont.truetype(font, size)
        l, t, r, b = f.getbbox('한글', stroke_width=0)
        size = max(4, round(size * height_px * ss / (b - t)))
    f = ImageFont.truetype(font, size)
    l, t, r, b = f.getbbox(text, stroke_width=stroke * ss)
    im = Image.new('RGBA', (r - l + 2 * ss, b - t + 2 * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((-l + ss, -t + ss), text, font=f, fill=color + (255,),
                            stroke_width=stroke * ss, stroke_fill=(stroke_color or color) + (255,))
    w, h = im.size
    return im.resize((max(1, round(w / ss)), max(1, round(h / ss))), Image.LANCZOS)


def ink_box(im, thr=40):
    """알파 기준 잉크 상자."""
    return im.getchannel('A').point(lambda v: 255 if v > thr else 0).getbbox()


def tab_body(src, light):
    """탭 몸통(글자 칸)을 단색으로 채운 그림, 채운 색, 원본 글자의 잉크 상자를 돌려준다.
    줄마다 양 끝에서 안쪽으로 테두리(바탕색과 밝기 차 >6)를 건너뛰고, 처음 만난 바탕색 픽셀 사이를 전부 채운다."""
    im = src.copy(); px = im.load(); w, h = im.size
    (x0, y0, x1, y1), color, thr, hpx = TAB_BOX[light]
    sample = [px[x, y] for y in range(y1, y1 + 3) for x in range(x0 + 4, x1 - 4) if px[x, y][3]]
    base = Counter(round(lum(c)) for c in sample).most_common(1)[0][0]
    # 채움 색: 그림 전체에서 바탕 밝기(±3)인 색 중 가장 흔한 것(압축 색 번짐으로 생긴 보랏빛 등은 소수라 빠진다)
    fill = Counter(px[x, y] for y in range(h) for x in range(w)
                   if px[x, y][3] > 200 and abs(lum(px[x, y]) - base) <= 3).most_common(1)[0][0]
    isbody = lambda c: c[3] > 200 and abs(lum(c) - base) <= 4
    # 원본 글자 잉크 상자(바탕보다 25 이상 밝은 픽셀)
    xs, ys = [], []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if px[x, y][3] and lum(px[x, y]) > base + 25:
                xs.append(x); ys.append(y)
    ink = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    rows = [y for y in range(h) if sum(1 for x in range(w) if isbody(px[x, y])) >= 10]
    n = 0
    for y in range(rows[0], rows[-1] + 1):
        # 바탕색이 3칸 이어지는 곳부터를 몸통으로 본다(테두리 바깥의 우연한 바탕색 1칸에 속지 않게)
        run = lambda x, d: all(0 <= x + d * k < w and isbody(px[x + d * k, y]) for k in range(3))
        l = next((x for x in range(w) if run(x, 1)), None)
        r = next((x for x in range(w - 1, -1, -1) if run(x, -1)), None)
        if l is None:
            continue
        for x in range(l, r + 1):
            if px[x, y] != fill:
                px[x, y] = fill; n += 1
    return im, fill, ink, n


def tab(src, text, light, font):
    clean, fill, ink, n = tab_body(src, light)
    (x0, y0, x1, y1), color, thr, hpx = TAB_BOX[light]
    t = render_text(text, font, hpx, color)
    bb = ink_box(t); t = t.crop(bb)
    maxw = x1 - TAB_ANCHOR[light][1] - 2
    if t.width > maxw:                                    # 가로 압축(최대 85%), 그래도 넘치면 축소
        t = t.resize((max(maxw, round(t.width * 0.85)), t.height), Image.LANCZOS)
        if t.width > maxw:
            t = t.resize((maxw, round(t.height * maxw / t.width)), Image.LANCZOS)
    im = clean.copy()
    # 세로: 원본 글자 잉크의 가운데에 한글 잉크의 가운데를 맞춘다 / 가로: 원본 잉크 왼쪽 끝에서 시작
    # 같은 종류 탭은 모두 같은 자리: 원본 6장 글자 잉크의 세로 가운데·왼쪽 끝 평균(밝은 탭 15.0/12, 어두운 탭 12.0/10)
    cy, lx = TAB_ANCHOR[light]
    im.alpha_composite(t, (lx, round(cy - t.height / 2)))
    return clean, im, n


def logo(src, font, stroke=5):
    im = src.copy(); px = im.load()
    x0, y0, x1, y1 = LOGO_BOX
    erased = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if px[x, y][3] and not (x >= TM[0] and y >= TM[1]):
                px[x, y] = (0, 0, 0, 0); erased += 1
    clean = im.copy()
    # 원래 가나 한 글자 칸 약 40px 간격, 글자 높이 약 27px(테두리 제외)
    # 글자마다 세로 잉크 가운데를 한 줄(원본 가나 테두리 포함 범위 y99~136의 가운데)에 맞추고,
    # 가로는 원본 가나 범위(x143~339) 안에서 글자 사이 간격을 똑같이 나눈다.
    glyphs = []
    # 납작한 글자(프·트, 원래 잉크 높이 21~22px)는 「기」(26px)의 위아래 끝을 넘지 않게 23px 로만 키운다
    target = ink_box(render_text('기', font, 27, (255, 255, 255)))
    target = target[3] - target[1] - 3
    for ch, c in zip('기프트피아', KANA_COLORS):
        size = 27
        if ch in '프트':                                   # 잉크 높이가 정확히 target 이 되는 크기를 찾는다
            size = min(range(27, 41), key=lambda z: abs((lambda b: b[3] - b[1])(ink_box(render_text(ch, font, z, c))) - target))
        g = render_text(ch, font, size, OUTLINE, stroke=stroke)
        f = render_text(ch, font, size, c)
        layer = Image.new('RGBA', g.size, (0, 0, 0, 0))
        layer.alpha_composite(g)
        layer.alpha_composite(f, ((g.width - f.width) // 2, (g.height - f.height) // 2))
        layer = layer.crop(ink_box(layer, 10))
        if ch in '프트' and layer.height != 36:            # 정수 글자 크기로는 1px 차가 남아, 테두리 포함 36px 로 똑같이 맞춘다
            layer = layer.resize((round(layer.width * 36 / layer.height), 36), Image.LANCZOS)
        glyphs.append(layer)
    left, right, cy = 143, 339, (99 + 136) / 2
    gap = (right - left - sum(g.width for g in glyphs)) / (len(glyphs) - 1)
    print('로고 글자 간격 %.1fpx, 폭' % gap, [g.width for g in glyphs], '높이', [g.height for g in glyphs])
    x = left
    top = round(cy - max(g.height for g in glyphs) / 2)   # 다섯 글자 윗끝을 한 줄에 맞춘다(사용자 지시)
    for g in glyphs:
        im.alpha_composite(g, (round(x), top))
        x += g.width + gap
    return clean, im, erased


def scale(im, k, bg=(58, 58, 58)):
    b = Image.new('RGBA', im.size, bg + (255,)); b.alpha_composite(im)
    return b.resize((im.width * k, im.height * k), Image.NEAREST)


def label(img, text, h=22):
    f = ImageFont.truetype(os.path.join(FONTS, 'NanumSquareRoundB.ttf'), 15)
    out = Image.new('RGBA', (img.width, img.height + h), (36, 36, 36, 255))
    ImageDraw.Draw(out).text((4, 3), text, font=f, fill=(230, 230, 230, 255))
    out.alpha_composite(img, (0, h))
    return out


def grid(cells, cols, gap=10, bg=(36, 36, 36, 255)):
    w = max(c.width for c in cells); h = max(c.height for c in cells)
    rows_ = (len(cells) + cols - 1) // cols
    s = Image.new('RGBA', (cols * w + (cols + 1) * gap, rows_ * h + (rows_ + 1) * gap), bg)
    for i, c in enumerate(cells):
        s.alpha_composite(c, (gap + (i % cols) * (w + gap), gap + (i // cols) * (h + gap)))
    return s


def preview():
    R = rows(); os.makedirs(OUT, exist_ok=True)
    tab_font = os.path.join(FONTS, TAB_FONT)
    has_tab_font = os.path.exists(tab_font)
    cells = []
    for i, (text, light) in TABS.items():
        src = Image.open(os.path.join(G, R[i]['png'])).convert('RGBA')
        if has_tab_font:
            clean, out, n = tab(src, text, light, tab_font)
            out.save(os.path.join(OUT, '%s_ko.png' % i))
        else:
            clean, _, _, n = tab_body(src, light); out = None
        clean.save(os.path.join(OUT, '%s_clean.png' % i))
        row = [label(scale(src, 4), '#%s 원본 %s' % (i, R[i]['text'].split(' ')[0])), label(scale(clean, 4), '지운 뒤 (%d px)' % n)]
        row.append(label(scale(out, 4), '한글: %s' % text) if out else label(scale(clean, 4), '(글꼴 대기)'))
        cells += [c.resize((108 * 4, c.height * 108 * 4 // c.width), Image.NEAREST) if c.width != 108 * 4 else c for c in row]
    grid(cells, 3).save(os.path.join(OUT, 'sheet_tabs.png'))
    cells = []
    for i in LOGOS:
        src = Image.open(os.path.join(G, R[i]['png'])).convert('RGBA')
        clean, out, n = logo(src, os.path.join(FONTS, LOGO_FONT))
        out.save(os.path.join(OUT, '%s_ko.png' % i)); clean.save(os.path.join(OUT, '%s_clean.png' % i))
        if i in ('2513', '2523'):
            crop = (120, 0, 478, 137)
            cells += [label(scale(src.crop(crop), 2), '#%s 원본' % i), label(scale(clean.crop(crop), 2), '지운 뒤 (%d px)' % n),
                      label(scale(out.crop(crop), 2), '한글: 티머니 둥근바람')]
    grid(cells, 3).save(os.path.join(OUT, 'sheet_logo.png'))
    print('저장:', OUT, '탭 글꼴', '있음' if has_tab_font else '없음(지우기만)')


if __name__ == '__main__':
    preview()
