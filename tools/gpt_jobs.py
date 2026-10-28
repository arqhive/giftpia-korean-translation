"""GPT 그림 재작업 대상 목록(gpt_prepare·gpt_import 가 같이 쓴다).

번호 체계
  A<n> : 이미 번역한 그림(graphics_list.csv 「확정」). 결과 → work/gfx/final/<n>.png → build.py 가 게임에 넣음
  N<n> : 일본어가 남은 그림(제외·원본 유지·새로 찾음). 반영하면 graphics_list.csv 를 「확정」으로 바꾸고 final 을 채운다
  M1·M2: 3D 글자 모델(게임 오버 / 끝). 결과(검은 글자) → 글자 모양 마스크 → tools/model_ko.py 가 삼각형으로 만든다
  B01  : 디스크 배너 그림(opening.bnr 96x32). 결과 → work/gfx/final/banner.png → build.py 의 build_banner
  V01~V12: 오프닝 영상 자막 카드. 결과(카드 화면 전체) → tools/movie_ko.py build 가 영상에 섞어 넣는다
fit
  frame : 불투명 그림. 그림 전체를 게임 크기로 줄인다
  alpha : 투명이 있는 그림(탭·아이콘 모양). 그림 전체를 줄이고 투명도는 원본 것을 그대로 쓴다(글자가 투명도에 없는 그림)
  ink   : 글자 자체가 투명도인 로고. GPT 그림의 불투명 덩어리를 원본 덩어리 상자에 비율 유지로 넣는다
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)

LOGOS = {'2513', '2517', '2518', '2519', '2520', '2521', '2522', '2523'}

# 미번역 그림: n → (한국어 번역안, 메모). 번역안은 확정 전(사용자 확인 필요)
NEW = {
    '1274': ('컴플리트까지 / 앞으로', '이전 결정: 제외(A) · 사진 수집 카운터 위 표지(UI처럼 보임) · 「완성까지」도 후보'),
    '1471': ('통장 ▲ / 캐시카드 ▲ / 현금 출구', '이전 결정: 제외(A) · ATM 앞판'),
    '1166': ('온에어 중에는 / 여닫기 엄금!', '이전 결정: 제외(A) · 방송국 문 표지(대사 표기 「온에어」)'),
    '1892': ('낚시 금지', '이전 결정: 제외(A) · 세로 표지(대사 표기 「낚시 금지」)'),
    '2078': ('출입 금지', '이전 결정: 제외(A) · 세로 표지'),
    '2291': ('이 물건은 나나시섬의 / 소유 물건입니다. / (작은 줄: 판독 불확실) / 나나시 촌장 메이어',
             '이전 결정: 제외(A) · 세로 안내판(대사 표기 「이 물건은 … 소유 물건입니다」), 작은 줄은 원문 판독 필요'),
    '635': ('(원문 판독 필요)', '이전 결정: 제외(A) · DJ 부스 빨간 가타카나(ヤモミナガメ?)'),
    '2276': ('방재', '새로 찾음 · 빨간 원 안 한자 「防」(방재 두건) — 699와 같은 마크'),
    '699': ('방재', '이전 결정: 제외(B) · 방재 두건 「防」 마크'),
    '2601': ('오른열 왼열 오른닫 오른열 / 왼닫 오른닫 오른열', '새로 찾음 · 메트 집 서랍 퍼즐 순서(대사 E13182). 투명 바탕에 짙은 회색 손글씨만, 원본처럼 두 줄'),
    '2602': ('아침 10시에 찾아라 / 라카타', '새로 찾음 · 산장 벽 힌트(대사 E14383, 라카타=보물 사냥꾼 이름). 투명 바탕에 검은 글씨, 첫 줄 크게·둘째 줄 오른쪽 서명'),
    '1964': ('마도로스', '새로 찾음 · 바위 무덤에 세로로 새긴 「マドロス」(10/28 사용자 판독) — 돌에 새긴 느낌 유지'),
    '589': ('나', '새로 찾음 · 편의점 마스코트 몸통 「ナ」 표식(원본 유지 후보)'),
    '258': ('차', '이전 결정: 제외(B) · 「茶」 원형 마크(251·1824·1828 「차」와 같은 결)'),
    '1935': ('밭', '이전 결정: 제외(B) · 「畑」 한 글자 표지'),
    '1969': ('(원문 판독 필요)', '이전 결정: 제외(C) · 현수막의 세로 일본어 쪽지(작음)'),
    '2481': ('젤리', '이전 결정: 제외(C) · 16×16 아이템 아이콘, 「ゼリー」로 보임(판독 불확실)'),
    '156': ('촌장', '이전 결정: 원본 유지 · 메이어 옷의 「村」 원형 배지 → 「촌장」(10/12 사용자 결정, 「마을」에서 바꿈)'),
    '1517': ('섬 안내서', '이전 결정: 원본 유지 · 「島のしおり」 책자(작업본 있었음)'),
    '1518': ('섬 안내서', '이전 결정: 원본 유지 · 「島のしおり」 책자(작업본 있었음)'),
    '1519': ('섬 안내서', '이전 결정: 원본 유지 · 「島のしおり」 책자(작업본 있었음)'),
    '1564': ('(원문 판독 필요)', '이전 결정: 원본 유지 · 텐진 고문서풍 손글씨 도감'),
    '1689': ('텐진 랜드', '이전 결정: 원본 유지 · 손글씨 가타카나 현수막(작업본 있었음)'),
    '1807': ('BAR 오스메스', '이전 결정: 원본 유지 · 간판 2개(용어집 「바 오스메스」, BAR 는 영어 유지)'),
    '2189': ('뷰티풀 나나시', '이전 결정: 원본 유지 · 쓰레기통 글씨(작업본 있었음)'),
}

MODELS = [('M1', '3D 글자 모델 「ゲームオーバー」', '게임 오버', 'haraheri_endtxt', '게임오버'),
          ('M2', '3D 글자 모델 「おわり？」(？는 원본 모델 그대로)', '끝', 'dmy_endtxt', '끝')]

VIDEO_REFS = [360, 720, 870, 1505, 1866, 2226, 2585, 4070, 4185, 4780, 4890, 5070]   # movie_ko.REFS 와 같음


def ko_texts():
    """확정 그림의 한국어 문구(그림 스크립트의 번호별 표에서)."""
    import gfx_g1 as g1, gfx_g2 as g2, gfx_g3 as g3
    M = {k: t for k, (t, _) in g1.TABS.items()}
    M.update({k: '기프트피아 (로고, ™ 왼쪽)' for k in g1.LOGOS})
    M.update({k: v['text'] for k, v in g2.SPEC.items()})
    M.update({k: v[0] for k, v in g2.CUSTOM.items()})
    M.update({k: v[0] for k, v in g3.CUSTOM.items()})
    return M


def jobs():
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'translation', 'graphics_list.csv'), encoding='utf-8-sig')))
    ko = ko_texts(); out = []
    for r in rows:
        n = r['n']
        if r['status'] == '확정' and r['png'].startswith('tex/') and n not in NEW:   # N 그림은 GPT 로 확정돼도 N 번호 그대로
            out.append(dict(id='A' + n, n=n, kind='tex', png=r['png'], w=int(r['w']), h=int(r['h']), fmt=int(r['fmt']),
                            cat=r['category'], jp=r['text'], ko=ko[n], note='', status=r['status']))
    sheet = {r['n']: r for r in csv.DictReader(open(os.path.join(ROOT, 'work', 'gfx_survey', 'sheets', 'sheet_index.csv'), encoding='utf-8'))}
    byn = {r['n']: r for r in rows}
    for n, (k, note) in NEW.items():
        r = byn.get(n)
        if r:
            png, w, h, fmt, cat, jp = r['png'], int(r['w']), int(r['h']), int(r['fmt']), r['category'], r['text']
        else:                                               # 목록에 없던 새 그림(시트 번호)
            s = sheet[n]; png = s['path'].replace('\\', '/'); w, h, fmt = int(s['w']), int(s['h']), int(s['fmt']); cat, jp = '', ''
        out.append(dict(id='N' + n, n=n, kind='tex', png=png, w=w, h=h, fmt=fmt, cat=cat, jp=jp, ko=k, note=note,
                        status=r['status'] if r else '목록 없음'))
    out.append(dict(id='B01', n='banner', kind='banner', png='', w=96, h=32, fmt=5, cat='디스크 배너 그림', jp='GIFTPIA (영문 로고)',
                    ko='기프트피아', status='확정',
                    note='게임 목록·메모리 카드 화면에 나오는 96×32 배너. 반영하면 work/gfx/final/banner.png → build.py 가 opening.bnr 교체. '
                         '배너 문자열(제목·설명)은 SJIS 라 한글 불가, 그대로 둠'))
    for i, cat, ko_, src, chars in MODELS:
        out.append(dict(id=i, n=i, kind='model', png='', w=0, h=0, fmt=0, cat=cat, jp='', ko=ko_, src=src, chars=chars, status='확정',
                        note='글자 %d개를 따로 움직이는 모델이라 글자끼리 떨어져 있어야 함' % len(chars)))
    cards = json.load(open(os.path.join(ROOT, 'translation', 'opening_ko.json'), encoding='utf-8'))['cards']
    for k, (c, f) in enumerate(zip(cards, VIDEO_REFS), 1):
        out.append(dict(id='V%02d' % k, n='V%02d' % k, kind='video', png='', w=0, h=0, fmt=0, cat='오프닝 자막 카드 %d' % k,
                        jp=' / '.join(c['jp']), ko=' / '.join(c['ko']), note='', frame=f, status='확정'))
    for j in out:
        if j['kind'] == 'tex':
            j['fit'] = 'ink' if j['n'] in LOGOS else None              # alpha / frame 은 원본 투명도를 보고 gpt_prepare 가 정한다
    return out


def name(j):
    """결과 파일 이름(확장자 없이)."""
    return j['id']
