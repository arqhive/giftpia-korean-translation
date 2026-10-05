"""번역 기계 검사: 제어 코드 보존, 글자 변환 가능, 창 폭·줄 수, 부호 규칙.

사용: python check_tr.py <번역 json>   (항목: id, kind, jp, ko)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_text
import kochar

CTL = re.compile(r'\{[0-9A-F]{2}\}')
OP = {'choice': 0x7E}


def check(row):
    jp, ko = row['jp'], row['ko']; out = []
    # {25}{xx}ぽ 는 printf 서식 '%Nd'(0x25 '%', 0x64 'd'). 0x64 를 디코더가 「ぽ」로 보였을 뿐이라 번역문은 {64} 로 적는다
    jp = re.sub(r'(\{25\}\{[0-9A-F]{2}\})ぽ', r'\1{64}', jp)
    if re.search(r'\{25\}\{[0-9A-F]{2}\}ぽ', ko):
        out.append(('error', '서식 %Nd 의 d 는 「ぽ」가 아니라 {64} 로 적을 것'))
    if CTL.findall(jp) != CTL.findall(ko):
        out.append(('error', '제어 코드 다름: %s → %s' % (''.join(CTL.findall(jp)), ''.join(CTL.findall(ko)))))
    try:
        kochar.encode(ko)
    except ValueError as e:
        out.append(('error', str(e)))
    # 폭 초과라도 원문 가장 긴 줄보다 길지 않으면 경고로 낮춘다(끼워 넣기 폭 가정이 보수적이라 원문도 넘는 경우)
    jp_max = max((check_text.width(l) for pg in check_text.pages(jp) for l in pg), default=0)
    # 줄 수도 마찬가지: 원문 쪽이 이미 창 줄 수를 넘는 항목(그림책·도감 같은 별도 창)은 원문 줄 수까지 허용
    jp_lines = max((len(pg) for pg in check_text.pages(jp)), default=0)
    for lv, msg in check_text.check(ko, OP.get(row['kind'], 0x66)):
        m = re.search(r'(\d+)자 > (\d+)$', msg)
        if lv == 'error' and m and int(m.group(1)) <= jp_max:
            lv, msg = 'warn', msg + ' (원문 %d자 이하)' % jp_max
        m = re.search(r'(\d+)줄 > (\d+)$', msg)
        if lv == 'error' and m and int(m.group(1)) <= jp_lines:
            lv, msg = 'warn', msg + ' (원문 %d줄 이하)' % jp_lines
        out.append((lv, msg))
    plain = CTL.sub('', ko)
    if re.search(r'…\.|~\.|～\.', plain):
        out.append(('error', '말줄임표·물결표 뒤 마침표'))
    if '그녀' in plain:
        out.append(('warn', '대사 속 그녀'))
    if re.search(r'이 내가|하는 것이다', plain):
        out.append(('warn', '직역투'))
    return out


def main(path):
    rows = json.load(open(path, encoding='utf-8')); n = {'error': 0, 'warn': 0}
    for r in rows:
        if not r.get('ko'):
            continue
        for lv, msg in check(r):
            n[lv] += 1
            print(lv, r['id'], msg, '|', r['ko'].replace('\n', '⏎')[:60])
    print('항목', len(rows), n)


if __name__ == '__main__':
    main(sys.argv[1])
