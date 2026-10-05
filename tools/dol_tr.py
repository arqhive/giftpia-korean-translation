"""실행 파일(main.dol) 문구 번역 진행 도구.

  python dol_tr.py next [N]      미번역 항목 N개: id 용량(바이트, 0 종료 포함)[*=참조 없음] 원문
  python dol_tr.py apply <파일>  {id: 번역} 을 translation/dol_ko.json 에 합치고 검사
  python dol_tr.py stat

- 실행 파일 문구는 2바이트 글자만 쓴다(1바이트 한글은 evt 전용). printf 서식(%s, %2d 등)만 ASCII 로 둔다.
- 원래 자리(cap)보다 길면 8단계에서 옮긴다(참조 있는 것만 가능) → 참조 없는(*) 항목이 넘치면 오류, 나머지는 경고.
- KEEP: 번역하지 않고 원문 그대로 두는 항목(가나 변환표·오독·메모리 카드 코멘트 후보).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kochar

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, 'translation', 'dol_texts.json')
KO = os.path.join(ROOT, 'translation', 'dol_ko.json')
FMT = re.compile(r'%[-0-9]*[sdx]')
KEEP = {'D0001', 'D0901', 'D0908'}


def encode(s):
    """{XX} 는 제어 바이트 그대로. {14} 뒤 한 글자(버튼 이름 Z·A·B·X 등)는 반각 ASCII 그대로(버튼 아이콘)."""
    out = bytearray()
    for tok in re.findall(r'\{14\}[A-Za-z]|\{[0-9A-F]{2}\}|%[-0-9]*[sdx]|\n|.', s, re.S):
        if tok.startswith('{14}'):
            out += b'\x14' + tok[4].encode('ascii')
        elif re.fullmatch(r'\{[0-9A-F]{2}\}', tok):
            out.append(int(tok[1:3], 16))
        elif FMT.fullmatch(tok) or tok == '\n':
            out += tok.encode('ascii')
        else:
            c = kochar.char_code(tok)
            out += bytes([c >> 8, c & 0xFF])
    return bytes(out)


SRC2 = os.path.join(ROOT, 'translation', 'dol_texts2.json')   # 1차 추출이 빠뜨린 문구(전각 공백·버튼 코드 포함, 10/2)
KO2 = os.path.join(ROOT, 'translation', 'dol_ko2.json')


def load(extra=True):
    L = [x for x in json.load(open(SRC, encoding='utf-8')) if not x['suspect']]
    ko = json.load(open(KO, encoding='utf-8')) if os.path.exists(KO) else {}
    if extra and os.path.exists(SRC2):
        L += json.load(open(SRC2, encoding='utf-8'))
        if os.path.exists(KO2):
            ko.update(json.load(open(KO2, encoding='utf-8')))
    return L, ko


def check(x, t):
    out = []
    if FMT.findall(x['jp']) != FMT.findall(t):
        out.append(('error', '서식 다름: %s → %s' % (FMT.findall(x['jp']), FMT.findall(t))))
    if x['jp'].count('\n') != t.count('\n'):
        out.append(('error', '줄바꿈 수 다름'))
    try:
        n = len(encode(t)) + 1
        if n > x['cap']:
            norefs = x['code_refs'] + x['ptr_refs'] == 0
            out.append(('error' if norefs else 'warn', '%d바이트 > 자리 %d%s' % (n, x['cap'], ' (참조 없음: 옮길 수 없음)' if norefs else '')))
    except ValueError as e:
        out.append(('error', str(e)))
    if re.search(r'…\.|~\.|～\.', t):
        out.append(('error', '말줄임표·물결표 뒤 마침표'))
    return out


def cmd_next(n=300):
    L, ko = load(); k = 0
    for x in L:
        if x['id'] in ko or x['id'] in KEEP:
            continue
        print('%s %d%s %s' % (x['id'], x['cap'], '*' if x['code_refs'] + x['ptr_refs'] == 0 else '', x['jp'].replace('\n', '⏎')))
        k += 1
        if k >= n:
            break


def cmd_apply(path):
    L, ko = load(False); src = {x["id"]: x for x in L}
    new = json.load(open(path, encoding='utf-8')); n = {'error': 0, 'warn': 0}
    for i, t in new.items():
        if i not in src:
            print('error', i, '없는 id'); n['error'] += 1; continue
        for lv, msg in check(src[i], t):
            n[lv] += 1; print(lv, i, msg, '|', t.replace('\n', '⏎'))
    if n['error']:
        print('오류가 있어 반영하지 않음', n); return
    ko.update(new)
    json.dump(ko, open(KO, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('반영', len(new), n); cmd_stat()


def cmd_stat():
    L, ko = load()
    over = sum(1 for x in L if x['id'] in ko and any(lv == 'warn' for lv, _ in check(x, ko[x['id']])))
    print('실행 파일 문구 %d/%d (원문 유지 %d), 자리 넘침(옮길 것) %d' % (len(ko), len(L) - len(KEEP), len(KEEP), over))


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'next': cmd_next(int(sys.argv[2]) if len(sys.argv) > 2 else 300)
    elif c == 'apply': cmd_apply(sys.argv[2])
    else: cmd_stat()
