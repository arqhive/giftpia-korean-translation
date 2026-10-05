"""실행 파일 데이터 섹션의 0 으로 끝나는 문자열 중 가나·한자가 든 것 가운데 번역 대상(dol_texts.json 의 의심 아닌 항목)에 없는 것.
제어 바이트(0x01~0x1F)는 {XX} 로, {14} 뒤 한 글자는 버튼 이름(ASCII)으로 살린다."""
import json
import re
import struct
import sys

sys.path.insert(0, 'tools')
from dol import Dol

D = Dol('extract/main.dol')
L = json.load(open('translation/dol_texts.json', encoding='utf-8'))
have = {int(x['addr'], 16) for x in L if not x['suspect']}
KANA = re.compile(r'[぀-ヿ一-鿿]')
ptrs = {}
for i, o, base, s in D.secs:
    if i < 7:
        continue
    for k in range(0, s - 3, 4):
        v = struct.unpack('>I', D.d[o + k:o + k + 4])[0]
        ptrs[v] = ptrs.get(v, 0) + 1


def dec(raw):
    out = []; p = 0
    while p < len(raw):
        b = raw[p]
        if b < 0x20 and b != 0x0A:
            out.append('{%02X}' % b); p += 1
            if b == 0x14 and p < len(raw):
                out.append(chr(raw[p])); p += 1
            continue
        if b < 0x80 or 0xA0 <= b < 0xE0:
            out.append(bytes([b]).decode('cp932')); p += 1
        else:
            out.append(raw[p:p + 2].decode('cp932')); p += 2
    return ''.join(out)


miss = []
for i, o, base, s in D.secs:
    if i < 7:
        continue
    k = 0; seg = D.d[o:o + s]
    while k < s:
        if seg[k] == 0:
            k += 1; continue
        e = seg.find(b'\0', k); e = s if e < 0 else e
        raw = seg[k:e]; a = base + k
        try:
            t = dec(raw)
        except Exception:
            t = None
        if t and KANA.search(t) and a not in have and ptrs.get(a):
            miss.append({'addr': '%08X' % a, 'len': len(raw), 'refs': ptrs.get(a, 0), 'jp': t})
        k = e + 1
json.dump(miss, open('work/dol_missing.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('번역 대상에 없는 가나·한자 문자열(포인터 참조 있음)', len(miss))
