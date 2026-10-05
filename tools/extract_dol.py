"""4단계 실행 파일 문구 추출 → translation/dol_texts.json, translation/dol_texts.xlsx

데이터 구획(7~14)에서 일본어 글자가 하나 이상 든 0 종료 SJIS 문자열을 모두 뽑는다.
- cap: 뒤쪽 0 채움까지 포함해 제자리에 쓸 수 있는 바이트 수(0 종료 포함)
- refs: 이 주소를 가리키는 곳(코드 lis/addi 쌍 + 데이터 안 포인터) 수. 0 이면 표 안 문자열(앞 문자열 기준 접근)일 수 있음
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dol import Dol
import xref

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
JP = re.compile(r'[぀-ヿ一-鿿ｦ-ﾟ]')


def suspect(addr, t):
    """이진 데이터를 문자열로 잘못 읽은 것 같은가.
    - 전각 가나·한자가 없으면 의심
    - 데이터 영역(0x80170C00~0x804F1060)은 전각 가나 3자 이상만 인정(표 사이 우연한 한자 걸림 제외)
    - SDA 영역(0x804F1060~)은 짧은 이름이 많으므로 전각 가나·한자 2자 이상 + ASCII 섞임 없음"""
    full = re.findall(r'[ぁ-ヾ一-鿿]', t)
    if not full:
        return True
    if 0x80170C00 <= addr < 0x804F1060:
        return len(re.findall(r'[ぁ-ヾ]', t)) < 3
    if addr >= 0x804F1060:
        return len(full) < 2 or bool(re.search(r'[!-~]', t))
    return False


def main():
    D = Dol(os.path.join(ROOT, 'extract', 'main.dol'))
    found = []
    for i, o, base, s in D.secs:
        if i < 7:
            continue
        blob = D.d[o:o + s]; p = 0
        while p < s:
            if blob[p] == 0:
                p += 1; continue
            e = blob.index(b'\0', p) if b'\0' in blob[p:] else s
            raw = blob[p:e]
            try:
                t = raw.decode('cp932')
            except UnicodeDecodeError:
                t = None
            if t and len(JP.findall(t)) >= 2 and all(c.isprintable() or c == '\n' for c in t):  # 일본어 2자 이상(이진 데이터 오독 제외)
                q = e
                while q < s and blob[q] == 0:
                    q += 1
                found.append({'addr': base + p, 'raw': raw, 'cap': q - p, 'jp': t})
            p = e + 1
    # 참조 수
    addrs = {f['addr'] for f in found}
    code_refs = {}
    for v, a in xref.refs(D, addrs):
        code_refs[v] = code_refs.get(v, 0) + 1
    ptr_refs = {}
    for i, o, base, s in D.secs:
        if i < 7: continue
        for k in range(0, s - 3, 4):
            v = struct.unpack_from('>I', D.d, o + k)[0]
            if v in addrs:
                ptr_refs[v] = ptr_refs.get(v, 0) + 1
    out = []
    for n, f in enumerate(found, 1):
        out.append({'id': 'D%04d' % n, 'addr': '%08X' % f['addr'], 'len': len(f['raw']) + 1, 'cap': f['cap'],
                    'code_refs': code_refs.get(f['addr'], 0), 'ptr_refs': ptr_refs.get(f['addr'], 0),
                    'suspect': suspect(f['addr'], f['jp']),
                    'jp': f['jp'], 'ko': ''})
    os.makedirs(os.path.join(ROOT, 'translation'), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, 'translation', 'dol_texts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = 'dol'
    ws.append(['id', 'addr', 'len', 'cap', 'code_refs', 'ptr_refs', 'jp', 'ko', 'note'])
    for r in out:
        ws.append([r['id'], r['addr'], r['len'], r['cap'], r['code_refs'], r['ptr_refs'], r['jp'], '', ''])
    ws.column_dimensions['G'].width = 50; ws.column_dimensions['H'].width = 50; ws.freeze_panes = 'A2'
    wb.save(os.path.join(ROOT, 'translation', 'dol_texts.xlsx'))
    unref = sum(1 for r in out if not r['code_refs'] and not r['ptr_refs'])
    print('의심', sum(1 for r in out if r['suspect']))
    print('문자열', len(out), '글자', sum(len(r['jp']) for r in out), '참조 없음', unref)


if __name__ == '__main__':
    main()
