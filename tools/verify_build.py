"""빌드 검증: ISO 안 파일이 빌드 산출물과 같은지, giftpia.dat 안 교체 파일, evt 다시 해석, 그림 다시 디코드."""
import csv
import hashlib
import json
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, 'tools')
import build_iso
import evt
import texenc
import u8

ISO = sys.argv[1] if len(sys.argv) > 1 else 'build/Giftpia_KO_v0.1.iso'; W = sys.argv[2] if len(sys.argv) > 2 else 'build/v01'
f = open(ISO, 'rb')
dol_off, fst_off, fst, ents = build_iso.read_fst(f)
E = {p: (a, b) for i, p, a, b in ents}
md5 = lambda b: hashlib.md5(b).hexdigest()


def disk(p):
    a, b = E[p]; f.seek(a); return f.read(b)


f.seek(0x420); dol_hdr = struct.unpack('>I', f.read(4))[0]
f.seek(dol_hdr); dol_iso = f.read(os.path.getsize(W + '/main.dol'))
print('1 실행 파일: boot.bin 위치', hex(dol_hdr), '= FST default.dol', hex(E['default.dol'][0]), '| 내용 같음', dol_iso == open(W + '/main.dol', 'rb').read())
for p, local in (('giftpia.dat', W + '/giftpia.dat'), ('gift/mov/opening.thp', 'work/movie/opening.thp'), ('kofont.szs', W + '/kofont.szs')):
    print('  ', p, '같음', md5(disk(p)) == md5(open(local, 'rb').read()))
orig = open('Giftpia (Japan).iso', 'rb'); _, _, _, oents = build_iso.read_fst(orig)
same = 0
for i, p, a, b in oents:
    if p in ('default.dol', 'giftpia.dat', 'gift/mov/opening.thp'):
        continue
    orig.seek(a); x = orig.read(b)
    same += md5(x) == md5(disk(p))
print('2 안 바꾼 디스크 파일', same, '/', len(oents) - 3, '원본과 같음')

dat = disk('giftpia.dat'); _, _, ents2 = u8.parse(dat)
odat = open('extract/giftpia.dat', 'rb').read(); _, _, oents2 = u8.parse(odat)
O = {p: odat[a:a + b] for i, p, a, b in oents2 if a is not None}
N = {p: dat[a:a + b] for i, p, a, b in ents2 if a is not None}
chg = [p for p in N if N[p] != O.get(p)]
rep_ok = sum(N[p] == open(os.path.join(W, 'dat', p), 'rb').read() for p in chg if os.path.exists(os.path.join(W, 'dat', p)))
print('3 giftpia.dat 파일', len(N), '(원본', len(O), ') 바뀐 것', len(chg), '중 빌드 산출물과 같음', rep_ok, '| 빌드 폴더에 없는데 바뀐 것', [p for p in chg if not os.path.exists(os.path.join(W, 'dat', p))][:5])

bad = 0; nt = 0; big = []
for p in sorted(x for x in N if x.startswith('evt/')):
    try:
        t = evt.texts(N[p]); nt += len(t)
    except Exception as e:
        bad += 1; print('  해석 실패', p, e)
    big.append((len(N[p]) - len(O[p]), len(N[p]), p))
big.sort(reverse=True)
print('4 evt 다시 해석: 실패', bad, '대사 위치', nt, '| 가장 많이 커진 맵', [(p, '%dKB→%dKB' % (len(O[p]) // 1024, n // 1024)) for dlt, n, p in big[:4]])

conf = {os.path.normpath(r['png']): r for r in csv.DictReader(open('translation/graphics_list.csv', encoding='utf-8-sig')) if r['status'] == '확정' and r['final'].endswith('.png')}
rows = [r for r in csv.DictReader(open('work/gfx_survey/index.csv', encoding='utf-8')) if os.path.normpath(r['path']) in conf]
worst = 0
for r in rows:
    rel = 'preload.cmb' if r['src'].startswith('preload/') else r['src']
    off, w, h, fmt = texenc.locate(N[rel], r['src'], r['label'])
    a = np.asarray(texenc.decode(N[rel], off, w, h, fmt)).astype(int)
    b = np.asarray(Image.open(conf[os.path.normpath(r['path'])]['final']).convert('RGBA')).astype(int)
    worst = max(worst, np.abs(a - b)[..., :3].mean())
print('5 그림 258곳 디스크에서 다시 디코드 ↔ 확정본: 평균 차 최대', round(worst, 2))

