"""GPT 가 다시 그린 그림을 게임 크기로 맞춰 반영하고 비교 시트를 만든다(목록은 work/GPT/목록.json, gpt_prepare 가 만듦).

  work/GPT/결과/<번호>.png
    A·N(그림) → work/gfx/final/<n>.png (바꾸기 전 파일은 work/GPT/이전_final/ 에 보관)
                N 은 translation/graphics_list.csv 를 「확정」, final 경로로 고친다(이전 상태는 work/GPT/이전_목록.csv)
    M(3D 글자) → work/GPT/모델/<M1|M2>.png 글자 마스크 → tools/model_ko.py 를 다시 돌려 work/model/*.dat
    V(영상 자막) → work/movie/gpt/card<NN>.png → tools/movie_ko.py build 를 다시 돌려야 영상에 들어감(오래 걸려 여기서는 안 돌림)
  비교 시트: work/GPT/비교/<번호>.png (원본 | 현재 | GPT 반영, 그림은 게임 형식으로 바꿨다 푼 모양)

맞추는 방식(결과가 이미 게임 크기면 그대로)
  frame 그림 전체를 게임 크기로 / alpha 그림 전체를 줄이고 투명도는 원본 것 / ink 불투명 덩어리를 원본 덩어리 상자에 비율 유지
사용: python tools/gpt_import.py                결과 폴더에 있는 것 전부
      python tools/gpt_import.py A76 N1274       번호 지정
      python tools/gpt_import.py --dry …        비교 시트만 만들고 아무것도 바꾸지 않음
"""
import csv
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import texenc

ROOT = os.path.normpath(os.path.join(HERE, '..'))
GPT = os.path.join(ROOT, 'work', 'GPT')
LIST = os.path.join(ROOT, 'translation', 'graphics_list.csv')


def premul_resize(im, size):
    a = np.asarray(im.convert('RGBA'), np.float32) / 255
    a[..., :3] *= a[..., 3:4]
    ch = [Image.fromarray(a[..., i], 'F').resize(size, Image.LANCZOS) for i in range(4)]
    r = np.stack([np.asarray(c, np.float32) for c in ch], -1).clip(0, 1)
    r[..., :3] = np.where(r[..., 3:4] > 1e-4, r[..., :3] / np.maximum(r[..., 3:4], 1e-4), 0)
    return Image.fromarray((r * 255 + .5).clip(0, 255).astype(np.uint8), 'RGBA')


def bbox(alpha, thr=16):
    ys, xs = np.where(alpha > thr)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def fit(gpt, orig, mode):
    w, h = orig.size
    g = gpt.convert('RGBA')
    if mode == 'ink':
        if g.size != (w, h):
            ga = np.asarray(g)
            ink = g.crop(bbox(ga[..., 3]))
            ox0, oy0, ox1, oy1 = bbox(np.asarray(orig)[..., 3])
            bw, bh = ox1 - ox0, oy1 - oy0; s = min(bw / ink.width, bh / ink.height)
            nw, nh = max(1, round(ink.width * s)), max(1, round(ink.height * s))
            out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            out.alpha_composite(premul_resize(ink, (nw, nh)), (ox0 + (bw - nw) // 2, oy0 + (bh - nh) // 2))
            g = out
        return g
    if g.size != (w, h):
        g = premul_resize(g, (w, h)) if mode == 'alpha' else g.resize((w, h), Image.LANCZOS)
    a = np.asarray(g).copy()
    if mode == 'alpha':
        a[..., 3] = np.asarray(orig)[..., 3]                    # 모양(투명도)은 원본 그대로
    else:
        a[..., 3] = 255
    return Image.fromarray(a, 'RGBA')


def glyph_fill(img):
    """3D 글자 그림 → 꽉 찬 글자 마스크(참/거짓).
    꽉 찬 글자면 잉크 그대로. GPT 가 점선 외곽선(게임 속 3D 글자 느낌)으로 그려 오면:
    점마다 가장 가까운 점 둘과 선으로 이어 외곽선을 복원하고(나란한 획의 선끼리는 붙지 않음),
    바깥에서부터 선을 몇 번 넘는지(짝·홀)로 안을 채운다 → ㅇ·ㅌ 속 구멍은 비어 있음.
    (모폴로지 닫기로 점을 잇는 방식은 ㄱ·ㅔ 처럼 가까운 획이 붙고 구멍이 메워져서 버림, 10/12)"""
    from scipy import ndimage
    from PIL import ImageDraw
    L = np.asarray(img.convert('L')).astype(int)
    ink = L > 128 if L.mean() < 128 else L < 128                     # 바탕이 어두우면 밝은 쪽이 잉크
    lab, n = ndimage.label(ink)
    sizes = ndimage.sum(ink, lab, range(1, n + 1))
    if n == 0 or np.median(sizes) > ink.size * 0.002:                # 덩어리가 크면 꽉 찬 글자
        return ink
    pts = np.array(ndimage.center_of_mass(ink, lab, range(1, n + 1)))  # 점(y, x)
    d = np.sqrt(((pts[:, None] - pts[None]) ** 2).sum(-1)); np.fill_diagonal(d, np.inf)
    nn = np.sort(d, 1)[:, 0]; dmax = np.median(nn) * 2.2
    pad = 4
    canvas = Image.fromarray(np.pad(ink, pad).astype(np.uint8) * 255); dr = ImageDraw.Draw(canvas)
    for i in range(n):
        for k in np.argsort(d[i])[:2]:
            if d[i, k] <= dmax:
                dr.line([(pts[i, 1] + pad, pts[i, 0] + pad), (pts[k, 1] + pad, pts[k, 0] + pad)], fill=255, width=2)
    line = np.asarray(canvas) > 0
    st = np.ones((3, 3), bool)
    reg, m = ndimage.label(~line)
    depth = {reg[0, 0]: 0}; frontier = [reg[0, 0]]
    while frontier:                                                  # 바깥에서 선 하나씩 건너며 깊이를 매김
        nxt = []
        for r in frontier:
            reach = ndimage.binary_dilation(reg == r, st, iterations=4) & ~line
            for q in np.unique(reg[reach]):
                if q and q not in depth:
                    depth[q] = depth[r] + 1; nxt.append(q)
        frontier = nxt
    fill = line.copy()
    for q, dp in depth.items():
        if dp % 2 == 0:
            fill &= reg != q                                          # 바깥·구멍 쪽 선 둘레는 그대로(선 굵기 2px)
        else:
            fill |= reg == q
    return fill[pad:-pad, pad:-pad]


def game(img, fmt):
    """게임 형식으로 바꿨다 푼 모양."""
    b = texenc.encode(img, fmt)
    return texenc.decode(b, 0, img.width, img.height, fmt).convert('RGBA')


def sheet(name, cols):
    font = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 16)
    w, h = cols[0][1].size
    s = max(1, min(4, 300 // max(w, h)))
    W, H = w * s, h * s
    out = Image.new('RGBA', (len(cols) * (W + 10) + 10, H + 42), (60, 90, 60, 255)); d = ImageDraw.Draw(out)
    for i, (lab, im) in enumerate(cols):
        x = 10 + i * (W + 10); d.text((x, 8), lab, fill=(255, 255, 210), font=font)
        bg = Image.new('RGBA', (W, H), (128, 128, 128, 255)); bg.alpha_composite(im.convert('RGBA').resize((W, H), Image.NEAREST))
        out.alpha_composite(bg, (x, 34))
    os.makedirs(os.path.join(GPT, '비교'), exist_ok=True)
    out.convert('RGB').save(os.path.join(GPT, '비교', name + '.png'))


def set_confirmed(n, final):
    rows = list(csv.DictReader(open(LIST, encoding='utf-8-sig')))
    if not os.path.exists(os.path.join(GPT, '이전_목록.csv')):
        shutil.copy2(LIST, os.path.join(GPT, '이전_목록.csv'))
    hit = [r for r in rows if r['n'] == n]
    if not hit:
        return False                                            # 목록에 없던 새 그림: 행을 직접 추가해야 함(아래 main 에서 알림)
    hit[0]['status'] = '확정'; hit[0]['final'] = final
    with open(LIST, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return True


def main(args):
    dry = '--dry' in args; want = [a for a in args if a != '--dry']
    J = json.load(open(os.path.join(GPT, '목록.json'), encoding='utf-8'))
    done = 0; model_changed = False
    for j in J:
        res = os.path.join(GPT, '결과', j['save'])
        gs = os.path.join(GPT, '결과', '게임크기', j['save'])    # 사용자가 게임 크기로 맞춰 준 판이 있으면 그것을 씀(큰 그림은 결과/ 에)
        if os.path.exists(gs):
            res = gs
        if want and j['id'] not in want:
            continue
        if not os.path.exists(res):
            if want:
                print('  없음  %s' % j['save'])
            continue
        gpt = Image.open(res)
        if j['kind'] in ('tex', 'banner'):                     # 배너(B01)도 그림처럼: final/banner.png → build_banner
            orig = Image.open(os.path.join(GPT, '원본', f'{j["id"]}_원본_{j["w"]}x{j["h"]}.png')).convert('RGBA')
            if abs((gpt.width / gpt.height) / (j['w'] / j['h']) - 1) > 0.03:
                print('  주의  %s 비율 %.2f (원본 %.2f)' % (j['save'], gpt.width / gpt.height, j['w'] / j['h']))
            new = fit(gpt, orig, j['fit'])
            final = os.path.join('work', 'gfx', 'final', j['n'] + '.png')
            cur = Image.open(os.path.join(ROOT, final)).convert('RGBA') if os.path.exists(os.path.join(ROOT, final)) else orig
            sheet(j['id'], [('원본', orig), ('현재', game(cur, j['fmt'])), ('GPT 반영', game(new, j['fmt']))])
            if not dry:
                if os.path.exists(os.path.join(ROOT, final)):
                    os.makedirs(os.path.join(GPT, '이전_final'), exist_ok=True)
                    keep = os.path.join(GPT, '이전_final', j['n'] + '.png')
                    if not os.path.exists(keep):                # 처음 바꾸기 전 것만 보관
                        shutil.copy2(os.path.join(ROOT, final), keep)
                new.save(os.path.join(ROOT, final))
                if j['id'][0] == 'N' and not set_confirmed(j['n'], final.replace(os.sep, '/')):
                    print('  알림  %s 는 목록 파일에 없는 그림이라 graphics_list.csv 에 행을 추가해야 빌드에 들어감' % j['id'])
            print('  %s  %s → %s (%dx%d, %s)' % ('시험' if dry else '반영', j['save'], final, j['w'], j['h'], j['fit']))
        elif j['kind'] == 'model':
            m = Image.fromarray((glyph_fill(gpt) * 255).astype(np.uint8))
            m = m.crop(m.getbbox())
            sheet(j['id'], [('현재', Image.open(os.path.join(GPT, '참고', j['id'] + '_현재한글판.png'))), ('GPT 글자 마스크', m)])
            if not dry:
                os.makedirs(os.path.join(GPT, '모델'), exist_ok=True)
                m.save(os.path.join(GPT, '모델', j['id'] + '.png')); model_changed = True
            print('  %s  %s → 3D 글자 마스크 %s' % ('시험' if dry else '반영', j['save'], j['ko']))
        else:
            ref = Image.open(os.path.join(GPT, '원본', f'{j["id"]}_원본_프레임{j["frame"]}.png')).convert('RGB')
            new = gpt.convert('RGB').resize(ref.size, Image.LANCZOS)
            sheet(j['id'], [('원본', ref), ('현재', Image.open(os.path.join(GPT, '참고', j['id'] + '_현재한글판.png'))), ('GPT 카드', new)])
            if not dry:
                os.makedirs(os.path.join(ROOT, 'work', 'movie', 'gpt'), exist_ok=True)
                new.save(os.path.join(ROOT, 'work', 'movie', 'gpt', 'card%s.png' % j['id'][1:]))
            print('  %s  %s → work/movie/gpt/card%s.png (영상에 넣으려면 python tools/movie_ko.py build)' % ('시험' if dry else '반영', j['save'], j['id'][1:]))
        done += 1
    if model_changed:
        import model_ko
        os.makedirs(model_ko.OUT, exist_ok=True); model_ko.x1(); model_ko.x2()
    print('%s %d개. 비교 시트: %s' % ('시험' if dry else '반영', done, os.path.join(GPT, '비교')))


if __name__ == '__main__':
    main(sys.argv[1:])
