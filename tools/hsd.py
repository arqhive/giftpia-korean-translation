"""HSD(.dat) 3D 모델 읽기(조사용): scene_data → 모델 → JObj 트리 → DObj → PObj(꼭짓점 정의·표시 목록).

  python tools/hsd.py info <dat>        구조·꼭짓점 배열·프리미티브 요약
  python tools/hsd.py png <dat> <out>   꼭짓점·삼각형을 위에서 본 그림(XY)
"""
import struct
import sys

ATTR = {0: 'PNMTXIDX', 9: 'POS', 10: 'NRM', 11: 'CLR0', 12: 'CLR1', 13: 'TEX0', 14: 'TEX1', 25: 'NBT'}
ATYPE = {0: 'NONE', 1: 'DIRECT', 2: 'INDEX8', 3: 'INDEX16'}
CTYPE = {0: 'u8', 1: 's8', 2: 'u16', 3: 's16', 4: 'f32'}


class Hsd:
    def __init__(self, path):
        self.raw = open(path, 'rb').read()
        fs, dsz, rc, rtc, xrc = struct.unpack('>5I', self.raw[:20])
        self.d = self.raw[0x20:0x20 + dsz]
        self.reloc = [struct.unpack('>I', self.raw[0x20 + dsz + i * 4:0x24 + dsz + i * 4])[0] for i in range(rc)]
        r0 = 0x20 + dsz + rc * 4; st = r0 + (rtc + xrc) * 8
        self.roots = {}
        for i in range(rtc):
            off, so = struct.unpack('>2I', self.raw[r0 + i * 8:r0 + i * 8 + 8])
            self.roots[self.raw[st + so:self.raw.index(b'\0', st + so)].decode()] = off

    def u32(self, o): return struct.unpack('>I', self.d[o:o + 4])[0]
    def u16(self, o): return struct.unpack('>H', self.d[o:o + 2])[0]
    def f32(self, o): return struct.unpack('>f', self.d[o:o + 4])[0]

    def jobjs(self):
        """scene_data 의 모든 JObj (깊이우선)."""
        sd = self.roots['scene_data']; models = self.u32(sd); out = []
        i = 0
        while True:
            ms = self.u32(models + i * 4)
            if not ms:
                break
            self._walk(self.u32(ms), out, 0); i += 1
        return out

    def _walk(self, j, out, depth):
        while j:
            out.append((depth, j))
            self._walk(self.u32(j + 8), out, depth + 1)
            j = self.u32(j + 12)

    def jobj_info(self, j):
        flags = self.u32(j + 4)
        rot = [self.f32(j + 0x14 + 4 * k) for k in range(3)]
        sc = [self.f32(j + 0x20 + 4 * k) for k in range(3)]
        tr = [self.f32(j + 0x2C + 4 * k) for k in range(3)]
        return flags, rot, sc, tr, self.u32(j + 0x10)

    def dobjs(self, d):
        while d:
            yield d
            d = self.u32(d + 4)

    def pobjs(self, p):
        while p:
            yield p
            p = self.u32(p + 4)

    def vtxdesc(self, p):
        o = self.u32(p + 8); out = []
        while True:
            attr = self.u32(o)
            if attr == 0xFF:
                break
            atype, cnt, ctype = self.u32(o + 4), self.u32(o + 8), self.u32(o + 12)
            frac = self.d[o + 16]; stride = self.u16(o + 18); ptr = self.u32(o + 20)
            out.append(dict(off=o, attr=attr, atype=atype, cnt=cnt, ctype=ctype, frac=frac, stride=stride, ptr=ptr))
            o += 0x18
        return out

    def dlist(self, p):
        """표시 목록 → [(prim, [[attr 값...] per vertex])]"""
        n32 = self.u16(p + 0x0E); o = self.u32(p + 0x10); end = o + n32 * 32
        vd = self.vtxdesc(p); prims = []
        while o < end:
            op = self.d[o]
            if op == 0:
                break
            cnt = self.u16(o + 1); o += 3; verts = []
            for _ in range(cnt):
                v = []
                for a in vd:
                    if a['atype'] == 2:
                        v.append(self.d[o]); o += 1
                    elif a['atype'] == 3:
                        v.append(self.u16(o)); o += 2
                    else:  # DIRECT: PNMTXIDX(u8) 만 가정
                        v.append(self.d[o]); o += 1
                verts.append(v)
            prims.append((op & 0xF8, verts))
        return prims

    def read_pos(self, a, idx):
        o = a['ptr'] + idx * a['stride']; sc = 1 << a['frac']
        comps = 3 if a['cnt'] == 1 else 2
        if a['ctype'] == 4:
            return [self.f32(o + 4 * k) for k in range(comps)]
        fmt = {0: '>B', 1: '>b', 2: '>H', 3: '>h'}[a['ctype']]; size = struct.calcsize(fmt)
        return [struct.unpack(fmt, self.d[o + size * k:o + size * (k + 1)])[0] / sc for k in range(comps)]


def info(path):
    h = Hsd(path)
    print('roots', {k: hex(v) for k, v in h.roots.items()}, 'data', hex(len(h.d)), 'reloc', len(h.reloc))
    for depth, j in h.jobjs():
        flags, rot, sc, tr, dob = h.jobj_info(j)
        print('  ' * depth + 'JObj %x flags %08x tr %s sc %s rot %s dobj %x' % (j, flags, [round(v, 2) for v in tr], [round(v, 2) for v in sc], [round(v, 2) for v in rot], dob))
        if flags & 0x1000 or not dob:   # PTCL 등은 건너뜀
            continue
        for d in h.dobjs(dob):
            for p in h.pobjs(h.u32(d + 0x0C)):
                vd = h.vtxdesc(p); pr = h.dlist(p)
                print('  ' * depth + '   PObj %x flags %04x dl %d*32B @%x  attrs %s' % (p, h.u16(p + 0x0C), h.u16(p + 0x0E), h.u32(p + 0x10),
                      ['%s/%s/%s cnt%d frac%d stride%d @%x' % (ATTR.get(a['attr'], a['attr']), ATYPE[a['atype']], CTYPE.get(a['ctype']), a['cnt'], a['frac'], a['stride'], a['ptr']) for a in vd]))
                print('  ' * depth + '     prims %d, verts %d, kinds %s' % (len(pr), sum(len(v) for _, v in pr), sorted({hex(k) for k, _ in pr})))


def png(path, out):
    from PIL import Image, ImageDraw
    h = Hsd(path); tris = []
    for depth, j in h.jobjs():
        flags, rot, sc, tr, dob = h.jobj_info(j)
        if not dob:
            continue
        for d in h.dobjs(dob):
            for p in h.pobjs(h.u32(d + 0x0C)):
                vd = h.vtxdesc(p); ip = [k for k, a in enumerate(vd) if a['attr'] == 9][0]
                for op, verts in h.dlist(p):
                    P = [h.read_pos(vd[ip], v[ip]) for v in verts]
                    P = [(x * sc[0] + tr[0], y * sc[1] + tr[1]) for x, y, *_ in P]
                    if op == 0x98:
                        tris += [(P[i], P[i + 1], P[i + 2]) for i in range(len(P) - 2)]
                    elif op == 0x90:
                        tris += [tuple(P[i:i + 3]) for i in range(0, len(P) - 2, 3)]
                    elif op == 0xA0:
                        tris += [(P[0], P[i], P[i + 1]) for i in range(1, len(P) - 1)]
    xs = [p[0] for t in tris for p in t]; ys = [p[1] for t in tris for p in t]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys); k = 1000 / max(x1 - x0, y1 - y0)
    im = Image.new('RGB', (int((x1 - x0) * k) + 20, int((y1 - y0) * k) + 20)); dr = ImageDraw.Draw(im)
    for t in tris:
        dr.polygon([((x - x0) * k + 10, (y1 - y) * k + 10) for x, y in t], fill=(200, 200, 200), outline=(90, 90, 90))
    im.save(out); print('tris', len(tris), 'bbox', round(x0, 2), round(x1, 2), round(y0, 2), round(y1, 2))


if __name__ == '__main__':
    {'info': lambda: info(sys.argv[2]), 'png': lambda: png(sys.argv[2], sys.argv[3])}[sys.argv[1]]()


# ---------------------------------------------------------------- 쓰기(글자 모델 교체)

def glyph_mesh(ch, font, px=120):
    """글자 하나를 px 높이로 그려 줄마다 칠해진 구간을 사각형으로 만들고, 위아래로 구간이 똑같은 줄은 한 사각형으로 합친다
    (구멍·획 사이 틈이 정확하고 삼각형 수가 적다). 감는 방향은 원본과 같은 시계 방향(화면 기준 왼위→오위→오아래).
    반환: 삼각형 목록 [(x,y)*3] (글자 칸 기준 픽셀 좌표, y 아래로 증가), 잉크 크기(h, w)."""
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    ft = ImageFont.truetype(font, px)
    im = Image.new('L', (px * 2, px * 2)); ImageDraw.Draw(im).text((px // 2, px // 4), ch, font=ft, fill=255)
    a = np.asarray(im) >= 128
    ys, xs = np.where(a); a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

    def runs(row):
        r, x, n = [], 0, len(row)
        while x < n:
            if row[x]:
                s0 = x
                while x < n and row[x]:
                    x += 1
                r.append((s0, x))
            else:
                x += 1
        return r
    open_ = {}; rects = []
    for y in range(a.shape[0] + 1):
        cur = set(runs(a[y])) if y < a.shape[0] else set()
        for r in list(open_):
            if r not in cur:
                rects.append((r[0], open_.pop(r), r[1], y))
        for r in cur:
            open_.setdefault(r, y)
    tris = []
    for x0, y0, x1, y1 in rects:
        tl, tr, br, bl = (x0, y0), (x1, y0), (x1, y1), (x0, y1)
        tris += [(tl, tr, br), (tl, br, bl)]
    return tris, a.shape


def rebuild(path, out, replace, empty=()):
    """replace = {PObj 오프셋: [월드 좌표 삼각형 (x,y)*3]} → 해당 PObj 의 표시 목록을 새 삼각형으로(꼭짓점은 JObj 이동값을 빼서 로컬로).
    empty = 빈 칸으로 만들 PObj(넓이 0 삼각형 1개). 기존 꼭짓점 배열은 새 위치로 복사하고 뒤에 새 꼭짓점을 이어 붙인다."""
    h = Hsd(path); d = bytearray(h.d)
    owner = {}
    for depth, j in h.jobjs():
        fl, rot, sc, tr, dob = h.jobj_info(j)
        if dob:
            for D in h.dobjs(dob):
                for p in h.pobjs(h.u32(D + 0x0C)):
                    owner[p] = (sc, tr)
    vds = {}
    for p in owner:
        for a in h.vtxdesc(p):
            if a['attr'] == 9:
                vds[a['off']] = a
    pos_ptr = {a['ptr'] for a in vds.values()}; assert len(pos_ptr) == 1, pos_ptr
    old_ptr = pos_ptr.pop()
    nold = max(i for p in owner for op, vs in h.dlist(p) for v in vs for i in v[:1]) + 1
    while len(d) % 32:
        d.append(0)
    new_pos = len(d); d += h.d[old_ptr:old_ptr + nold * 12]
    verts = []; dls = {}
    for p, tris in replace.items():
        sc, tr = owner[p]; idx = []
        for t in tris:
            for x, y in t:
                verts.append(((x - tr[0]) / sc[0], (y - tr[1]) / sc[1], 0.0)); idx.append(nold + len(verts) - 1)
        dls[p] = idx
    for p in empty:
        dls[p] = [0, 0, 0]
    for v in verts:
        d += struct.pack('>3f', *v)
    assert nold + len(verts) < 65536
    for p, idx in dls.items():
        while len(d) % 32:
            d.append(0)
        o = len(d); dl = bytearray([0x90]) + struct.pack('>H', len(idx)) + b''.join(struct.pack('>H', i) for i in idx)
        while len(dl) % 32:
            dl.append(0)
        d += dl
        struct.pack_into('>H', d, p + 0x0E, len(dl) // 32); struct.pack_into('>I', d, p + 0x10, o)
    for off in vds:
        struct.pack_into('>I', d, off + 20, new_pos)
    raw = h.raw; dsz_old = len(h.d); tail = raw[0x20 + dsz_old:]
    hdr = bytearray(raw[:0x20]); struct.pack_into('>I', hdr, 4, len(d))
    blob = bytes(hdr) + bytes(d) + tail
    blob = blob[:0] + struct.pack('>I', len(blob)) + blob[4:]
    open(out, 'wb').write(blob)
    return nold, len(verts)
