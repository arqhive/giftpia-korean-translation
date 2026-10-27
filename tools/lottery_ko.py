"""나나시 마트 복권 간판(map/convini/lottery_txt.dat): 「宝くじ」 모양 메시(PObj 0x3b80)를 그림 569 의 「복권」 모양으로 바꾼다.

간판 글자는 그림 한 장이 아니라 글자 모양 3D 판에 텍스처(64x48)를 평면으로 입힌 것이라, 텍스처만 바꾸면
「宝くじ」 모양에 잘려 뭉개진다(10/28 사용자 지적). 텍스처의 글자(+테두리) 칸을 겹쳐도 되는 직사각형으로 덮고
(tools/rect_cover.py), 원본 메시의 위치↔UV 대응(평면 투영)을 거꾸로 써서 꼭짓점을 만든다.
- 꼭짓점 위치: POS 배열(INDEX16)을 파일 끝으로 복사하고 뒤에 이어 붙임
- UV: TEX0 는 INDEX8 이라 256칸까지. 원래 배열(0x1880, 221칸)을 끝으로 복사해 256칸으로 늘리고
  다른 모델(안내판·쪽지)이 안 쓰는 34번부터 새 UV 를 씀
- 표시 목록: 삼각형(0x90), 꼭짓점마다 POS u16 + TEX0 u8
"""
import struct
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hsd
import rect_cover

POBJ = 0x3B80          # 「宝くじ」 메시
UV_FIRST = 34          # 안내판(≤33)·쪽지(≤19)가 쓰는 UV 다음
TEX_W, TEX_H = 64, 48
LIFT = 0.6             # 메시를 위로 올리는 양(로컬 단위, 글자 높이 3.79 = 48px → 약 8px). 앞의 안내판에 「권」 아래가 가려져서(10/28 사용자 요청)


def _uv_to_local(h, po):
    """원본 메시에서 로컬 (x,y) → (u,v) 평면 대응을 최소제곱으로 구해 역행렬을 돌려준다."""
    vd = h.vtxdesc(po); P = []; T = []
    for op, vs in h.dlist(po):
        for v in vs:
            P.append(h.read_pos(vd[0], v[0])[:2]); T.append(h.read_pos(vd[1], v[1]))
    P = np.array(P); T = np.array(T); A = np.c_[P, np.ones(len(P))]
    cu = np.linalg.lstsq(A, T[:, 0], rcond=None)[0]; cv = np.linalg.lstsq(A, T[:, 1], rcond=None)[0]
    M = np.array([[cu[0], cu[1]], [cv[0], cv[1]]]); b = np.array([cu[2], cv[2]])
    Mi = np.linalg.inv(M)
    return lambda u, v: Mi @ (np.array([u, v]) - b)


def patch(blob, mask):
    """blob: lottery_txt.dat 바이트(텍스처를 이미 써 넣은 것도 됨), mask: 64x48 참/거짓(글자+테두리 칸). → 새 바이트."""
    tmp = os.path.join(os.environ.get('TEMP', '.'), '_lottery_txt.dat')
    open(tmp, 'wb').write(blob); h = hsd.Hsd(tmp); os.remove(tmp)
    d = bytearray(h.d)
    vd = h.vtxdesc(POBJ)
    assert [a['attr'] for a in vd] == [9, 13] and vd[0]['atype'] == 3 and vd[1]['atype'] == 2, vd   # POS INDEX16, TEX0 INDEX8
    to_local = _uv_to_local(h, POBJ)
    # 모든 PObj 의 POS·TEX0 설명(배열 주소를 같이 바꿔야 함)
    descs = {}
    for depth, j in h.jobjs():
        fl, rot, sc, tr, dob = h.jobj_info(j)
        if dob:
            for D in h.dobjs(dob):
                for p in h.pobjs(h.u32(D + 0x0C)):
                    for a in h.vtxdesc(p):
                        descs[a['off']] = a
    pos_ptrs = {a['ptr'] for a in descs.values() if a['attr'] == 9}
    uv_ptrs = {a['ptr'] for a in descs.values() if a['attr'] == 13}
    assert len(pos_ptrs) == 1 and len(uv_ptrs) == 1
    pos_old, uv_old = pos_ptrs.pop(), uv_ptrs.pop()
    uv_stride = vd[1]['stride']; assert uv_stride == 4 and vd[1]['ctype'] == 2   # u16 u,v
    # 다른 모델이 쓰는 UV 번호가 UV_FIRST 미만인지 확인
    for depth, j in h.jobjs():
        fl, rot, sc, tr, dob = h.jobj_info(j)
        if dob:
            for D in h.dobjs(dob):
                for p in h.pobjs(h.u32(D + 0x0C)):
                    if p == POBJ:
                        continue
                    pv = h.vtxdesc(p); k = [i for i, a in enumerate(pv) if a['attr'] == 13]
                    if k:
                        assert max(v[k[0]] for op, vs in h.dlist(p) for v in vs) < UV_FIRST, hex(p)
    npos = max(v[0] for p in [POBJ] + [q for q in []] for op, vs in h.dlist(p) for v in vs) + 1
    npos = max(npos, max(v[0] for depth, j in h.jobjs() for D in (h.dobjs(h.jobj_info(j)[4]) if h.jobj_info(j)[4] else [])
                          for p in h.pobjs(h.u32(D + 0x0C)) for op, vs in h.dlist(p) for v in vs) + 1)
    nuv_old = max(v[1] for op, vs in h.dlist(POBJ) for v in vs) + 1
    # 새 메시
    rects = rect_cover.cover(mask)
    pts = sorted(rect_cover.corners(rects))
    assert len(pts) <= 256 - UV_FIRST, len(pts)
    pid = {q: i for i, q in enumerate(pts)}
    sc, tr = h.jobj_info([j for depth, j in h.jobjs() if any(p == POBJ for D in (h.dobjs(h.jobj_info(j)[4]) if h.jobj_info(j)[4] else []) for p in h.pobjs(h.u32(D + 0x0C)))][0])[2:4]
    assert all(abs(s - 1) < 1e-6 for s in sc[:2]) and abs(tr[0]) + abs(tr[1]) >= 0      # 로컬 좌표 그대로(크기 1)
    # 위치 배열: 원본 복사 + 새 꼭짓점
    while len(d) % 32:
        d.append(0)
    new_pos = len(d); d += h.d[pos_old:pos_old + npos * 12]
    for x, y in pts:
        lx, ly = to_local(x / TEX_W, y / TEX_H)
        d += struct.pack('>3f', float(lx), float(ly) + LIFT, 0.0)
    # UV 배열: 원본 복사(256칸) + 새 UV
    while len(d) % 32:
        d.append(0)
    new_uv = len(d); uv = bytearray(h.d[uv_old:uv_old + nuv_old * 4]); uv += bytes(256 * 4 - len(uv))
    for i, (x, y) in enumerate(pts):
        struct.pack_into('>HH', uv, (UV_FIRST + i) * 4, min(32767, round(x / TEX_W * 32768)), min(32767, round(y / TEX_H * 32768)))
    d += uv
    # 표시 목록: 삼각형, 꼭짓점 = POS u16 + TEX0 u8 (감는 방향은 원본 글자 모델과 같은 시계 방향)
    idx = []
    for x0, y0, x1, y1 in rects:
        tl, trp, br, bl = (x0, y0), (x1, y0), (x1, y1), (x0, y1)
        idx += [tl, trp, br, tl, br, bl]
    dl = bytearray([0x90]) + struct.pack('>H', len(idx))
    for q in idx:
        dl += struct.pack('>HB', npos + pid[q], UV_FIRST + pid[q])
    while len(dl) % 32:
        dl.append(0)
    while len(d) % 32:
        d.append(0)
    o = len(d); d += dl
    struct.pack_into('>H', d, POBJ + 0x0E, len(dl) // 32); struct.pack_into('>I', d, POBJ + 0x10, o)
    for off, a in descs.items():
        struct.pack_into('>I', d, off + 20, new_pos if a['attr'] == 9 else new_uv if a['attr'] == 13 else a['ptr'])
    raw = h.raw; tail = raw[0x20 + len(h.d):]
    hdr = bytearray(raw[:0x20]); struct.pack_into('>I', hdr, 4, len(d))
    out = bytes(hdr) + bytes(d) + tail
    return struct.pack('>I', len(out)) + out[4:], len(rects), len(pts)


def mask_from_png(path, th=140):
    """글자+짙은 테두리 칸. 흰 바탕 쪽 옅은 회색 번짐(>th)은 빼야 메시 가장자리에 회색 띠가 안 생김."""
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    return a.min(2) <= th
