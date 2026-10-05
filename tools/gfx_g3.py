"""6단계 셋째 묶음(책·도감·신문·포스터 등) 지우기·한글 배치. gfx_g2 의 도구를 그대로 쓴다.

  python tools/gfx_g3.py preview 번호...   → work/gfx/g3/
"""
import os
import sys
from collections import Counter

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx_g2 as g2
from gfx_g2 import G, FONTS, lum, render_text, ink_box, scale, label, grid, fit, crisp_outline, changed_outside

OUT = os.path.join(g2.ROOT, 'work', 'gfx', 'g3')
sys.path.insert(0, os.path.expandvars(r'%LOCALAPPDATA%\lama'))


def lama_fill(src, mask, k=8):
    """mask(bool HxW) 자리를 LaMa(PC 공용 설치)로 채운다. 알파는 원본 그대로.
    LaMa 는 큰 그림으로 배운 모델이라 64px 그림을 그대로 넣으면 뭉개진다 → k배(최근접)로 키워 채운 뒤 BOX 로 줄여 마스크 자리만 쓴다."""
    from lama_inpaint import inpaint
    a = np.asarray(src).copy(); h, w = mask.shape
    big = np.asarray(Image.fromarray(a[..., :3]).resize((w * k, h * k), Image.NEAREST))
    bm = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).resize((w * k, h * k), Image.NEAREST))
    r = inpaint(big.copy(), bm)
    sm = np.asarray(Image.fromarray(r).resize((w, h), Image.BOX))
    a[..., :3][mask] = sm[mask]
    return Image.fromarray(a, 'RGBA')


def nearest_fill(src, mask):
    """마스크 자리를 가장 가까운 마스크 밖 픽셀 색으로(단색 말풍선·띠 등)."""
    from scipy import ndimage
    a = np.asarray(src).copy()
    _, (iy, ix) = ndimage.distance_transform_edt(mask, return_indices=True)
    a[mask] = a[iy[mask], ix[mask]]
    return Image.fromarray(a, 'RGBA')


def outlined(text, font, h, fill, edge, stroke=2):
    t = crisp_outline(text, os.path.join(FONTS, font), h, fill, edge, stroke=stroke, aa=True)
    return t


def custom_lottery(src, num):
    """복권 당첨 포스터(1~3등): 「N等」·「おめでとう」(채움색 + 짙은 테두리)를 LaMa 로 지우고 「N등」·「축하합니다」.
    오른쪽 포클 그림은 둔다(「う」 오른쪽 아래가 셔츠에 닿는 곳: 47줄 아래는 x74까지만)."""
    from scipy import ndimage
    a = np.asarray(src); s3 = a[..., :3].astype(int).sum(2)
    region = np.zeros(s3.shape, bool); region[8:37, 4:56] = True; region[37:47, 4:78] = True; region[47:55, 4:75] = True
    dark = (s3 < 330) & region
    m = ndimage.binary_dilation(dark, iterations=3) & region
    clean = lama_fill(src, m)
    o = src.load()
    edge = Counter(o[x, y][:3] for y in range(8, 55) for x in range(4, 70) if sum(o[x, y][:3]) < 250).most_common(1)[0][0]
    # 채움색: 「N」 획 안쪽(테두리 안) — 큰 글자 줄에서 어둡지도 바탕도 아닌 가장 흔한 색
    ys, xs = np.where(dark[8:37, 4:56]); x0, x1, y0, y1 = xs.min() + 4, xs.max() + 5, ys.min() + 8, ys.max() + 9
    inner = ndimage.binary_erosion(ndimage.binary_fill_holes(ndimage.binary_dilation(dark, iterations=1)), iterations=2) & ~dark & region
    fillc = Counter(tuple(a[y, x, :3]) for y, x in zip(*np.where(inner[8:37] if False else inner)) if 8 <= y < 37).most_common(1)[0][0]
    im = clean.copy(); font = 'Jua.ttf'
    big = outlined('%d등' % num, font, y1 - y0 - 4, fillc, edge); big = fit(big, x1 - x0 + 2, y1 - y0 + 2)
    im.alpha_composite(big, (round((x0 + x1) / 2 - big.width / 2), round((y0 + y1) / 2 - big.height / 2)))
    ys2, xs2 = np.where(dark[37:55, 4:78]); a0, a1, b0, b1 = xs2.min() + 4, xs2.max() + 5, ys2.min() + 37, ys2.max() + 38
    sm = outlined('축하합니다', font, b1 - b0 - 4, fillc, edge); sm = fit(sm, a1 - a0 + 2, b1 - b0 + 2)
    im.alpha_composite(sm, (round((a0 + a1) / 2 - sm.width / 2), round((b0 + b1) / 2 - sm.height / 2)))
    return clean, im, int(m.sum()), (3, 7, 79, 56)


def custom_shiori(src, text='섬 안내서'):
    """책자 「島のしおり」(64x64, 흰 알약 띠 안 5px 갈색 글자): 띠 안 글자 픽셀(13~18줄)을 위·아래 줄 색 세로 보간으로 지우고
    갈무리7(8px 비트맵)로 같은 갈색 글자를 띠 가운데에 놓는다."""
    from PIL import ImageDraw, ImageFont
    a = np.asarray(src).copy(); v = a[..., :3].astype(int).sum(2) // 3
    xs = np.where((v[11:20] >= 240).any(0))[0]; L, Rr = xs.min(), xs.max()          # 띠 흰 구간(11~19줄 중 가장 넓은 폭)
    # 띠는 가로 띠라 세로로만 색이 변한다 → 13~18줄에서 위(12줄)·아래(19줄) 색과 다른 픽셀을 글자로 보고 두 줄 색을 세로 보간
    c3 = a[..., :3].astype(int); m = np.zeros(v.shape, bool); out = a.copy()
    for x in range(L - 3, Rr + 4):
        top, bot = c3[12, x], c3[19, x]
        for y in range(13, 19):
            c = c3[y, x]
            if min(np.abs(c - top).sum(), np.abs(c - bot).sum()) > 45 and c.sum() < min(top.sum(), bot.sum()) - 45:   # 글자는 띠보다 어둡다(둥근 끝은 가운데가 더 밝음)
                m[y, x] = True
                t = (y - 12) / 7
                out[y, x, :3] = (top * (1 - t) + bot * t).round()
    ink = Counter(tuple(a[y, x, :3]) for y, x in zip(*np.where(m & (v < 70)))).most_common(1)[0][0]
    clean = Image.fromarray(out, 'RGBA')
    cx = (L + Rr + 1) / 2; cy = 15.5
    ft = ImageFont.truetype(os.path.join(FONTS, 'Galmuri7.ttf'), 8)
    t = Image.new('L', (80, 20)); d = ImageDraw.Draw(t); d.fontmode = '1'; d.text((2, 2), text, font=ft, fill=255)
    ty, tx = np.where(np.asarray(t) > 0)
    w, h = tx.max() - tx.min() + 1, ty.max() - ty.min() + 1
    ox, oy = round(cx - w / 2), round(cy - h / 2)
    im = np.asarray(clean).copy()
    for y, x in zip(ty, tx):
        im[oy + y - ty.min(), ox + x - tx.min()] = (*ink, 255)
    return clean, Image.fromarray(im, 'RGBA'), int(m.sum()), (L - 4, 11, Rr + 5, 20)

def narrow_text(text, font, h, maxw, fillc, edgec=None, stroke=1):
    """글자 높이 h 로 그린 뒤 가로만 maxw 까지 좁히고(원본 세로로 긴 글자 느낌), edgec 가 있으면 stroke 칸 테두리."""
    from PIL import ImageFilter
    g = render_text(text, os.path.join(FONTS, font), h, fillc)
    if g.width > maxw:
        g = g.resize((maxw, g.height), Image.LANCZOS)
    if edgec is None:
        return g
    pad = stroke + 1
    m = Image.new('L', (g.width + pad * 2, g.height + pad * 2), 0)
    m.paste(g.getchannel('A').point(lambda v: 255 if v >= 80 else 0), (pad, pad))
    for _ in range(stroke):
        m = m.filter(ImageFilter.MaxFilter(3))
    out = Image.new('RGBA', m.size, (0, 0, 0, 0))
    out.paste(Image.new('RGBA', m.size, tuple(edgec) + (255,)), (0, 0), m)
    out.alpha_composite(g, (pad, pad))
    return out


def custom_shiori_big(src, covers, flat=None):
    """책자 표지 「島のしおり」(흰 테두리 갈색 굵은 글자, 588: 2권·1093: 3권): 표지마다 글자+흰 테두리를 LaMa 로 지우고
    엄마까투리체 「섬 안내서」를 원본 글자 칸(높이·폭)에 맞춰 세로로 긴 꼴로 놓는다. covers = [(x0, x1)], 글자 줄 9~28."""
    from scipy import ndimage
    a = np.asarray(src); c3 = a[..., :3].astype(int)
    brown = (c3[..., 0] - c3[..., 2] > 60) & (c3.sum(2) < 400)
    region = np.zeros(brown.shape, bool)
    for x0, x1 in covers: region[8:31, x0:x1] = True
    core = brown & region
    m = ndimage.binary_dilation(core, iterations=3) & region      # 흰 테두리(1~2칸)+번짐까지
    clean = lama_fill(src, m)
    ca = np.asarray(clean).copy()
    for (x0, x1), how in zip(covers, flat or ()):                # 단색 표지(분홍·초록): 세로로 색이 같으니 칸마다 글자 줄 위(3~7)·아래(31~34) 원본 최빈색으로
        if how:
            cc = {}
            for x in range(x0, x1):
                cc[x] = Counter(tuple(a[y, x]) for y in list(range(3, 8)) + list(range(31, 35))).most_common(1)[0][0]   # 글자 줄(8~30) 밖에서만
            for x in range(x0 + 1, x1 - 1):                       # 해·잎 끝이 걸린 한 칸만 튀면 양옆 색으로
                d = lambda p, q: np.abs(np.subtract(p[:3], q[:3], dtype=int)).sum()
                if d(cc[x - 1], cc[x + 1]) <= 8 and d(cc[x - 1], cc[x]) > 8:
                    cc[x] = cc[x - 1]
            for x in range(x0, x1):
                c = cc[x]; col = m[:, x].copy()
                ca[col, x] = c
                for y in range(6, 30):                            # 마스크 바로 밖에 남은 흰 테두리 점도 같은 색으로
                    if not col[y] and np.abs(a[y, x, :3].astype(int) - c[:3]).sum() > 30:
                        ca[y, x] = c; m[y, x] = True
    clean = Image.fromarray(ca, 'RGBA')
    fillc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(core))).most_common(1)[0][0]
    glow = ndimage.binary_dilation(core, iterations=1) & ~core & region & (c3.sum(2) > 690)
    edgec = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(glow))).most_common(1)[0][0]
    im = clean.copy()
    for x0, x1 in covers:
        ys, xs = np.where(core[:, x0:x1]); bx0, bx1, by0, by1 = xs.min() + x0, xs.max() + x0 + 1, ys.min(), ys.max() + 1
        t = narrow_text('섬 안내서', 'AndongKaturi.ttf', by1 - by0, bx1 - bx0, fillc, edgec, 1)
        im.alpha_composite(t, (round((bx0 + bx1) / 2 - t.width / 2), round((by0 + by1) / 2 - t.height / 2)))
    return clean, im, int(m.sum()), (0, 6, a.shape[1], 32)


def custom_tyousha_news(src):
    """책자 「村庁舎だより」(흰 말풍선 안 빨간 붓글씨 2줄): 빨간 글자를 LaMa 로 지우고 엄마까투리체 「사무소」/「소식」.
    아래 「23~30」 숫자·줄 무늬는 둔다."""
    from scipy import ndimage
    a = np.asarray(src); c3 = a[..., :3].astype(int)
    red = (c3[..., 0] - c3[..., 2] > 100)
    pinkish = (c3[..., 0] - c3[..., 2] > 10) & (c3[..., 0] - c3[..., 1] > 10)       # 글자 둘레 연분홍 번짐(아주 옅은 것까지)
    region = np.zeros(red.shape, bool); region[5:29, 3:33] = True
    core = red & region
    m = (ndimage.binary_dilation(core, iterations=1) | pinkish) & region
    clean = nearest_fill(src, m)
    ca = np.asarray(clean).copy()                                                 # 말풍선 안(가까운 색이 흰빛)은 순백으로
    wh = m & (ca[..., :3].min(2) > 200); ca[wh, :3] = 255
    clean = Image.fromarray(ca, 'RGBA')
    fillc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(core))).most_common(1)[0][0]
    im = clean.copy()
    for (y0, y1), txt in (((7, 17), '사무소'), ((18, 28), '소식')):
        ys, xs = np.where(core[y0:y1]); bx0, bx1, by0, by1 = xs.min(), xs.max() + 1, ys.min() + y0, ys.max() + y0 + 1
        t = narrow_text(txt, 'AndongKaturi.ttf', by1 - by0, bx1 - bx0, fillc)
        im.alpha_composite(t, (round((bx0 + bx1) / 2 - t.width / 2), round((by0 + by1) / 2 - t.height / 2)))
    return clean, im, int(m.sum()), (2, 4, 34, 30)

def vfill(a, m, ytop=None, ybot=None):
    """마스크 자리를 같은 열에서 마스크 바로 위·아래 픽셀 색으로 세로 보간(단색·가로 띠 바탕용). a: RGBA 배열(수정됨)"""
    H = m.shape[0]
    for x in np.where(m.any(0))[0]:
        y = 0
        while y < H:
            if not m[y, x]:
                y += 1; continue
            y0 = y
            while y < H and m[y, x]: y += 1
            t0, t1 = max(y0 - 1, 0), min(y, H - 1)
            top, bot = a[t0, x, :3].astype(float), a[t1, x, :3].astype(float)
            for yy in range(y0, y):
                t = (yy - t0) / max(t1 - t0, 1)
                a[yy, x, :3] = (top * (1 - t) + bot * t).round()
    return a


def custom_muranokoe(src):
    """책자 「村の声」(주황 바탕 빨간 붓글씨): 글자를 LaMa(8배)로 지우고 연천 허목체 「마을의 소리」."""
    from scipy import ndimage
    a = np.asarray(src).copy(); c3 = a[..., :3].astype(int)
    region = np.zeros(c3.shape[:2], bool); region[3:20, 3:62] = True
    core = (c3[..., 0] - c3[..., 1] > 120) & region
    m = ndimage.binary_dilation((c3[..., 0] - c3[..., 1] > 95) & region, iterations=1) & region
    fillc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(core))).most_common(1)[0][0]
    clean = lama_fill(src, m)                                       # 주황 바탕이 블록마다 달라 세로 보간은 줄무늬 → LaMa 8배
    ys, xs = np.where(core); bx0, bx1, by0, by1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    t = narrow_text('마을의 소리', 'YeoncheonHeomok.ttf', by1 - by0, bx1 - bx0, fillc)
    im = clean.copy(); im.alpha_composite(t, (round((bx0 + bx1) / 2 - t.width / 2), round((by0 + by1) / 2 - t.height / 2)))
    return clean, im, int(m.sum()), (2, 2, 63, 21)


def custom_shiryou(src, num, blur=0.5):
    """책장 표지 「資料N」(32x16): 테두리 안쪽(3~13줄, 2~29열)을 전부 흰색으로 칠하고 갈무리9 「자료N」(원본 남색, 도트).
    「자료」는 여섯 장 모두 같은 자리(「자료2」를 가운데 맞춘 위치)에 둔다."""
    from PIL import ImageDraw, ImageFont
    a = np.asarray(src).copy(); c3 = a[..., :3].astype(int)
    ink = Counter(tuple(c3[y, x]) for y in range(4, 13) for x in range(3, 31) if c3[y, x].sum() < 260).most_common(1)[0][0]
    m = np.zeros(c3.shape[:2], bool); m[3:14, 2:30] = True
    m &= (a[..., :3] != 255).any(2)
    a[3:14, 2:30, :3] = 255
    clean = Image.fromarray(a, 'RGBA')
    ft = ImageFont.truetype(os.path.join(FONTS, 'Galmuri9.ttf'), 10)

    def bits(txt):
        t = Image.new('L', (60, 20)); d = ImageDraw.Draw(t); d.fontmode = '1'; d.text((2, 2), txt, font=ft, fill=255)
        return np.asarray(t) > 0
    ref = bits('자료2'); ry, rx = np.where(ref)
    ox = round(16 - (rx.max() - rx.min() + 1) / 2) - rx.min(); oy = round(8.5 - (ry.max() - ry.min() + 1) / 2) - ry.min()
    from PIL import ImageFilter
    lay = Image.new('L', clean.size, 0); lp = lay.load()
    for y, x in zip(*np.where(bits('자료%d' % num))):
        lp[int(ox + x), int(oy + y)] = 255
    core = np.asarray(lay).astype(float) / 255
    halo = np.asarray(lay.filter(ImageFilter.GaussianBlur(0.8))).astype(float) / 255
    al = np.maximum(core, np.clip(halo * blur * 2.5, 0, blur))[..., None]   # 원본처럼: 획은 진하게, 둘레만 연한 번짐(최대 blur)
    al[:3] = 0; al[14:] = 0; al[:, :2] = 0; al[:, 30:] = 0     # 테두리 밖은 그대로
    im = a.copy().astype(float)
    im[..., :3] = im[..., :3] * (1 - al) + np.array(ink) * al
    return clean, Image.fromarray(im.round().astype(np.uint8), 'RGBA'), int(m.sum()), (2, 3, 30, 14)

def custom_hebionna(src):
    """TV 화면 「恐怖!! / へび女」(어두운 둥근 그러데이션 위 빨간 손글씨, 「び」가 파란 뱀과 겹침):
    빨간 글자만 LaMa 8배로 지우고(뱀 픽셀은 마스크에서 뺌) 연천 허목체 「공포!!」/「뱀 여자」."""
    from scipy import ndimage
    a = np.asarray(src); c3 = a[..., :3].astype(int)
    red = (c3[..., 0] - c3[..., 1] > 20) & (c3[..., 0] > 60)
    region = np.zeros(red.shape, bool); region[2:27, 8:60] = True
    core = (c3[..., 0] - c3[..., 1] > 50) & region
    blue = (c3[..., 2] - c3[..., 0] > 40)
    m = ndimage.binary_dilation(red & region, iterations=1) & region & ~blue      # 뱀(파랑) 픽셀은 두고 빨간 글자만
    clean = lama_fill(src, m)
    fillc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(core))).most_common(1)[0][0]
    im = clean.copy()
    for (y0, y1), txt in (((2, 13), '공포!!'), ((13, 27), '뱀 여자')):
        ys, xs = np.where(core[y0:y1]); bx0, bx1, by0, by1 = xs.min(), xs.max() + 1, ys.min() + y0, ys.max() + y0 + 1
        t = narrow_text(txt, 'YeoncheonHeomok.ttf', by1 - by0, bx1 - bx0, fillc)
        im.alpha_composite(t, (round((bx0 + bx1) / 2 - t.width / 2), round((by0 + by1) / 2 - t.height / 2)))
    return clean, im, int(m.sum()), (7, 1, 61, 28)


def custom_desune(src):
    """TV 자막 띠 「デスネ〜・カンパニー」(64x16 RGBA8, 투명 바탕에 흰 글자, 색=알파): 전부 투명으로 지우고 도현 「데스네~ 컴퍼니」."""
    a = np.asarray(src).copy(); m = a[..., 3] > 0
    a[...] = 0
    clean = Image.fromarray(a, 'RGBA')
    t = narrow_text('데스네~ 컴퍼니', 'DoHyeon-Regular.ttf', 10, 57, (255, 255, 255))
    lay = Image.new('RGBA', clean.size, (0, 0, 0, 0)); lay.alpha_composite(t, (round(32.5 - t.width / 2), round(7.5 - t.height / 2)))
    b = np.asarray(lay).copy(); al = np.clip((b[..., 3].astype(int) - 50) * 2, 0, 255).astype(np.uint8)   # 원본처럼 또렷하게
    b[..., 0] = b[..., 1] = b[..., 2] = b[..., 3] = al                          # 원본처럼 색 = 알파
    return clean, Image.fromarray(b, 'RGBA'), int(m.sum()), (0, 0, 64, 16)

def crisp_alpha(t, lo=40, k=1.6):
    """작은 글자가 뿌옇게 흐려지지 않게 알파 대비를 올린다."""
    ta = np.asarray(t).copy(); ta[..., 3] = np.clip((ta[..., 3].astype(int) - lo) * k, 0, 255)
    return Image.fromarray(ta, 'RGBA')


def pixel_text(txt, font, size, color):
    """도트 글꼴(fontmode 1)로 그린 RGBA(잉크에 딱 맞게 자름)."""
    from PIL import ImageDraw, ImageFont
    ft = ImageFont.truetype(os.path.join(FONTS, font), size)
    t = Image.new('L', (size * len(txt) * 2 + 8, size * 2 + 8)); d = ImageDraw.Draw(t); d.fontmode = '1'
    d.text((4, 4), txt, font=ft, fill=255)
    t = t.crop(t.getbbox())
    out = Image.new('RGBA', t.size, tuple(color) + (0,)); out.putalpha(t)
    return out


def put_center(im, t, box):
    x0, y0, x1, y1 = box
    im.alpha_composite(t, (round((x0 + x1) / 2 - t.width / 2), round((y0 + y1) / 2 - t.height / 2)))


def custom_premium(src):
    """잡지 표지 「プレミアム / 1月号」(보라 바탕·머리카락 위 흰 글자): 흰 글자를 LaMa 8배로 지우고 나눔스퀘어라운드 「프리미엄」/「1월호」."""
    from scipy import ndimage
    a = np.asarray(src); c3 = a[..., :3].astype(int); s3 = c3.sum(2); sat = c3.max(2) - c3.min(2)
    core = (s3 > 600) & (sat < 60)
    r1 = np.zeros(core.shape, bool); r1[3:13, 4:60] = True
    r2 = np.zeros(core.shape, bool); r2[14:22, 40:61] = True
    bg = np.array(Counter(tuple(c3[y, x]) for y in range(2, 14) for x in range(4, 60)).most_common(1)[0][0])
    hair = (c3[..., 2] < 60) & (c3[..., 0] > 130)                                  # 머리카락(주황)
    other = (np.abs(c3 - bg).sum(2) > 25) & ~hair                                  # 보라도 머리카락도 아닌 것 = 흰 글자·번짐
    m = (ndimage.binary_dilation(core & (r1 | r2), iterations=3) & other & (r1 | r2)) | (core & (r1 | r2))
    clean = lama_fill(src, m)
    im = clean.copy(); white = (255, 255, 255)
    ys, xs = np.where(core & r1); box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    t = narrow_text('프리미엄', 'NanumSquareRoundB.ttf', box[3] - box[1], box[2] - box[0] + 1, white)
    put_center(im, crisp_alpha(t), box)
    ys, xs = np.where(core & r2); box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)   # 「1월호」는 7px 라 도트 글꼴
    put_center(im, pixel_text('1월호', 'Galmuri7.ttf', 8, white), box)
    return clean, im, int(m.sum()), (3, 2, 62, 23)


def custom_jamonica(src):
    """학습장 표지 「ジャモニカ学習帳」(분홍 띠 위 7px 진분홍): 띠 5~11줄을 띠 분홍으로 칠하고 갈무리7 「자모니카학습장」(도트)."""
    from PIL import ImageDraw, ImageFont
    a = np.asarray(src).copy(); c3 = a[..., :3].astype(int)
    bandc = Counter(tuple(a[y, x]) for y in range(5, 12) for x in range(4, 60)).most_common(1)[0][0]
    ink = Counter(tuple(c3[y, x]) for y in range(5, 12) for x in range(4, 60) if c3[y, x].sum() < 420).most_common(1)[0][0]
    m = np.zeros(c3.shape[:2], bool); m[5:12, 4:60] = (a[5:12, 4:60] != np.array(bandc)).any(2)
    a[5:12, 4:60] = bandc
    clean = Image.fromarray(a, 'RGBA')
    ft = ImageFont.truetype(os.path.join(FONTS, 'Galmuri7.ttf'), 8)
    txt = '자모니카 학습장'
    t = Image.new('L', (120, 20)); d = ImageDraw.Draw(t); d.fontmode = '1'; d.text((2, 2), txt, font=ft, fill=255)
    ty, tx = np.where(np.asarray(t) > 0)
    if tx.max() - tx.min() + 1 > 56:
        txt = '자모니카학습장'
        t = Image.new('L', (120, 20)); d = ImageDraw.Draw(t); d.fontmode = '1'; d.text((2, 2), txt, font=ft, fill=255)
        ty, tx = np.where(np.asarray(t) > 0)
    w, h = tx.max() - tx.min() + 1, ty.max() - ty.min() + 1
    ox, oy = round(32 - w / 2) - tx.min(), round(8.5 - h / 2) - ty.min()
    im = a.copy()
    for y, x in zip(ty, tx):
        im[oy + y, ox + x] = (*ink, 255)
    return clean, Image.fromarray(im, 'RGBA'), int(m.sum()), (4, 5, 60, 12)


def custom_koteihyou(src):
    """게시판 「工程表」(오른쪽 세로 초록 글자): LaMa 8배로 지우고 갈무리11 굵게(도트) 「공」「정」「표」를 원본 세 글자 칸에 한 자씩(같은 크기)."""
    from scipy import ndimage
    a = np.asarray(src); c3 = a[..., :3].astype(int)
    g = (c3[..., 1] - c3[..., 0] > 15)
    reg = np.zeros(g.shape, bool); reg[14:50, 102:122] = True
    core = (c3[..., 1] - c3[..., 0] > 40) & reg
    m = ndimage.binary_dilation(g & reg, iterations=1) & reg
    clean = lama_fill(src, m)
    fillc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(core))).most_common(1)[0][0]
    ys, xs = np.where(core); x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    im = clean.copy()                                         # 9~10px 칸이라 굵은 도트 글꼴(갈무리11 굵게)을 한 자씩 세로로, 사이 1칸
    ts = [pixel_text(c, 'Galmuri11-Bold.ttf', 12, fillc) for c in '공정표']
    tot = sum(t.height for t in ts) + 2; y = round((y0 + y1) / 2 - tot / 2)
    for t in ts:
        im.alpha_composite(t, (round((x0 + x1) / 2 - t.width / 2), y)); y += t.height + 1
    return clean, im, int(m.sum()), (100, 12, 124, 52)

def custom_goalin(src):
    """신문 「ゴールイン」(파란 띠 노란 글자)·「結婚」(파란 칸 세로 빨간 글자+흰 테두리): 띠·칸 안쪽을 단색 파랑으로 칠하고
    블랙한산스 노란 「골인」(가로 1.5배), 빨간 「결」「혼」 세로. 빨간 알약·주황 낙서는 원본 그대로."""
    a = np.asarray(src); c3 = a[..., :3].astype(int)
    blue = (c3[..., 2] - c3[..., 0] > 100) & (c3[..., 2] - c3[..., 1] > 60)
    zb = np.zeros(blue.shape, bool); zb[7:17, 9:101] = True                      # 띠 안
    zk = np.zeros(blue.shape, bool); zk[18:58, 67:98] = True                     # 「結婚」 칸 안
    m = (zb | zk) & ~blue
    yel = (c3[..., 0] > 150) & (c3[..., 1] > 130) & (c3[..., 2] < 120) & zb
    red = (c3[..., 0] - c3[..., 1] > 80) & zk
    yc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(yel))).most_common(1)[0][0]
    rc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(red))).most_common(1)[0][0]
    bc = Counter(tuple(a[y, x]) for y, x in zip(*np.where(blue & (zb | zk)))).most_common(1)[0][0]
    ca = np.asarray(src).copy(); ca[zb | zk] = bc                 # 파란 칸 안쪽은 단색 파랑으로 통째 칠함(번짐·잔상 없이)
    m = (zb | zk) & (np.asarray(src) != np.array(bc)).any(2)
    clean = Image.fromarray(ca, 'RGBA')
    im = clean.copy(); font = os.path.join(FONTS, 'BlackHanSans-Regular.ttf')
    ys, xs = np.where(yel); box = (xs.min(), ys.min() - 1, xs.max() + 1, ys.max() + 2)
    t = render_text('골인', font, box[3] - box[1], yc)
    t = crisp_alpha(t.resize((round(t.width * 1.5), t.height), Image.LANCZOS))   # 띠가 길어 가로로 넓혀
    put_center(im, t, box)
    ys, xs = np.where(red); x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    h = (y1 - y0 - 2) / 2
    for k, c in enumerate('결혼'):
        t = crisp_alpha(render_text(c, font, round(h), rc))
        put_center(im, t, (x0, y0 + k * (h + 2), x1, y0 + k * (h + 2) + h))
    return clean, im, int(m.sum()), (8, 6, 102, 59)


def custom_lottery_rule(src):
    """복권 안내문 「ナナシ島 宝くじ」·「―規則―」(흰 바탕 짙은 회색 6px): 흰색으로 칠하고 갈무리7 「나나시섬 복권」·「-규칙-」.
    아래 작은 글 5줄은 원본 유지(규칙: 작은 본문)."""
    a = np.asarray(src).copy(); c3 = a[..., :3].astype(int)
    m = np.zeros(c3.shape[:2], bool)
    m[8:16, 6:58] = c3[8:16, 6:58].sum(2) < 740
    m[19:26, 8:30] = c3[19:26, 8:30].sum(2) < 740
    ink = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(m)) if c3[y, x].sum() < 250).most_common(1)[0][0]
    whitec = Counter(tuple(a[y, x]) for y in range(8, 16) for x in range(6, 58) if not m[y, x]).most_common(1)[0][0]
    a[m] = whitec
    clean = Image.fromarray(a, 'RGBA'); im = clean.copy()
    t1 = pixel_text('나나시섬 복권', 'Galmuri7.ttf', 8, ink)
    if t1.width > 50:
        t1 = pixel_text('나나시섬복권', 'Galmuri7.ttf', 8, ink)
    im.alpha_composite(t1, (round(30 - t1.width / 2), 9))
    t2 = pixel_text('-규칙-', 'Galmuri7.ttf', 8, ink)
    im.alpha_composite(t2, (round(18.5 - t2.width / 2), 19))
    return clean, im, int(m.sum()), (5, 7, 59, 27)


def custom_rumiko(src):
    """사물함 명판 「ルミコ」: 명판 안쪽(검은 테두리 안, 32~45줄·46~81열)을 안쪽 최빈색 단색으로 칠하고 갈무리11 굵게(도트) 「루미코」."""
    a = np.asarray(src).copy(); s3 = a[..., :3].astype(int).sum(2)
    core = np.zeros(s3.shape, bool); core[32:46, 46:82] = s3[32:46, 46:82] < 200
    ink = Counter(tuple(a[y, x, :3]) for y, x in zip(*np.where(core))).most_common(1)[0][0]
    ys, xs = np.where(core); box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    fillc = Counter(tuple(a[y, x]) for y in range(32, 46) for x in range(46, 82) if s3[y, x] > 500).most_common(1)[0][0]
    m = np.zeros(s3.shape, bool); m[32:46, 46:82] = (a[32:46, 46:82] != np.array(fillc)).any(2)
    a[32:46, 46:82] = fillc
    clean = Image.fromarray(a, 'RGBA')
    im = clean.copy(); put_center(im, pixel_text('루미코', 'Galmuri11-Bold.ttf', 12, ink), box)
    return clean, im, int(m.sum()), (45, 31, 83, 47)

def custom_keyperson(src):
    """포스터 2장 「キーパーソン」(빨강+짙은 자주 테두리)·「ゴミひろい」(남색): LaMa 8배로 지우고
    블랙한산스 「키 퍼슨」(빨강+자주 테두리), 주아 「쓰레기 줍기」(남색). 아래 작은 띠 글자는 원본 유지."""
    from scipy import ndimage
    a = np.asarray(src); c3 = a[..., :3].astype(int)
    zl = np.zeros(c3.shape[:2], bool); zl[2:23, 0:64] = True
    zr = np.zeros(c3.shape[:2], bool); zr[3:23, 66:128] = True
    redish = (c3[..., 0] > 80) & (c3[..., 1] < 50) & (c3[..., 2] < 90)
    navy = (c3[..., 2] - c3[..., 0] > 80) & (c3.sum(2) < 330)
    tl, tr = redish & zl, navy & zr
    dark = (c3.sum(2) < 260) & ~((c3[..., 2] - c3[..., 0] > 60))                   # 자주·검정 테두리(남색 사람 그림은 뺌)
    bluish = (c3[..., 2] > c3[..., 1] + 25) & zr                                    # 남색 글자 둘레 연파랑 번짐
    m = (ndimage.binary_dilation(tl, iterations=2) & zl & (redish | dark | (np.abs(c3 - c3[1, 30]).sum(2) > 60)))         | (ndimage.binary_dilation(tr, iterations=2) & zr & (navy | bluish | (c3.sum(2) < 500)))
    rc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(tl & (c3[..., 0] > 200)))).most_common(1)[0][0]
    ec = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(tl & (c3[..., 0] < 160)))).most_common(1)[0][0]
    nc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(tr))).most_common(1)[0][0]
    clean = lama_fill(src, m); im = clean.copy()
    ys, xs = np.where(tl); box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    t = crisp_outline('키 퍼슨', os.path.join(FONTS, 'BlackHanSans-Regular.ttf'), box[3] - box[1] - 4, rc, ec, stroke=1, aa=True)
    put_center(im, fit(t, box[2] - box[0] + 1, box[3] - box[1] + 1), box)
    ys, xs = np.where(tr); box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    t = crisp_alpha(narrow_text('쓰레기 줍기', 'Jua.ttf', box[3] - box[1] - 2, box[2] - box[0], nc))
    put_center(im, t, box)
    return clean, im, int(m.sum()), (0, 1, 128, 24)


def bold_pixel(txt, font, size, color, bold=True):
    """도트 글꼴을 1칸 오른쪽으로 한 번 더 찍어 굵게(원본 계약서처럼 두꺼운 도트)."""
    from PIL import ImageDraw, ImageFont
    ft = ImageFont.truetype(os.path.join(FONTS, font), size)
    t = Image.new('L', (size * len(txt) * 2 + 8, size * 2 + 8)); d = ImageDraw.Draw(t); d.fontmode = '1'
    d.text((4, 4), txt, font=ft, fill=255)
    if bold:
        d.text((5, 4), txt, font=ft, fill=255)
    t = t.crop(t.getbbox())
    out = Image.new('RGBA', t.size, tuple(color) + (0,)); out.putalpha(t)
    return out


CONTRACT = [((40, 50), 23, '텐진의 머천다이징에'), ((54, 64), 23, '관한 권리는 모두'), ((68, 78), 23, '데스네에 귀속됩니다'),
            ((87, 97), 14, '재단법인 데스네 컴퍼니'), ((101, 111), 14, '이사장  코맛타·찬 귀하')]


def custom_contract(src, sign=False):
    """계약서 「契約書 ~Contract~」+본문 5줄(크림색 종이, 고동색 도트 글자): 「契約書」와 본문만 LaMa 8배로 지우고(~Contract~ 는 원본)
    갈무리11 굵게 「계약서」(세로 1.5배), 갈무리9 본문 5줄(원본 줄 시작 위치에 왼쪽 맞춤). sign=True(2173)면 초록 서명 「ポックル」도
    지우고 나눔손글씨 펜 「포클」을 원본처럼 기울여 쓴다."""
    from scipy import ndimage
    a = np.asarray(src); c3 = a[..., :3].astype(int)
    bg = np.array(Counter(tuple(c3[y, x]) for y in range(30, 100) for x in range(20, 110)).most_common(1)[0][0])
    diff = np.abs(c3 - bg).sum(2) > 40
    z = np.zeros(diff.shape, bool); z[12:31, 12:48] = True
    for (y0, y1), x0, _ in CONTRACT:
        z[y0 - 1:y1 + 1, x0 - 2:122] = True
    if sign:
        z[98:123, 86:123] = True
    m = ndimage.binary_dilation(diff & z, iterations=1) & z
    ink = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(diff & z & (c3.sum(2) < 200)))).most_common(1)[0][0]
    g = (c3[..., 1] - c3[..., 0] > 20) & z
    clean = lama_fill(src, m); im = clean.copy()
    t = bold_pixel('계약서', 'Galmuri11-Bold.ttf', 12, ink, bold=False)
    t = t.resize((t.width, round(t.height * 1.5)), Image.NEAREST)
    put_center(im, t, (13, 13, 47, 30))
    for (y0, y1), x0, txt in CONTRACT:
        t = bold_pixel(txt, 'Galmuri9.ttf', 10, ink, bold=False)     # 굵게 찍으면 ㅔ·ㅐ 획이 뭉침 → 보통
        if x0 + t.width > 121:
            t = t.resize((121 - x0, t.height), Image.NEAREST)
        im.alpha_composite(t, (x0, round((y0 + y1) / 2 - t.height / 2)))
    if sign:
        gc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(g))).most_common(1)[0][0]
        t = render_text('포클', os.path.join(FONTS, 'NanumPenScript-Regular.ttf'), 18, gc)
        t = crisp_alpha(t.rotate(25, resample=Image.BICUBIC, expand=True))
        put_center(im, t, (92, 100, 124, 124))
    return clean, im, int(m.sum()), (10, 11, 124, 124)

def place_fit(im, txt, font, box, color, squeeze_ok=True):
    """box(x0,y0,x1,y1) 높이에 맞춰 그리고 폭이 넘치면 가로만 줄여 가운데에 놓는다(작은 글자는 알파 대비 올림)."""
    x0, y0, x1, y1 = box
    t = render_text(txt, os.path.join(FONTS, font), y1 - y0, color)
    if t.width > x1 - x0 + 2:
        t = t.resize((x1 - x0 + 2, t.height), Image.LANCZOS)
    put_center(im, crisp_alpha(t), box)


def custom_kitchen(src):
    """아이템 아이콘 「キッチン」 전단지(32x32, 분홍 5px): 분홍 글자·번짐을 줄별 바탕 최빈색으로 지우고 갈무리7 「키  친」(띄워 폭 맞춤, 원본 분홍)."""
    from scipy import ndimage
    a = np.asarray(src); c3 = a[..., :3].astype(int)
    m = np.zeros(c3.shape[:2], bool)
    m[2:8, 1:31] = (c3[2:8, 1:31, 0] - c3[2:8, 1:31, 1] > 8)                    # 2~7줄: 옅은 분홍빛까지 전부 글자·번짐
    m[8:10, 1:31] = (c3[8:10, 1:31, 0] - c3[8:10, 1:31, 1] > 60)                  # 8~9줄: 붉은 글자 끝만(고양이 귀는 회갈색이라 R-G 작음)
    core = m & (c3[..., 0] - c3[..., 1] > 80)
    pc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(core))).most_common(1)[0][0]
    a2 = a.copy()
    for y in range(2, 10):                                                        # 줄마다 분홍 아닌 바탕 최빈색으로
        ok = [tuple(a[y, x]) for x in range(1, 31) if not m[y, x] and c3[y, x, 0] - c3[y, x, 1] <= 8]
        if ok:
            a2[y][m[y]] = Counter(ok).most_common(1)[0][0]
    clean = Image.fromarray(a2, 'RGBA'); im = clean.copy()
    t = pixel_text('키  친', 'Galmuri7.ttf', 8, pc)                 # 원본 4글자 폭에 맞춰 띄움
    ys, xs = np.where(core); put_center(im, t, (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    return clean, im, int(m.sum()), (0, 1, 32, 10)


def custom_baito(src):
    """아이템 아이콘 「バイト / 募集」 포스터(32x32, 빨강): LaMa 8배로 지우고 갈무리9 굵게 「알바」/「모집」."""
    from scipy import ndimage
    a = np.asarray(src); c3 = a[..., :3].astype(int)
    z1 = np.zeros(c3.shape[:2], bool); z1[0:9, 1:31] = True
    z2 = np.zeros(c3.shape[:2], bool); z2[19:32, 0:23] = True
    redd = (c3[..., 0] - c3[..., 1] > 40)
    m = ndimage.binary_dilation(redd & (z1 | z2), iterations=1) & (z1 | z2) & (c3[..., 0] - c3[..., 1] > 15)
    rc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where((c3[..., 0] - c3[..., 1] > 80) & (z1 | z2)))).most_common(1)[0][0]
    clean = lama_fill(src, m); im = clean.copy()
    put_center(im, bold_pixel('알바', 'Galmuri9.ttf', 10, rc), (2, 0, 30, 9))       # 7~9px 칸 → 도트 글꼴 굵게
    put_center(im, bold_pixel('모집', 'Galmuri9.ttf', 10, rc), (1, 22, 22, 31))
    return clean, im, int(m.sum()), (0, 0, 32, 32)


def custom_kingfine(src):
    """포스터 「キング と 罰金」(노랑 단색 바탕 빨간 굵은 글자, 가운데 작은 검은 「と」): 글자 자리를 노랑으로 칠하고
    블랙한산스 빨강 「킹」·「벌」「금」(넓적하게), 검은 「과」."""
    a = np.asarray(src).copy(); c3 = a[..., :3].astype(int)
    yc = Counter(tuple(a[y, x]) for y in range(34) for x in range(64)).most_common(1)[0][0]
    z = np.zeros(c3.shape[:2], bool); z[2:12, 2:63] = True; z[12:16, 27:38] = True; z[14:29, 3:62] = True   # 28줄 = 글자 그림자
    m = z & (np.abs(c3 - np.array(yc[:3])).sum(2) > 40)
    core = m & (c3[..., 0] - c3[..., 1] > 100)
    rc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(core))).most_common(1)[0][0]
    a[m] = yc
    clean = Image.fromarray(a, 'RGBA'); im = clean.copy()
    bh = os.path.join(FONTS, 'BlackHanSans-Regular.ttf')

    def wide(txt, h, w, col):                                    # 원본 가타카나·한자처럼 넓적하게
        t = render_text(txt, bh, h, col)
        return crisp_alpha(t.resize((w, t.height), Image.LANCZOS))
    t = bold_pixel('킹', 'Galmuri9.ttf', 10, rc)                     # 8px 매끈한 글꼴은 ㅇ이 뭉개짐 → 도트 굵게를 가로 2배
    put_center(im, t.resize((t.width * 2, t.height), Image.NEAREST), (3, 1, 62, 10))
    tc = Counter(tuple(c3[y, x]) for y in range(12, 15) for x in range(28, 38) if c3[y, x].sum() < 330).most_common(1)[0][0]
    put_center(im, wide('과', 5, 9, tc), (27, 11, 39, 16))           # 가운데 검은 「と」 → 「과」(1칸 키우려고 위·아래 줄을 1칸씩 벌림)
    put_center(im, wide('벌', 12, 22, rc), (4, 16, 25, 29))       # 「罰」·「金」 자리에 한 자씩
    put_center(im, wide('금', 12, 22, rc), (38, 16, 61, 29))
    return clean, im, int(m.sum()), (1, 1, 64, 31)

def _q565(c):
    c = np.clip(np.round(c), 0, 255).astype(int)
    r, g, b = c[..., 0] >> 3, c[..., 1] >> 2, c[..., 2] >> 3
    return np.stack([r * 255 // 31, g * 255 // 63, b * 255 // 31], -1), (r << 11) | (g << 5) | b   # tpl.py c565 와 같은 확장


def cmpr_sim(img):
    """GC CMPR(DXT1 계열) 압축을 흉내 낸다: 4x4 블록마다 주축 양 끝 두 색(RGB565) + 그 사이 1/3·2/3 두 색, 픽셀은 가장 가까운 색.
    게임에 넣으면 어차피 이렇게 뭉개지므로 미리보기·원본 질감 맞추기에 쓴다(알파 그대로)."""
    a = np.asarray(img.convert('RGBA')).astype(float).copy(); H, W = a.shape[:2]
    for by in range(0, H, 4):
        for bx in range(0, W, 4):
            blk = a[by:by + 4, bx:bx + 4, :3].reshape(-1, 3)
            mu = blk.mean(0); d = blk - mu
            if np.abs(d).max() < 1:
                c0 = c1 = mu
            else:
                v = np.linalg.svd(d, full_matrices=False)[2][0]
                t = d @ v; c0, c1 = mu + v * t.max(), mu + v * t.min()
            (q0, k0), (q1, k1) = _q565(c0), _q565(c1)
            if k0 < k1:
                q0, q1 = q1, q0
            pal = np.array([q0, q1, (2 * q0 + q1) / 3, (q0 + 2 * q1) / 3]).round()
            idx = ((blk[:, None, :] - pal[None]) ** 2).sum(2).argmin(1)
            a[by:by + 4, bx:bx + 4, :3] = pal[idx].reshape(a[by:by + 4, bx:bx + 4, :3].shape[0], -1, 3)
    return Image.fromarray(a.round().astype(np.uint8), 'RGBA')

def soften(clean, ko, r=0.6):
    """한글 글자층(ko 가 clean 과 다른 곳)만 살짝 번지게: 글자 색을 1칸 번지고 알파를 가우시안으로 흐림(획 중심은 유지)."""
    from PIL import ImageFilter
    from scipy import ndimage
    c, k = np.asarray(clean).astype(float), np.asarray(ko).astype(float)
    M = (np.abs(c - k).sum(2) > 0).astype(float)
    if not M.any():
        return ko
    _, (iy, ix) = ndimage.distance_transform_edt(M == 0, return_indices=True)
    col = k[iy, ix]                                                  # 글자 바깥은 가장 가까운 글자 색
    al = np.asarray(Image.fromarray((M * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(float) / 255
    al = np.maximum(al, M * 0.8)[..., None]
    out = c.copy(); out[..., :3] = c[..., :3] * (1 - al) + col[..., :3] * al
    return Image.fromarray(out.round().astype(np.uint8), 'RGBA')

A3 = np.array([0, 36, 72, 109, 145, 182, 218, 255])


def rgb5a3_sim(img):
    """RGB5A3 흉내: 알파 3비트(8단계), 반투명 픽셀은 RGB 4비트, 불투명은 RGB 5비트."""
    a = np.asarray(img.convert('RGBA')).astype(int).copy()
    al = A3[np.abs(a[..., 3:4] - A3[None, None, :]).argmin(2)]
    op = al == 255
    rgb = a[..., :3]
    q5 = (rgb >> 3) * 255 // 31; q4 = (rgb >> 4) * 17                  # tpl.py c5a3 와 같은 확장
    a[..., :3] = np.where(op[..., None], q5, q4); a[..., 3] = al
    a[al == 0] = 0
    return Image.fromarray(a.astype(np.uint8), 'RGBA')


def _glyphs(txt, font, size, bold=False):
    from PIL import ImageDraw, ImageFont
    ft = ImageFont.truetype(os.path.join(FONTS, font), size)
    out = []
    for ch in txt:
        if ch == ' ':
            out.append(None); continue
        t = Image.new('L', (size * 2 + 8, size * 2 + 8)); d = ImageDraw.Draw(t); d.fontmode = '1'
        d.text((4, 4), ch, font=ft, fill=255)
        if bold:
            d.text((5, 4), ch, font=ft, fill=255)
        out.append(t.crop(t.getbbox()) if t.getbbox() else None)
    return out


def vcol(txt, font, size, gap=1, drift=0, bold=False):
    """세로쓰기 한 줄(L 마스크). 글자는 똑바로 두고, drift 만큼 아래로 갈수록 오른쪽으로 비켜 놓아 원본 낙서의 기울기를 따른다
    (도트 글자를 돌리면 뭉개지므로 줄 전체를 돌리는 대신 글자 자리만 기울인다)."""
    gl = _glyphs(txt, font, size, bold)
    w = max(g.width for g in gl if g); H = sum((g.height if g else size // 2) + gap for g in gl) - gap
    out = Image.new('L', (w + abs(drift) + 1, H)); y = 0
    for g in gl:
        if g is None:
            y += size // 2 + gap; continue
        dx = round(drift * (y + g.height / 2) / H) + (abs(drift) if drift < 0 else 0)
        out.paste(g, ((w - g.width) // 2 + dx, y)); y += g.height + gap
    return out


def hline(txt, font, size, rise=0, gap=1, bold=False):
    """가로 한 줄(L 마스크). rise 만큼 오른쪽으로 갈수록 위로 올려 놓는다(글자는 똑바로)."""
    gl = _glyphs(txt, font, size, bold)
    h = max(g.height for g in gl if g); W = sum((g.width if g else size // 3) + gap for g in gl) - gap
    out = Image.new('L', (W, h + abs(rise) + 1)); x = 0
    for g in gl:
        if g is None:
            x += size // 3 + gap; continue
        dy = abs(rise) - round(rise * (x + g.width / 2) / W) if rise > 0 else round(-rise * (x + g.width / 2) / W)
        out.paste(g, (x, h - g.height + dy)); x += g.width + gap
    return out


def custom_rakugaki(src, parts):
    """낙서 데칼(RGB5A3, 투명 바탕에 흰 손글씨, 가장자리는 옅은 색·반투명): 전부 투명으로 지우고
    parts = [(L 마스크, 회전각, 중심 x, 중심 y)] 를 회전해 얹은 뒤 원본처럼 흰 속 + 가장자리 색, RGB5A3 로 줄인다."""
    from PIL import ImageFilter
    a = np.asarray(src).astype(int); al0 = a[..., 3]
    core = tuple(np.median(a[al0 == 255][:, :3], 0).round().astype(int)) if (al0 == 255).any() else (255, 255, 255)
    edge = tuple(np.median(a[(al0 > 0) & (al0 < 120)][:, :3], 0).round().astype(int))
    bgc = Counter(tuple(p) for p in a[al0 == 0][:, :3]).most_common(1)[0][0]
    clean = np.zeros_like(a); clean[..., :3] = bgc
    m = Image.new('L', src.size, 0)
    for mask, ang, cx, cy in parts:
        r = mask if ang == 0 else mask.rotate(ang, resample=Image.NEAREST, expand=True)
        lay = Image.new('L', src.size, 0); lay.paste(r, (round(cx - r.width / 2), round(cy - r.height / 2)))
        m = Image.fromarray(np.maximum(np.asarray(m), np.asarray(lay)))
    halo = m.filter(ImageFilter.GaussianBlur(0.7))
    A = np.maximum(np.asarray(m).astype(float), np.minimum(np.asarray(halo).astype(float) * 1.0, 110))   # 원본처럼 획 둘레에 옅은 색 반투명
    k = (np.asarray(m).astype(float) / 255)[..., None]
    out = np.zeros_like(a, dtype=float); out[..., :3] = np.array(edge) * (1 - k) + np.array(core) * k; out[..., 3] = A
    out[A == 0, :3] = bgc
    im = rgb5a3_sim(Image.fromarray(out.round().astype(np.uint8), 'RGBA'))
    return Image.fromarray(clean.astype(np.uint8), 'RGBA'), im, int((al0 > 0).sum()), (0, 0, src.width, src.height)


def custom_1676(src):
    """「メイヤー邸の / 噴水で手を洗った / 勝っ!!」(64x32, 오른쪽 위로 기운 3줄) → 메이어 저택 / 분수에서 손 씻고 / 이겼다!!"""
    return custom_rakugaki(src, [(hline('메이어 저택', 'Galmuri7.ttf', 8, rise=4), 0, 31, 6),
                                 (hline('분수에서 손 씻고', 'Galmuri7.ttf', 8, rise=4), 0, 32, 16),
                                 (hline('이겼다!!', 'Galmuri7.ttf', 8, rise=2), 0, 26, 26)])


def custom_1917(src):
    """「タオにかまれて」(왼쪽 세로)·「勝った!!」(오른쪽 세로, 큼) → 타오한테 물렸다 / 이겼다!!"""
    return custom_rakugaki(src, [(vcol('타오한테물렸다', 'Galmuri7.ttf', 8, 1, drift=3), 0, 7, 32),
                                 (vcol('이겼다!!', 'Galmuri9.ttf', 10, 2, drift=3, bold=True), 0, 22, 33)])


def custom_2059(src):
    """「アンの下着に(さわった)」(왼쪽, 위에서 오른쪽 아래로 비스듬)·「勝った!!」(오른쪽 세로) → 앤 속옷 만졌다 / 이겼다!!"""
    return custom_rakugaki(src, [(vcol('앤속옷만졌다', 'Galmuri7.ttf', 8, 2, drift=12), 0, 12, 32),
                                 (vcol('이겼다!!', 'Galmuri9.ttf', 10, 2, drift=2, bold=True), 0, 25, 27)])

LETTER_LINES = ['내 치매로 폐를', '끼쳤구먼. 이제', '괜찮구먼.', '치비타야, 강한', '사내가 되거라.', '루미코야, 여자의', '행복을 잡거라.',
                '하늘나라에서', '딴지 공부를 하기로']   # 대사 E12075~E12079 번역 그대로
RULED = [36, 45, 55, 64, 74, 83, 92, 102, 111]
LINE_ROWS = [36, 45, 46, 55, 64, 73, 74, 83, 92, 93, 102, 111, 112]


def custom_letter(src):
    """할머니 편지(E12075~E12080, 흰 종이·주황 줄, 검은 손글씨 7줄 + 「さようなら」): 글자 픽셀을 같은 줄의 가장 가까운 종이·줄 색으로
    가로로 메워 지우고(주황 줄은 이어짐), 대사 번역문을 갈무리7 로 줄마다(주황 줄 바로 위) 줄바꿈해 쓴다. 「잘 있거라.」는 마지막 줄 오른쪽."""
    a = np.asarray(src).copy(); c3 = a[..., :3].astype(int); s3 = c3.sum(2)
    orange = (c3[..., 0] > 180) & (c3[..., 1] > 60) & (c3[..., 1] < 200) & (c3[..., 2] < 160)   # 주황 줄(짙은 갈색 글씨는 R<180)
    z = np.zeros(s3.shape, bool); z[24:119, 28:98] = True
    neutral = np.abs(c3[..., 0] - c3[..., 2]) < 25                                 # 글씨는 무채색(줄 아래 살구색 음영은 둔다)
    m = z & (s3 < 735) & neutral & ~orange                                        # 옅은 회색 번짐까지
    for y in range(26, 32):                                       # 첫 줄 끝 「く」가 오른쪽 점선 테두리(98~99열)까지 삐침 → 왼쪽 테두리 대칭 자리 색으로
        for x in (98, 99):
            if s3[y, x] < 400:
                a[y, x] = a[y, 125 - x]; m[y, x] = True
    ink = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(m & (s3 < 250)))).most_common(1)[0][0]
    for y in range(24, 119):
        xs = np.where(~m[y, 28:100])[0] + 28
        for x in np.where(m[y, :98])[0]:
            a[y, x] = a[y, xs[np.abs(xs - x).argmin()]]
    for y in LINE_ROWS:                                           # 주황 줄(1~2줄 두께)은 줄 시작~끝을 그 줄 최빈 주황 하나로 다시 그음(글씨 겹친 자국 없이)
        lo = (c3[y, 30:96, 0] > 150) & (c3[y, 30:96, 0] - c3[y, 30:96, 2] > 40)
        xs = np.where(lo)[0] + 30
        oc = Counter(tuple(np.asarray(src)[y, x]) for x in xs if c3[y, x, 0] > 180).most_common(1)[0][0]
        a[y, xs.min():xs.max() + 1] = oc; m[y, xs.min():xs.max() + 1] = True
        for x in list(range(xs.min() - 4, xs.min())) + list(range(xs.max() + 1, xs.max() + 5)):   # 줄 끝에 걸친 짙은 글씨 자국
            if 28 <= x < 98 and c3[y, x].sum() < 450:
                a[y, x] = oc; m[y, x] = True
    for y in range(24, 119):                                      # 마무리: 줄이 아닌 행에서 그 행 최빈색보다 확 어두운 점(글씨 찌꺼기)은 최빈색으로
        if y in LINE_ROWS:
            continue
        mc = Counter(tuple(a[y, x]) for x in range(30, 96)).most_common(1)[0][0]
        for x in range(28, 98):
            if a[y, x, :3].astype(int).sum() < sum(int(v) for v in mc[:3]) - 90:   # uint8 합은 넘쳐서 int 로
                a[y, x] = mc; m[y, x] = True
    clean = Image.fromarray(a, 'RGBA'); im = np.asarray(clean).copy()
    lines = LETTER_LINES                                          # 줄마다 66px 안(문장 끊기 자연스럽게 손으로 나눔)
    def put(txt, x, ybot):
        g = np.asarray(hline(txt, 'Galmuri7.ttf', 8)) > 0
        y0 = ybot - g.shape[0]
        for yy, xx in zip(*np.where(g)):
            im[y0 + yy, x + xx, :3] = ink
    for txt, r in zip(lines, RULED):
        put(txt, 29, r - 2)
    put('했구먼…', 29, 117)                                       # 마지막 칸: 왼쪽에 문장 끝, 오른쪽에 「잘 있거라.」(원본 「さようなら」 자리)
    w = hline('잘 있거라.', 'Galmuri7.ttf', 8).width
    put('잘 있거라.', 94 - w, 117)
    out = soften(clean, Image.fromarray(im, 'RGBA'), 0.5)
    return clean, out, int(m.sum()), (27, 23, 100, 120)

def custom_2223(src):
    """「おさい銭したら」(왼쪽, 위에서 오른쪽 아래로 비스듬)·「勝った!」(오른쪽 세로) → 새전 넣었더니 / 이겼다!"""
    return custom_rakugaki(src, [(vcol('새전넣었더니', 'Galmuri9.ttf', 10, 1, drift=8), 0, 9, 33),   # 두 줄 같은 크기·굵기(굵게 하면 ㅐ가 뭉쳐 「시」처럼 보임)
                                 (vcol('이겼다!', 'Galmuri9.ttf', 10, 2, drift=2), 0, 25, 35)])


def custom_rensho(src):
    """신문 큰 제목 「連勝」(32x32 RGB565, 노란 글자+파란 테두리, 오른쪽 빨간 띠는 원본 유지): LaMa 8배로 지우고
    갈무리11 굵게 「연」「승」 세로(가로로 넓힘, 노랑 + 파란 테두리 1칸), 글자층만 살짝 번지게 한 뒤 RGB565 로 줄인다."""
    from scipy import ndimage
    a = np.asarray(src); c3 = a[..., :3].astype(int)
    z = np.zeros(c3.shape[:2], bool); z[1:29, 1:23] = True
    yel = (c3[..., 0] > 180) & (c3[..., 2] < 150) & z
    blu = (c3[..., 2] - c3[..., 0] > 80) & z
    m = ndimage.binary_dilation(yel | blu, iterations=1) & z & ~((c3[..., 1] - c3[..., 0] > 40) & ~blu & ~yel)
    yc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(yel))).most_common(1)[0][0]
    bc = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(blu))).most_common(1)[0][0]
    clean = lama_fill(src, m); im = clean.copy()
    font = os.path.join(FONTS, 'BlackHanSans-Regular.ttf')
    for c, box in (('연', (1, 1, 23, 15)), ('승', (1, 15, 23, 29))):  # 원본 한자처럼 칸을 꽉 채우게(가로로 넓혀)
        t = pixel_text(c, 'Galmuri11-Bold.ttf', 12, yc)              # 칸이 12px 라 매끈한 글꼴은 획이 메워짐 → 도트 굵게를 가로로 넓힘
        t = t.resize((round(t.width * 19 / 11), 12), Image.NEAREST)    # 두 글자 같은 배율(글자마다 따로 늘리면 획 굵기·크기가 달라짐)
        al = np.asarray(t.getchannel('A')) >= 128
        H, W = al.shape; op = np.zeros((H + 2, W + 2, 4), np.uint8)
        dil = ndimage.binary_dilation(np.pad(al, 1))
        op[dil] = (*bc, 255); op[1:H + 1, 1:W + 1][al] = (*yc, 255)
        put_center(im, Image.fromarray(op, 'RGBA'), box)
    out = np.asarray(soften(clean, im, 0.5)).copy()
    o3 = out[..., :3].astype(int)                                 # RGB565 로 줄이기: tpl.py 디코더와 같은 확장(v*255//최댓값) → 원본 픽셀은 그대로
    out[..., 0] = (o3[..., 0] * 31 + 127) // 255 * 255 // 31; out[..., 2] = (o3[..., 2] * 31 + 127) // 255 * 255 // 31
    out[..., 1] = (o3[..., 1] * 63 + 127) // 255 * 255 // 63
    return clean, Image.fromarray(out, 'RGBA'), int(m.sum()), (0, 0, 24, 30)

ZUKAN = {
    '1545': dict(cover=(128, 256), title=('나나시섬', '식물 도감'), spine='나나시섬식물도감',
                 pages=[((0, 0), ['남국 플라워']), ((128, 0), ['물 주는 풀']), ((0, 128), ['헨푸']), ((128, 128), ['신목'])]),
    '1546': dict(cover=(384, 256), title=('나나시섬', '물고기 도감'), spine='나나시섬물고기도감',
                 pages=list(zip([(x * 64, y * 128) for y in range(3) for x in range(8)][:20],
                                [['나나시', '붕어'], ['나나시', '메기'], ['나나시', '잉어'], ['황금', '잉어'], ['정어리'], ['꽁치'], ['경사참돔'], ['참다랑어'],
                                 ['비송어'], ['일찍', '곤들매기'], ['대왕', '송사리'], ['요노하테의', '주인'], ['뻥', '참치'], ['마네거북'], ['나나시', '바다뱀'], ['도망천어'],
                                 ['피라미'], ['나나시', '망둥이'], ['옜다고기'], ['나나시', '장어']]))),
    '1547': dict(cover=(128, 256), title=('나나시섬', '버섯 도감'), spine='나나시섬버섯도감',
                 pages=list(zip([(x * 64, y * 128) for y in range(3) for x in range(4)][:9],
                                [['그냥', '버섯'], ['초록', '버섯'], ['하늘색', '버섯'], ['새빨간', '버섯'], ['쪽빛', '버섯'], ['노란', '버섯'],
                                 ['보라', '버섯'], ['오렌지', '버섯'], ['무지개', '버섯']]))),
}


def _outlined_bits(g, fill, edge):
    """bool 글자 모양 g 에 1칸 테두리(8방향)를 둘러 RGBA 로."""
    from scipy import ndimage
    H, W = g.shape; op = np.zeros((H + 2, W + 2, 4), np.uint8)
    op[ndimage.binary_dilation(np.pad(g, 1), structure=np.ones((3, 3)))] = (*edge, 255)
    op[1:H + 1, 1:W + 1][g] = (*fill, 255)
    return Image.fromarray(op, 'RGBA')


def custom_zukan(src, key):
    """도감 3권(식물·물고기·버섯): 쪽마다 이름(갈색 굵은 글자, 24~47줄)을 그 쪽 종이 최빈색(단색)으로 지우고 이름을 새로 쓴다
    (식물은 원본처럼 한 줄 갈무리9, 물고기·버섯은 갈무리11 굵게, 두 줄이면 윗줄 왼쪽·아랫줄 오른쪽).
    책등 이름표(안쪽 단색)·표지 제목(패널 단색)은 바탕색으로 칠하고 흰 글자+짙은 테두리로 새로 쓴다. 작은 설명 글은 원본 유지."""
    from scipy import ndimage
    cfg = ZUKAN[key]
    a = np.asarray(src).copy(); c3 = a[..., :3].astype(int); s3 = c3.sum(2)
    dark = (s3 < 420) & (c3[..., 0] > c3[..., 2] + 10)
    cl = a.copy(); total = 0
    ink = Counter(tuple(c3[y, x]) for (px, py), _ in cfg['pages'] for y in range(py + 26, py + 46) for x in range(px + 6, px + 58) if s3[y, x] < 300 and c3[y, x, 0] > c3[y, x, 2]).most_common(1)[0][0]
    for (px, py), _ in cfg['pages']:                              # 1) 쪽 이름 지우기(종이 단색)
        z = np.zeros(s3.shape, bool); z[py + 24:py + 48, px + 4:px + 60] = True
        m = ndimage.binary_dilation(dark & z, iterations=1) & z
        total += int(m.sum())
        pc0 = Counter(tuple(a[y, x]) for y in range(py + 22, py + 50) for x in range(px + 8, px + 56) if not m[y, x] and not dark[y, x]).most_common(1)[0][0]
        cl[m] = pc0                                               # 이름 둘레 종이는 단색 → 그 쪽 종이 최빈색 하나로 채움
    cx, cy = cfg['cover']
    sx0, sx1, sy0, sy1 = cx + 42, cx + 51, 270, 342                 # 2) 책등 이름표 안쪽 → 최빈 바탕색 단색
    lc = Counter(tuple(a[y, x]) for y in range(sy0, sy1) for x in range(sx0, sx1) if 450 < s3[y, x] < 650).most_common(1)[0][0]
    sp_edge = Counter(tuple(c3[y, x]) for y in range(sy0, sy1) for x in range(sx0, sx1) if s3[y, x] < 300).most_common(1)[0][0]
    total += int((np.abs(c3[sy0:sy1, sx0:sx1] - np.array(lc[:3])).sum(2) > 0).sum())
    cl[sy0:sy1, sx0:sx1] = lc
    pc = Counter(tuple(a[y, x]) for y in range(cy + 40, cy + 90) for x in range(cx + 50, cx + 125)).most_common(1)[0][0]
    tz = np.zeros(s3.shape, bool); tz[298:342, cx + 64:cx + 124] = True   # 오른쪽 테두리선(cx+124~127)은 건드리지 않음  # 3) 표지 제목 → 패널색
    tm = tz                                                       # 패널은 단색 → 제목 칸 전체를 패널색 하나로(옅은 번짐까지 남김없이)
    edge = Counter(tuple(c3[y, x]) for y, x in zip(*np.where(tm & (s3 < 200)))).most_common(1)[0][0]   # 원본 제목 테두리색
    cl[tm] = pc; total += int(tm.sum())
    clean = Image.fromarray(cl, 'RGBA'); lay = clean.copy()
    one_line = key == '1545'
    for (px, py), lines in cfg['pages']:                          # 4) 이름 쓰기
        if one_line:
            gm = hline(lines[0], 'Galmuri9.ttf', 10)                 # 띄어쓰기를 좁게(1/3칸) 해 늘리지 않고 쪽 안에 맞춤
            g = Image.new('RGBA', gm.size, tuple(ink) + (0,)); g.putalpha(gm.point(lambda v: 255 if v else 0))
            lay.alpha_composite(g, (px + 7 if g.width > 48 else px + 10, py + 30))
            continue
        gl = []
        for t in lines:
            g = pixel_text(t, 'Galmuri11-Bold.ttf', 12, ink)
            gl.append(g.resize((50, g.height), Image.NEAREST) if g.width > 50 else g)
        if len(gl) == 1:
            lay.alpha_composite(gl[0], (px + 9, py + 30))
        else:
            lay.alpha_composite(gl[0], (px + 9, py + 25))                  # 두 줄 사이 1칸(붙으면 한 덩어리로 보임)
            lay.alpha_composite(gl[1], (px + 56 - gl[1].width, py + 37))
    col = np.asarray(vcol(cfg['spine'], 'Galmuri7.ttf', 8, 1)) > 0  # 5) 책등: 흰 글자 + 짙은 테두리(원본처럼), 세로
    if col.shape[0] > sy1 - sy0 - 2:
        col = np.asarray(Image.fromarray(col.astype(np.uint8) * 255).resize((col.shape[1], sy1 - sy0 - 2), Image.NEAREST)) > 0
    put_center(lay, _outlined_bits(col, (255, 255, 255), cmpr_edge((255, 255, 255), lc)), (sx0, sy0, sx1, sy1))
    tims = []                                                     # 6) 표지 제목: 두 줄 왼쪽 맞춤(윗줄 시작에 아랫줄 맞춤), 오른쪽 테두리선(cx+124~127)은 넘지 않게
    for t in cfg['title']:
        g = np.asarray(pixel_text(t, 'Galmuri11-Bold.ttf', 12, (255, 255, 255)).getchannel('A')) > 0
        if g.shape[1] > 54:
            g = np.asarray(Image.fromarray(g.astype(np.uint8) * 255).resize((54, g.shape[0]), Image.NEAREST)) > 0
        tims.append(_outlined_bits(g, (255, 255, 255), cmpr_edge((255, 255, 255), pc)))
    x0 = round((cx + 66 + cx + 121) / 2 - tims[0].width / 2)
    x0 = min(x0, cx + 123 - max(t.width for t in tims))
    for t, (y0, y1) in zip(tims, ((304, 318), (319, 332))):
        lay.alpha_composite(t, (x0, round((y0 + y1) / 2 - t.height / 2)))
    return clean, lay, total, (0, 0, a.shape[1], a.shape[0])

def cmpr_best(img):
    """CMPR 인코더(품질 우선): 4x4 칸마다 끝점 후보(칸 안 픽셀 색 모든 쌍 + 주축 양 끝)를 RGB565 로 줄여 넣어 보고
    4색 팔레트 오차 합이 가장 작은 쌍을 고른다. 흰 글자+짙은 테두리+바탕처럼 대비가 큰 칸의 얼룩을 줄인다(빌드용 인코더와 같은 규칙)."""
    a = np.asarray(img.convert('RGBA')).astype(float).copy(); H, W = a.shape[:2]
    for by in range(0, H, 4):
        for bx in range(0, W, 4):
            blk = a[by:by + 4, bx:bx + 4, :3]; sh = blk.shape; px = blk.reshape(-1, 3)
            uniq = np.unique(px.round(), axis=0)
            if len(uniq) == 1:
                q, _ = _q565(uniq[0]); a[by:by + 4, bx:bx + 4, :3] = q; continue
            mu = px.mean(0); v = np.linalg.svd(px - mu, full_matrices=False)[2][0]; t = (px - mu) @ v
            cands = [(mu + v * t.max(), mu + v * t.min())]
            cands += [(uniq[i], uniq[j]) for i in range(len(uniq)) for j in range(i + 1, len(uniq))]
            best = None
            for c0, c1 in cands:
                q0, q1 = _q565(c0)[0].astype(float), _q565(c1)[0].astype(float)
                pal = np.array([q0, q1, ((2 * q0 + q1) / 3).round(), ((q0 + 2 * q1) / 3).round()])
                d = ((px[:, None, :] - pal[None]) ** 2).sum(2)
                e = d.min(1).sum()
                if best is None or e < best[0]:
                    best = (e, pal, d.argmin(1))
            a[by:by + 4, bx:bx + 4, :3] = best[1][best[2]].reshape(sh)
    return Image.fromarray(a.round().astype(np.uint8), 'RGBA')

def cmpr_edge(fill, bg):
    """CMPR 에서 글자색 fill·바탕색 bg 와 한 칸에 섞여도 얼룩이 안 나는 테두리색: fill→테두리 선분의 1/3·2/3 지점에 bg 가 오도록
    테두리 = fill + (bg - fill)/k (k=2/3 또는 1/3). 0~255 로 잘리는 오차가 작고 bg 보다 충분히 어두운 쪽을 고른다."""
    f, b = np.array(fill[:3], float), np.array(bg[:3], float)
    best = None
    for k in (2 / 3, 1 / 3):
        o = f + (b - f) / k; oc = np.clip(o, 0, 255)
        err = np.abs(o - oc).sum(); dark = b.sum() - oc.sum()
        score = err - 0.5 * dark
        if best is None or score < best[0]:
            best = (score, tuple(int(v) for v in oc.round()))
    return best[1]


CUSTOM = {'1504': ('1등 축하합니다', lambda s: custom_lottery(s, 1)),
          '1505': ('2등 축하합니다', lambda s: custom_lottery(s, 2)),
          '1506': ('3등 축하합니다', lambda s: custom_lottery(s, 3)),
          '1517': ('섬 안내서', custom_shiori), '1518': ('섬 안내서', custom_shiori), '1519': ('섬 안내서', custom_shiori),
          '588': ('섬 안내서 ×2', lambda s: custom_shiori_big(s, [(0, 64), (64, 128)], [0, 1])),
          '1093': ('섬 안내서 ×3', lambda s: custom_shiori_big(s, [(0, 43), (43, 85), (85, 128)], [0, 1, 1])),
          '1520': ('사무소 소식', custom_tyousha_news),
          '1522': ('마을의 소리', custom_muranokoe),
          '422': ('공포!! 뱀 여자', custom_hebionna), '1112': ('공포!! 뱀 여자', custom_hebionna),
          '427': ('데스네~ 컴퍼니', custom_desune),
          '414': ('프리미엄 1월호', custom_premium), '1375': ('자모니카 학습장', custom_jamonica), '1043': ('공정표', custom_koteihyou),
          '1024': ('골인 결혼', custom_goalin), '568': ('나나시섬 복권 -규칙-', custom_lottery_rule), '608': ('루미코', custom_rumiko),
          '1844': ('키 퍼슨 / 쓰레기 줍기', custom_keyperson), '2172': ('계약서', custom_contract),
          '2173': ('계약서+포클 서명', lambda s: custom_contract(s, True)),
          '2455': ('키친', custom_kitchen), '2457': ('알바 모집', custom_baito), '1530': ('킹과 벌금', custom_kingfine),
          '1676': ('메이어 저택 낙서', custom_1676), '1917': ('타오 낙서', custom_1917), '2059': ('앤 낙서', custom_2059),
          '681': ('할머니 편지', custom_letter),
          '2223': ('새전 낙서', custom_2223), '1031': ('연승', custom_rensho),
          '1545': ('식물 도감', lambda s: custom_zukan(s, '1545')), '1546': ('물고기 도감', lambda s: custom_zukan(s, '1546')),
          '1547': ('버섯 도감', lambda s: custom_zukan(s, '1547'))}
for _n, _i in zip((1, 2, 3, 4, 5, 6), ('1556', '1559', '1560', '1561', '1562', '1563')):
    CUSTOM[_i] = ('자료%d' % _n, lambda s, n=_n: custom_shiryou(s, n))


SOFT = {'2455', '2457', '1530', '1545', '1546', '1547'}
NO_SOFTEN = {'1545', '1546', '1547'}                                # 흰 글자+짙은 테두리(표지)·도트 이름 → 번짐 없이 압축만(10/2 사용자 지적: 글자 둘레 지저분)                                     # 이 묶음부터 「부드럽게+CMPR」 기본(10/2 사용자)


def preview(ids):
    R = g2.rows(); os.makedirs(OUT, exist_ok=True)
    for i in ids:
        text, fn = CUSTOM[i]
        src = Image.open(os.path.join(G, R[i.rstrip('b')]['png'])).convert('RGBA')
        clean, out, n, box = fn(src)
        bad = changed_outside(src, out, box)                       # 칸 밖 변경은 압축 흉내 전에 잰다
        if i in SOFT:                                              # 원본 질감 맞추기: 글자 번짐 + CMPR(게임 화면과 같은 뭉개짐)
            out = cmpr_best(out if i in NO_SOFTEN else soften(clean, out))   # 테두리 글자는 번짐 없이(번지면 4x4 칸 얼룩이 커짐)
        clean.save(os.path.join(OUT, '%s_clean.png' % i)); out.save(os.path.join(OUT, '%s_ko.png' % i))
        k = max(2, min(8, 384 // max(src.size)))
        grid([label(scale(src, k), '#%s 원본' % i), label(scale(clean, k), '지운 뒤 (%d px)' % n),
              label(scale(out, k), '한글: %s · 칸 밖 변경 %d' % (text, bad))], 3).save(os.path.join(OUT, 'sheet_%s.png' % i))
        print(i, '지운 픽셀', n, '칸 밖 변경', bad)


if __name__ == '__main__':
    preview(sys.argv[2:])
