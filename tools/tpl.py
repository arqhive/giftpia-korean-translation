"""TPL 디코더(I4·I8·IA4·IA8·RGB565·RGB5A3·RGBA8·CMPR): python tpl.py <tpl> <outdir>"""
import os, struct, sys
from PIL import Image

BLK = {0: (8, 8, 4), 1: (8, 4, 8), 2: (8, 4, 8), 3: (4, 4, 16), 4: (4, 4, 16), 5: (4, 4, 16), 6: (4, 4, 32), 14: (8, 8, 4)}


def c565(v):
    return ((v >> 11) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31, 255)


def c5a3(v):
    if v & 0x8000:
        return ((v >> 10 & 31) * 255 // 31, (v >> 5 & 31) * 255 // 31, (v & 31) * 255 // 31, 255)
    return ((v >> 8 & 15) * 17, (v >> 4 & 15) * 17, (v & 15) * 17, (v >> 12 & 7) * 255 // 7)


def decode(d, off, w, h, fmt):
    img = Image.new('RGBA', (w, h)); px = img.load()
    bw, bh, bpp = BLK[fmt]
    p = off
    for by in range(0, h, bh):
        for bx in range(0, w, bw):
            if fmt == 14:
                for sy in range(0, 8, 4):
                    for sx in range(0, 8, 4):
                        c0, c1 = struct.unpack('>HH', d[p:p + 4]); bits = struct.unpack('>I', d[p + 4:p + 8])[0]; p += 8
                        a, b = c565(c0), c565(c1)
                        if c0 > c1:
                            pal = [a, b, tuple((2 * x + y) // 3 for x, y in zip(a, b)), tuple((x + 2 * y) // 3 for x, y in zip(a, b))]
                        else:
                            pal = [a, b, tuple((x + y) // 2 for x, y in zip(a, b)), (0, 0, 0, 0)]
                        for i in range(16):
                            x, y = bx + sx + i % 4, by + sy + i // 4
                            if x < w and y < h:
                                px[x, y] = pal[(bits >> (30 - 2 * i)) & 3]
                continue
            if fmt == 6:
                blk = d[p:p + 64]; p += 64
                for i in range(16):
                    x, y = bx + i % 4, by + i // 4
                    if x < w and y < h:
                        px[x, y] = (blk[i * 2 + 1], blk[32 + i * 2], blk[32 + i * 2 + 1], blk[i * 2])
                continue
            for yy in range(bh):
                for xx in range(bw):
                    x, y = bx + xx, by + yy
                    if fmt == 0:
                        v = d[p + (yy * bw + xx) // 2]; v = (v >> 4 if xx % 2 == 0 else v & 15) * 17; c = (v, v, v, 255)
                    elif fmt == 1:
                        v = d[p + yy * bw + xx]; c = (v, v, v, 255)
                    elif fmt == 2:
                        v = d[p + yy * bw + xx]; c = ((v & 15) * 17,) * 3 + ((v >> 4) * 17,)
                    elif fmt == 3:
                        a, l = d[p + (yy * bw + xx) * 2:p + (yy * bw + xx) * 2 + 2]; c = (l, l, l, a)
                    elif fmt == 4:
                        c = c565(struct.unpack('>H', d[p + (yy * bw + xx) * 2:p + (yy * bw + xx) * 2 + 2])[0])
                    elif fmt == 5:
                        c = c5a3(struct.unpack('>H', d[p + (yy * bw + xx) * 2:p + (yy * bw + xx) * 2 + 2])[0])
                    if x < w and y < h:
                        px[x, y] = c
            p += bw * bh * bpp // 8
    return img


def images(d):
    n, tbl = struct.unpack('>II', d[4:12])
    for i in range(n):
        io = struct.unpack('>I', d[tbl + i * 8:tbl + i * 8 + 4])[0]
        h, w, fmt, doff = struct.unpack('>HHII', d[io:io + 12])
        yield i, w, h, fmt, doff


if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read(); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    base = os.path.splitext(os.path.basename(sys.argv[1]))[0]
    for i, w, h, fmt, doff in images(d):
        decode(d, doff, w, h, fmt).save(os.path.join(out, f'{base}_{i:02d}.png'))


def encode_i4(img):
    """L 이미지 → I4 바이트(8x8 타일)."""
    w, h = img.size; px = img.load(); out = bytearray()
    for by in range(0, h, 8):
        for bx in range(0, w, 8):
            for y in range(8):
                for x in range(0, 8, 2):
                    a = px[bx + x, by + y] >> 4 if bx + x < w and by + y < h else 0
                    b = px[bx + x + 1, by + y] >> 4 if bx + x + 1 < w and by + y < h else 0
                    out.append(a << 4 | b)
    return bytes(out)


def replace_i4(d, i, img):
    """TPL d(bytearray) 의 i 번째 이미지를 같은 크기 I4 로 덮어쓴다."""
    for k, w, h, fmt, doff in images(d):
        if k == i:
            assert fmt == 0 and img.size == (w, h)
            data = encode_i4(img)
            d[doff:doff + len(data)] = data
            return
    raise KeyError(i)
