"""빌드한 main.dol 에서 D2xxx(빠졌던 문구) 각각: 포인터가 가리키는 곳의 바이트가 번역 인코딩과 같은지, 남은 가나 문구가 있는지."""
import json
import re
import struct
import sys

sys.path.insert(0, 'tools')
import dol_tr
from dol import Dol

W = sys.argv[1]
O = Dol('extract/main.dol'); N = Dol(W + '/main.dol')
B = json.load(open('translation/dol_texts2.json', encoding='utf-8')); K = json.load(open('translation/dol_ko2.json', encoding='utf-8'))


def words(D):
    for i, o, base, s in D.secs:
        if i < 7:
            continue
        for k in range(0, s - 3, 4):
            yield base + k, struct.unpack('>I', D.d[o + k:o + k + 4])[0]


def cstr(D, a):
    o = D.a2o(a); e = D.d.index(b'\0', o); return D.d[o:e]


oldp = {}
for at, v in words(O):
    oldp.setdefault(v, []).append(at)
newv = dict(words(N))
ok = bad = 0
for x in B:
    a = int(x['addr'], 16); want = dol_tr.encode(K[x['id']])
    for at in oldp.get(a, []):
        got = cstr(N, newv[at])
        if got == want:
            ok += 1
        else:
            bad += 1; print('다름', x['id'], hex(at), got[:20], want[:20])
print('포인터 확인 맞음', ok, '틀림', bad)
