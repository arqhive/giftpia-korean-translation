"""GC 텍스처 인코더(CMPR·RGBA8·RGB5A3·RGB565)와 담긴 파일(HSD dat·preload.cmb·TPL) 안 위치 찾기.

encode(img, fmt) → 바이트 (tpl.decode 와 같은 타일 배치)
locate(file_bytes, src, label) → (데이터 위치, w, h, fmt)   label 은 추출 색인(work/gfx_survey/index.csv)의 이름
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tpl

BPP = {0: 4, 1: 8, 2: 8, 3: 16, 4: 16, 5: 16, 6: 32, 8: 4, 9: 8, 10: 16, 14: 4}
BLK = {0: (8, 8), 1: (8, 4), 2: (8, 4), 3: (4, 4), 4: (4, 4), 5: (4, 4), 6: (4, 4), 8: (8, 8), 9: (8, 4), 10: (4, 4), 14: (8, 8)}


def tsize(w, h, fmt):
    bw, bh = BLK[fmt]
    return ((w + bw - 1) // bw * bw) * ((h + bh - 1) // bh * bh) * BPP[fmt] // 8


# ---------------------------------------------------------------- 인코더

def _pad(a, bw, bh):
    h, w = a.shape[:2]; H = (h + bh - 1) // bh * bh; W = (w + bw - 1) // bw * bw
    out = np.zeros((H, W, 4), a.dtype); out[:h, :w] = a
    return out


def _q565(c):
    c = np.clip(np.round(c), 0, 255).astype(int)
    r, g, b = c[..., 0] >> 3, c[..., 1] >> 2, c[..., 2] >> 3
    return np.stack([r * 255 // 31, g * 255 // 63, b * 255 // 31], -1), (r << 11) | (g << 5) | b


def _cmpr_block(px, al):
    """4x4 → 8바이트. al: 불투명 여부(16). 투명 픽셀이 있으면 3색+투명 모드."""
    trans = (~al).any()
    sel = px[al] if al.any() else px
    uniq = np.unique(sel.round(), axis=0)
    if len(uniq) > 12:                                            # 후보가 많으면 주축 위 고르게 12개
        mu = uniq.mean(0); v = np.linalg.svd(uniq - mu, full_matrices=False)[2][0]; t = (uniq - mu) @ v
        uniq = uniq[np.argsort(t)][np.linspace(0, len(uniq) - 1, 12).round().astype(int)]
    cands = [(uniq[i], uniq[j]) for i in range(len(uniq)) for j in range(i, len(uniq))]
    if len(sel) > 1:
        mu = sel.mean(0); d = sel - mu
        if np.abs(d).max() > 0:
            v = np.linalg.svd(d, full_matrices=False)[2][0]; t = d @ v
            cands.append((mu + v * t.max(), mu + v * t.min()))
    best = None
    for c0, c1 in cands:
        (q0, k0), (q1, k1) = _q565(np.array(c0, float)), _q565(np.array(c1, float))
        q0 = q0.astype(float); q1 = q1.astype(float); k0 = int(k0); k1 = int(k1)
        if trans:                                                 # 3색 모드: k0 <= k1
            if k0 > k1:
                q0, q1, k0, k1 = q1, q0, k1, k0
            pal = np.array([q0, q1, ((q0 + q1) / 2).round()])
        else:                                                     # 4색 모드: k0 > k1 (같으면 하나만 쓰면 됨)
            if k0 < k1:
                q0, q1, k0, k1 = q1, q0, k1, k0
            if k0 == k1:
                pal = np.array([q0, q0, q0, q0])
            else:
                pal = np.array([q0, q1, ((2 * q0 + q1) / 3).round(), ((q0 + 2 * q1) / 3).round()])
        dd = ((px[:, None, :] - pal[None]) ** 2).sum(2); idx = dd.argmin(1); e = dd.min(1)[al].sum()
        if best is None or e < best[0]:
            best = (e, k0, k1, idx)
    _, k0, k1, idx = best
    if trans:
        idx = np.where(al, idx, 3)
    elif k0 == k1:                                                 # 4색 모드를 지키려 k1 을 하나 낮춤(전부 0번 색)
        if k0 > 0:
            k1 = k0 - 1
        else:
            k0, k1 = 1, 0
        idx = np.zeros(16, int)
    bits = 0
    for i in range(16):
        bits = (bits << 2) | int(idx[i])
    return struct.pack('>HHI', k0, k1, bits)


def encode(img, fmt):
    a = np.asarray(img.convert('RGBA')).astype(float)
    bw, bh = BLK[fmt]; a = _pad(a, bw, bh); H, W = a.shape[:2]; out = bytearray()
    for by in range(0, H, bh):
        for bx in range(0, W, bw):
            t = a[by:by + bh, bx:bx + bw]
            if fmt == 14:
                for sy, sx in ((0, 0), (0, 4), (4, 0), (4, 4)):
                    s = t[sy:sy + 4, sx:sx + 4].reshape(-1, 4)
                    out += _cmpr_block(s[:, :3], s[:, 3] >= 128)
            elif fmt == 6:
                p = t.reshape(-1, 4).round().astype(int)
                out += bytes(v for px in p for v in (px[3], px[0]))
                out += bytes(v for px in p for v in (px[1], px[2]))
            elif fmt == 4:
                p = t.reshape(-1, 4)
                _, k = _q565(p[:, :3])
                out += b''.join(struct.pack('>H', int(v)) for v in k)
            elif fmt == 5:
                for px in t.reshape(-1, 4).round().astype(int):
                    r, g, b, al = px
                    if al >= 0xE0:
                        v = 0x8000 | (r >> 3) << 10 | (g >> 3) << 5 | (b >> 3)
                    else:
                        v = (al >> 5) << 12 | (r >> 4) << 8 | (g >> 4) << 4 | (b >> 4)
                    out += struct.pack('>H', v)
            else:
                raise ValueError('형식 %d 인코더 없음' % fmt)
    return bytes(out)


# ---------------------------------------------------------------- 위치 찾기(추출 도구와 같은 규칙)

def hsd_textures(f):
    """HSD 파일 → [(이미지 설명 위치, w, h, fmt, 파일 안 데이터 위치)] (extract_tex.hsd_textures 와 같은 순서)."""
    fs, ds, rc, rt, rf = struct.unpack('>5I', f[:20])
    base = 0x20; data = f[base:base + ds]
    rel = struct.unpack('>%dI' % rc, f[base + ds:base + ds + rc * 4]); P = set(rel)
    found = {}
    for o in P:
        if o + 0x18 > ds:
            continue
        ip, w, h, fmt, mip = struct.unpack('>IHHII', data[o:o + 16])
        if fmt not in BPP or not (1 <= w <= 1024 and 1 <= h <= 1024) or mip > 16:
            continue
        if ip >= ds or ip + tsize(w, h, fmt) > ds:
            continue
        found[o] = (w, h, fmt, ip)
    targets = {}
    for o in P:
        if o + 4 <= ds:
            targets.setdefault(struct.unpack('>I', data[o:o + 4])[0], []).append(o)
    return [(o, w, h, fmt, base + ip) for o, (w, h, fmt, ip) in sorted(found.items()) if targets.get(o)]


def hsd_split(f):
    o = 0; parts = []
    while o + 0x20 <= len(f):
        fs = struct.unpack('>I', f[o:o + 4])[0]
        if fs == 0 or o + fs > len(f):
            break
        parts.append(o); o = (o + fs + 31) & ~31
    return parts


def locate(f, src, label):
    """f: 담긴 파일 바이트(preload 는 preload.cmb 전체). → (데이터 위치, w, h, fmt)"""
    parts = label.split('_')
    if src.endswith('.tpl'):
        i = int(parts[0])
        for k, w, h, fmt, doff in tpl.images(f):
            if k == i:
                return doff, w, h, fmt
        raise KeyError(label)
    if src.endswith('.txg'):
        raise KeyError('txg 미지원: ' + label)
    i, o = int(parts[0]), int(parts[1], 16)
    base = 0
    if src.startswith('preload/'):
        base = int(src.split('/')[1], 16)
        fs = struct.unpack('>I', f[base:base + 4])[0]; f = f[base:base + fs]
    for k, (oo, w, h, fmt, doff) in enumerate(hsd_textures(f)):
        if k == i:
            assert oo == o, (label, hex(oo))
            return base + doff, w, h, fmt
    raise KeyError(label)


def decode(f, off, w, h, fmt):
    return tpl.decode(f, off, w, h, fmt)
