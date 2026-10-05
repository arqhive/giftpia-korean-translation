"""본 번역 진행 도구.

  python tr.py next [N]        다음 미번역 항목 N개(기본 250)를 압축 표기로 출력
  python tr.py apply <파일>    묶음 번역({id: 번역}) 을 translation/evt_ko.json 에 합치고 검사
  python tr.py stat            진행률

순서: evt_texts.json 순서(맵 순서·위치). 살아있는 대사 먼저, 죽은 코드·디버그 맵은 마지막.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_tr

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, 'translation', 'evt_texts.json')
KO = os.path.join(ROOT, 'translation', 'evt_ko.json')
# 화자 번호({0C}{xx}·{08}{xx}) → 이름(시범 번역에서 확인한 것)
SPK = {'06': '캐피', '07': '메이어', '0B': '루미코', '0D': '킹', '0E': '메트', '0F': '에진소', '1B': '맛포', '3E': '나레이션', '12': 'DEEJ',
       '05': '지기', '03': '염소소년', '04': '앤', '08': '에이프런', '09': '바야', '0A': '치비타', '0C': '타오', '3D': '버섯정령', '0D': '킹', '0E': '메트', '0F': '에진소', '11': '피비', '17': '갈레리오', '19': '데이브', '13': '찬', '14': 'SP1', '15': 'SP2', '3F': '에지폰', '10': '마도로스', '1A': '갈레리오', '40': '신목', '2D': '염소', '32': '염소', '41': '카렌'}


def load():
    E = json.load(open(SRC, encoding='utf-8'))
    ko = json.load(open(KO, encoding='utf-8')) if os.path.exists(KO) else {}
    order = [x for x in E if not ({'dead', 'debugmap'} & set(x['flags']))] + \
            [x for x in E if {'dead', 'debugmap'} & set(x['flags'])]
    return order, ko


def speaker(jp):
    m = re.search(r'\{(?:0C|08)\}\{([0-9A-F]{2})\}', jp)
    if not m:
        return ''
    return SPK.get(m.group(1), m.group(1))


def pending_ids():
    """translation/pending.md 표에 적힌 보류 id(E00000, E00000~E00000 범위 포함)."""
    p = os.path.join(os.path.dirname(KO), 'pending.md')
    if not os.path.exists(p):
        return set()
    s = set()
    for a, b in re.findall(r'E(\d{5})(?:~E(\d{5}))?', open(p, encoding='utf-8').read()):
        for i in range(int(a), int(b or a) + 1):
            s.add('E%05d' % i)
    return s


def cmd_next(n=250):
    order, ko = load(); k = 0; skip = pending_ids()
    for x in order:
        if x['id'] in ko or x['id'] in skip:
            continue
        tag = speaker(x['jp'])
        print('%s%s%s %s' % (x['id'], ' [' + tag + ']' if tag else '', ' (선택지)' if x['kind'] == 'choice' else
                               (' (라디오)' if x['kind'] == 'ticker' else ''), x['jp'].replace('\n', '⏎')))
        k += 1
        if k >= n:
            break


def cmd_apply(path):
    order, ko = load(); src = {x['id']: x for x in order}
    new = json.load(open(path, encoding='utf-8')); n = {'error': 0, 'warn': 0}
    for i, t in new.items():
        if i not in src:
            print('error', i, '없는 id'); n['error'] += 1; continue
        row = dict(src[i]); row['ko'] = t
        for lv, msg in check_tr.check(row):
            n[lv] += 1; print(lv, i, msg, '|', t.replace('\n', '⏎')[:70])
    if n['error']:
        print('오류가 있어 반영하지 않음', n); return
    ko.update(new)
    json.dump(ko, open(KO, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('반영', len(new), n); cmd_stat()


def cmd_stat():
    order, ko = load()
    live = [x for x in order if not ({'dead', 'debugmap'} & set(x['flags']))]
    done = sum(1 for x in live if x['id'] in ko)
    print('살아있는 대사 %d/%d (%.1f%%), 전체 %d/%d' % (done, len(live), 100 * done / len(live), len(ko), len(order)))


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'next': cmd_next(int(sys.argv[2]) if len(sys.argv) > 2 else 250)
    elif c == 'apply': cmd_apply(sys.argv[2])
    else: cmd_stat()
