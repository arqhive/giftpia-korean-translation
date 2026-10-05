"""7단계 기계 검수: 대사(evt)·실행 파일 문구(DOL)·그래픽 산출물 전수 검사 → translation/review_report.json + 요약 출력.

검사
  1 미번역·일본어 남음        2 태그·인코딩·창 폭·줄 수(check_tr)   3 문장부호(마침표 누락·…./~.·그녀)
  4 용어집 불일치             5 같은 원문 다른 번역                   6 보류 목록(pending.md) 항목
  7 DOL 서식(printf) 보존·자리 넘침   8 그래픽 산출물 규격(크기·존재)
"""
import csv
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_tr
import dol_tr

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
T = os.path.join(ROOT, 'translation')
CTL = re.compile(r'\{[0-9A-F]{2}\}')
JP = re.compile(r'[぀-ヿ一-鿿ｦ-ﾟ]')
END_OK = tuple('.!?…~♪」』)）～！？').__add__(('♥',))


def N(s):
    return unicodedata.normalize('NFKC', s)


def pages(text):
    """제어 코드 {01}{02}(페이지 끝) 기준으로 나눈 평문 조각."""
    return [CTL.sub('', p).strip() for p in re.split(r'\{0[12]\}', text) if CTL.sub('', p).strip()]


def glossary():
    out = []
    for line in open(os.path.join(T, 'glossary.md'), encoding='utf-8'):
        c = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(c) < 2 or not c[0] or c[0] in ('원문', '안') or set(c[0]) <= set('-:') or c[0].startswith('**'):
            continue
        jp, ko = N(c[0]), c[1]
        if not JP.search(jp) or not ko or JP.search(ko):
            continue
        ko = re.split(r'[(/（]', ko)[0].strip()
        for j, k in zip(jp.split(' / '), ko.split(' / ')):
            j, k = j.strip(), k.strip()
            if len(j) >= 2 and k and '→' not in k and '…' not in j:
                out.append((j, k))
    return out


def main():
    evt = json.load(open(os.path.join(T, 'evt_texts.json'), encoding='utf-8'))
    eko = json.load(open(os.path.join(T, 'evt_ko.json'), encoding='utf-8'))
    issues = defaultdict(list)
    G = glossary()
    same = defaultdict(set)
    for e in evt:
        ko = eko.get(e['id'], '')
        if not ko:
            issues['1 미번역'].append((e['id'], e['jp'][:40], ''))
            continue
        plain = CTL.sub('', ko)
        if JP.search(plain.replace('ぽ', '')):
            issues['1 일본어 남음'].append((e['id'], e['jp'][:40], ko[:60]))
        for lv, msg in check_tr.check({'jp': e['jp'], 'ko': ko, 'kind': e['kind']}):
            key = '2 ' + ('태그·인코딩' if '제어' in msg or '변환' in msg or '서식' in msg else '창 폭·줄 수' if ('자 >' in msg or '줄 >' in msg) else '기타')
            if '말줄임표' in msg or '그녀' in msg or '직역' in msg:
                key = '3 문장부호·문체'
            issues[key + (' (오류)' if lv == 'error' else ' (경고)')].append((e['id'], msg, ko.replace('\n', '⏎')[:60]))
        if e['kind'] == 'dialog':                                  # 마침표 누락: 원문 조각이 。로 끝나는데 번역 조각이 부호 없이 끝남
            jp_p, ko_p = pages(N(e['jp'])), pages(ko)
            if len(jp_p) == len(ko_p):
                for a, b in zip(jp_p, ko_p):
                    if a.endswith('。') and b and b[-1] not in END_OK and re.match(r'[가-힣]', b[-1]):
                        issues['3 마침표 누락 (경고)'].append((e['id'], a[-20:], b[-30:])); break
        jn = N(CTL.sub('', e['jp']))
        for j, k in G:                                             # 용어집: 원문에 용어가 있는데 번역에 한국어 표기가 없음
            if j in jn and k.replace(' ', '') not in plain.replace(' ', ''):
                issues['4 용어집 불일치 (경고)'].append((e['id'], '%s → %s' % (j, k), plain[:60]))
        if len(jn) >= 4:
            same[jn].add(plain.strip())
    for jn, kos in same.items():                                   # 같은 원문 다른 번역(부호·띄어쓰기만 다른 것은 제외)
        canon = {re.sub(r'[\s.,!?…~～]', '', k) for k in kos}
        if len(canon) > 1:
            issues['5 같은 원문 다른 번역 (참고)'].append(('', jn[:40], ' ∥ '.join(sorted(kos))[:120]))
    for e in evt:                                                  # 6 보류 목록
        ko = eko.get(e['id'], '')
        if '水かけ草' in N(e['jp']) and '물 주는 풀' not in ko:
            issues['6 보류: 水かけ草→물 주는 풀'].append((e['id'], N(e['jp'])[:40], ko[:60]))
        if 'むらさきキノコ' in N(e['jp']) and '보라 버섯' not in ko:
            issues['6 보류: むらさきキノコ→보라 버섯'].append((e['id'], N(e['jp'])[:40], ko[:60]))
    # 7 DOL
    L, dko = dol_tr.load()
    for x in L:
        k = dko.get(x['id'])
        if not k:
            if x['id'] not in dol_tr.KEEP:
                issues['7 DOL 미번역'].append((x['id'], x['jp'][:40], ''))
            continue
        for lv, msg in dol_tr.check(x, k):
            issues['7 DOL ' + ('자리 넘침(8단계에서 옮김)' if '자리' in msg else msg.split(':')[0]) + (' (오류)' if lv == 'error' else ' (참고)')].append((x['id'], msg, k[:60]))
        if '水かけ草' in N(x['jp']) and '물 주는 풀' not in k:
            issues['6 보류: 水かけ草→물 주는 풀'].append((x['id'], N(x['jp'])[:40], k[:60]))
        if 'むらさきキノコ' in N(x['jp']) and '보라 버섯' not in k:
            issues['6 보류: むらさきキノコ→보라 버섯'].append((x['id'], N(x['jp'])[:40], k[:60]))
    # 8 그래픽
    from PIL import Image
    G2 = os.path.join(ROOT, 'work', 'gfx_survey')
    for r in csv.DictReader(open(os.path.join(T, 'graphics_list.csv'), encoding='utf-8-sig')):
        if r['status'] != '확정':
            continue
        f = os.path.join(ROOT, r['final'])
        if not os.path.exists(f):
            issues['8 그래픽 산출물 없음 (오류)'].append((r['n'], r['final'], '')); continue
        if r['final'].endswith('.png'):
            a = Image.open(os.path.join(G2, r['png'])); b = Image.open(f)
            if a.size != b.size:
                issues['8 그래픽 크기 다름 (오류)'].append((r['n'], '%s → %s' % (a.size, b.size), r['final']))
    json.dump({k: v for k, v in issues.items()}, open(os.path.join(T, 'review_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k in sorted(issues):
        print('%-40s %5d  예: %s' % (k, len(issues[k]), ' | '.join(str(x) for x in issues[k][0])[:110]))


if __name__ == '__main__':
    main()
