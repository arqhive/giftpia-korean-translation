"""GPT 그림 재작업 묶음 만들기 → work/GPT/
  원본/   GPT 에 첨부할 일본어 원본(작은 그림은 픽셀 그대로 키운 _N배 판도)
  참고/   지금 패치에 들어간 한글판(빌드 디스크에서 다시 꺼낸 것)
  결과/   사용자가 GPT 결과를 「저장할 이름」으로 넣는 곳
  목록.json, 요청서.md

  python tools/gpt_prepare.py [빌드 폴더(기본 build/v012)]
"""
import csv
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gpt_jobs
import texenc
import thp
import u8

ROOT = gpt_jobs.ROOT
GPT = os.path.join(ROOT, 'work', 'GPT')
SURV = os.path.join(ROOT, 'work', 'gfx_survey')
FMT = {14: 'CMPR', 6: 'RGBA8', 5: 'RGB5A3', 4: 'RGB565'}


def dat_files(p):
    d = open(p, 'rb').read(); _, _, ents = u8.parse(d)
    return {q: d[a:a + b] for i, q, a, b in ents if a is not None}


def tex_image(files, png):
    r = IDX[os.path.normpath(png)]
    rel = 'preload.cmb' if r['src'].startswith('preload/') else r['src']
    return texenc.decode(files[rel], *texenc.locate(files[rel], r['src'], r['label'])).convert('RGBA'), r['src']


def model_silhouette(path, W=1000):
    """3D 글자 모델의 삼각형을 정면에서 꽉 채워 그린 흰 바탕 검은 글자."""
    from PIL import ImageDraw
    import hsd
    import model_ko
    T = [t for s in model_ko.slots(hsd.Hsd(path)) for t in s[2]]
    xs = [p[0] for t in T for p in t]; ys = [p[1] for t in T for p in t]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys); s = (W - 40) / (x1 - x0)
    im = Image.new('L', (W, int((y1 - y0) * s) + 40), 255); d = ImageDraw.Draw(im)
    for t in T:
        d.polygon([((p[0] - x0) * s + 20, (y1 - p[1]) * s + 20) for p in t], fill=0)
    return im


def up(im):
    """긴 변이 512 근처가 되도록 정수배 픽셀 확대(작은 그림만)."""
    k = 512 // max(im.size)
    return (im.resize((im.width * k, im.height * k), Image.NEAREST), k) if k >= 2 else (None, 1)


def main(W):
    global IDX
    IDX = {os.path.normpath(r['path']): r for r in csv.DictReader(open(os.path.join(SURV, 'index.csv'), encoding='utf-8'))}
    for d in ('원본', '참고', '결과'):
        os.makedirs(os.path.join(GPT, d), exist_ok=True)
    O = dat_files(os.path.join(ROOT, 'extract', 'giftpia.dat')); N = dat_files(os.path.join(ROOT, W, 'giftpia.dat'))
    J = gpt_jobs.jobs()
    for j in J:
        att = []
        if j['kind'] == 'tex':
            o, src = tex_image(O, j['png']); j['src'] = src
            a = np.asarray(o)[..., 3]
            if not j['fit']:
                j['fit'] = 'alpha' if (a < 250).any() else 'frame'
            j['bg'] = '투명 포함(모양은 원본 그대로)' if j['fit'] == 'alpha' else ('투명 배경' if j['fit'] == 'ink' else '불투명(그림 전체)')
            p = f'{j["id"]}_원본_{j["w"]}x{j["h"]}.png'; o.save(os.path.join(GPT, '원본', p)); att.append('원본\\' + p)
            big, k = up(o)
            if big:                                         # 확대판만 첨부(원래 크기 원본은 폴더에만 둠 — 프롬프트의 「첫 번째·두 번째 그림」 순서 유지)
                p = f'{j["id"]}_원본_{k}배_{big.width}x{big.height}.png'; big.save(os.path.join(GPT, '원본', p)); att[0] = '원본\\' + p
            if j['id'][0] == 'A':
                c, _ = tex_image(N, j['png'])
                c = up(c)[0] or c
                p = f'{j["id"]}_현재한글판.png'; c.save(os.path.join(GPT, '참고', p)); att.append('참고\\' + p)
            j['size'] = f'{j["w"]}×{j["h"]}'; j['fmt_name'] = FMT.get(j['fmt'], str(j['fmt']))
        elif j['kind'] == 'banner':
            b = open(os.path.join(ROOT, 'extract', 'opening.bnr'), 'rb').read()
            o = texenc.decode(b, 0x20, 96, 32, 5).convert('RGBA')
            j['fit'] = 'ink' if (np.asarray(o)[..., 3] < 250).any() else 'frame'
            j['bg'] = '투명 배경' if j['fit'] == 'ink' else '불투명(그림 전체)'
            o.save(os.path.join(GPT, '원본', 'B01_원본_96x32.png'))
            big = o.resize((384, 128), Image.NEAREST); big.save(os.path.join(GPT, '원본', 'B01_원본_4배_384x128.png'))
            att.append('원본\\B01_원본_4배_384x128.png')
            c, _ = tex_image(N, next(x['png'] for x in J if x['id'] == 'A2513'))
            c.save(os.path.join(GPT, '참고', 'B01_타이틀로고_현재한글판.png')); att.append('참고\\B01_타이틀로고_현재한글판.png')
            j['size'] = '96×32'; j['fmt_name'] = 'RGB5A3'
        elif j['kind'] == 'model':
            # 모델 삼각형을 꽉 채워 그린 실루엣(게임에서 보이는 글자 모양). 예전 첨부(꼭짓점을 점으로 찍은 조사용 투영)는
            # GPT 가 점선 글자로 따라 그려서 못 씀(10/12)
            o = model_silhouette(os.path.join(ROOT, 'extract', 'dat', 'map', 'worldmap', j['src'] + '.dat'))
            p = f'{j["id"]}_원본_모델실루엣.png'; o.save(os.path.join(GPT, '원본', p)); att.append('원본\\' + p)
            c = model_silhouette(os.path.join(ROOT, 'work', 'model', j['src'] + '.dat'))
            p = f'{j["id"]}_현재한글판.png'; c.save(os.path.join(GPT, '참고', p)); att.append('참고\\' + p)
            j['size'] = '글자 모양만'; j['bg'] = '흰 바탕 검은 글자'; j['fit'] = 'mask'; j['fmt_name'] = '3D 모델'
        else:
            to = thp.Thp(os.path.join(ROOT, 'extract', 'gift', 'mov', 'opening.thp'))
            tn = thp.Thp(os.path.join(ROOT, 'work', 'movie', 'opening.thp'))
            o = to.image(j['frame']).convert('RGB'); j['w'], j['h'] = o.size
            p = f'{j["id"]}_원본_프레임{j["frame"]}.png'; o.save(os.path.join(GPT, '원본', p)); att.append('원본\\' + p)
            p = f'{j["id"]}_현재한글판.png'; tn.image(j['frame']).convert('RGB').save(os.path.join(GPT, '참고', p)); att.append('참고\\' + p)
            j['size'] = f'{o.width}×{o.height}'; j['bg'] = '불투명(화면 전체)'; j['fit'] = 'video'; j['fmt_name'] = 'THP 영상'
        j['attach'] = att; j['save'] = j['id'] + '.png'
    json.dump(J, open(os.path.join(GPT, '목록.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    write_request(J)
    print('묶음 %d개(A %d · N %d · B %d · M %d · V %d) → %s' % (len(J), *(sum(j['id'][0] == c for j in J) for c in 'ANBMV'), GPT))


COMMON = '''닌텐도 게임큐브 게임 「기프트피아(ギフトピア)」의 그림을 한국어판으로 바꾸는 작업이야.
네가 만든 PNG를 내가 프로그램으로 원래 크기로 줄이고 게임 형식으로 다시 인코딩해서 넣을 거라서,
아래 규칙을 반드시 지켜야 해.

[필수 규칙]
1. 결과는 반드시 PNG. JPG 금지.
2. 첨부한 원본과 가로세로 비율을 똑같이 맞춰. 크기는 원본보다 크게(긴 변 512픽셀 이상) 만들어.
   (첨부가 픽셀을 키운 그림이면 그 비율 그대로)
3. 그림 전체를 원본과 같은 구도로 다시 그리고, 일본어 글자만 내가 준 한국어로 바꿔.
   그림·색·테두리·배경 무늬·위치는 원본 그대로 둬. 새로 그려 넣는 것 금지(테두리 상자, 받침 판, 워터마크, 서명 금지).
4. 내가 "투명 배경"이라고 한 그림은 글자 밖을 완전히 투명하게. 흰 배경·체크무늬 금지.
5. 글자는 원본의 서체 느낌(굵기·기울기·손글씨/인쇄체), 색, 외곽선, 크기, 정렬을 따라 해.
   한국어가 길면 글자 폭을 조금 좁혀서라도 원본 글자가 있던 자리 안에 넣어.
6. 한국어 맞춤법과 글자 모양을 정확하게. 받침이 빠지거나 획이 붙거나 깨지면 안 돼.
   다 만든 뒤에 글자를 한 자씩 확인하고, 틀렸으면 다시 만들어.
7. 내가 준 문구를 그대로 써. 띄어쓰기·문장부호도 바꾸지 마. 「 / 」는 줄바꿈 표시야.
8. 영어·숫자로 된 부분은 번역하지 말고 원본 그대로 둬.

이해했으면 "확인"이라고만 답하고, 내가 그림을 보낼 때까지 기다려.'''


def prompt(j):
    if j['kind'] == 'banner':
        return ('첨부한 첫 번째 그림은 게임큐브 디스크 배너(실제 크기 96×32 픽셀)를 4배로 키운 거야. 영어 로고 「GIFTPIA」가 그려져 있어.\n'
                '같은 구성으로 한국어 배너 「기프트피아」를 그려 줘. 비율 3:1. 원본처럼 투명한 곳은 투명하게.\n'
                '- 글자마다 원본처럼 다른 색(빨강·주황·노랑·연두·파랑·보라 계열)에 짙은 자주색 외곽선, 원본의 귀 모양 장식(안테나)도 비슷한 자리에.\n'
                '- 두 번째 그림은 지금 패치의 타이틀 로고(한글 「기프트피아」)야. 글자 느낌을 이것과 어울리게.\n'
                '- 아주 중요: 96×32 픽셀로 줄어들어. 줄여도 읽히도록 획을 굵고 단순하게, 외곽선은 한 겹만 두껍게, 자잘한 무늬는 빼.')
    if j['kind'] == 'model':
        return (f'첨부한 첫 번째 그림은 {j["cat"]}을 정면에서 본 글자 모양(실루엣)이고, 두 번째 그림이 지금 쓰는 한글 모양이야.\n'
                '이 그림의 검은 모양을 그대로 3D 모델 삼각형으로 바꿀 거라서, 글자 모양만 필요해.\n'
                f'첫 번째 그림의 둥근 손글씨 서체 그대로 「{j["ko"]}」를 그려 줘. 흰 바탕에 획 속을 순수한 검정(#000000)으로 꽉 채운 글자.\n'
                '점선·윤곽선·그림자·입체감·색 금지. 글자 사이는 확실히 띄우고(서로 닿으면 안 됨), 한 줄로.\n'
                'ㅇ·ㅁ·ㅂ·ㅌ 속 빈 곳은 흰색으로 비워 두고, ㅔ·ㅌ 처럼 나란한 획 사이도 흰 틈이 분명히 보이게.\n'
                '글자 하나하나가 따로 움직이는 모델이라 각 글자 안의 획은 서로 붙어 있어도 되지만 글자끼리는 떨어져야 해.')
    if j['kind'] == 'video':
        return (f'첨부한 첫 번째 그림은 오프닝 영상의 한 장면이고, 일본어 자막 「{j["jp"]}」이 그림 위에 손글씨로 쓰여 있어.\n'
                f'같은 장면을 그대로 두고 자막만 한국어 「{j["ko"]}」로 바꿔 줘(「 / 」는 줄바꿈).\n'
                '원본 자막처럼 먹색 손글씨, 같은 위치·크기·기울기. 장면 그림은 바꾸지 마. 두 번째 그림은 지금 한글판이야.')
    bg = {'ink': '투명 배경. 글자(로고)만 그려.', 'alpha': '원본처럼 투명한 부분은 투명하게 두고 모양을 바꾸지 마.',
          'frame': '배경까지 그림 전체를 다시 그려.'}[j['fit']]
    tail = '\n두 번째 그림은 지금 쓰는 한글판이야. 문구는 같게, 그림 품질만 원본 수준으로 맞춰 줘.' if j['id'][0] == 'A' else ''
    return (f'첨부한 첫 번째 그림(일본어 원본, 실제 게임 크기 {j["size"]})을 한국어로 다시 그려 줘. {bg}\n'
            f'바꿀 글자: 「{j["jp"]}」 → 「{j["ko"]}」{tail}')


def write_request(J):
    L = ['# GPT 그림 재작업 요청서 (기프트피아 한글 패치)', '',
         'GPT(ChatGPT 이미지 생성)에게 그림을 다시 그려 달라고 할 때 쓰는 프롬프트입니다.',
         '결과 PNG를 받아서 게임 크기·형식(CMPR·RGB5A3 등)에 맞춰 넣습니다. **필요한 것만 골라서 맡기면 됩니다.**', '',
         '## 폴더', '', '| 폴더 | 내용 |', '|---|---|',
         '| `work\\GPT\\원본\\` | GPT에 첨부할 일본어 원본. 작은 그림은 픽셀 그대로 키운 `_N배` 판이 있습니다(첨부는 확대판 권장). |',
         '| `work\\GPT\\참고\\` | 지금 패치에 들어간 한글판(`_현재한글판`, 빌드 디스크에서 다시 꺼낸 것). |',
         '| `work\\GPT\\결과\\` | **GPT가 만든 PNG를 여기에 저장합니다.** 「저장할 이름」을 그대로 써 주세요(예: `A76.png`). |',
         '| `work\\GPT\\비교\\` | 반영하면 원본 \\| 현재 \\| GPT 반영(게임 형식으로 바꿨다 푼 모양) 비교 시트가 생깁니다. |', '',
         '결과를 저장한 뒤 저에게 말하면 `python tools/gpt_import.py`(또는 `… A76 N1274`처럼 번호 지정)로 크기를 맞춰 넣고 비교 시트를 보내 드립니다.',
         '- 결과가 원본과 비율이 다르면 경고만 하고, 그림 전체를 게임 크기로 줄입니다(게임 크기 그대로 와도 됩니다).',
         '- 투명이 있는 탭·아이콘은 원본 투명도(모양)를 그대로 쓰고 색만 GPT 그림에서 가져옵니다.',
         '- N 번호(아직 일본어인 그림)는 반영하면 목록 파일에서 「확정」으로 바뀝니다. 한국어는 **번역안**이라 바꾸고 싶으면 말해 주세요.',
         '- M(3D 글자 모델)은 검은 글자 실루엣만 받아서 모델 삼각형으로 바꿉니다. V(영상 자막)는 장면 그림을 받아 자막 부분만 영상에 섞습니다.', '',
         '## 1. 맨 처음 한 번만 붙여 넣을 공통 규칙', '', '```', COMMON, '```', '']
    groups = [('A', 'A. 이미 번역한 그림 다시 그리기 (반영하면 바로 빌드에 들어감)'),
              ('N', 'N. 아직 일본어인 그림 (한국어는 번역안)'),
              ('B', 'B. 디스크 배너 그림'), ('M', 'M. 3D 글자 모델'), ('V', 'V. 오프닝 영상 자막 카드')]
    L += ['## 2. 목록', '']
    for g, title in groups:
        S = [j for j in J if j['id'][0] == g]
        L += [f'### {title} — {len(S)}개', '', '| 번호 | 분류 | 원문 | 한국어 | 게임 크기 | 배경 | 저장할 이름 |', '|---|---|---|---|---|---|---|']
        for j in S:
            L.append(f'| {j["id"]} | {j["cat"]} | {j["jp"]} | {j["ko"]} | {j["size"]} | {j["bg"]} | `{j["save"]}` |')
        L.append('')
    L += ['## 3. 그림별 요청', '', '첨부 파일은 `work\\GPT\\` 기준 경로입니다.', '']
    for j in J:
        L += [f'### {j["id"]} {j["cat"]}', '']
        if j.get('note'):
            L += [f'> {j["note"]}', '']
        L += ['첨부: ' + ', '.join(f'`{a}`' for a in j['attach']), '', '```', prompt(j), '```', '']
    open(os.path.join(GPT, '요청서.md'), 'w', encoding='utf-8').write('\n'.join(L))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join('build', 'v012'))
