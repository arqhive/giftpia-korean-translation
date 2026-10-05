"""GC IPL Shift-JIS ROM 폰트(Yay0) 읽기·쓰기.

형식(OSFontHeader, BE): 헤더 0x30 + 글자 폭 표 + 2비트 시트(512x512, I4 타일 순서, 4픽셀/바이트)
칸 번호 변환은 main.dol 0x80117718(SDK GetFontCode)과 같다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yay0

HDR = struct.Struct('>10HI6HII4B')
NAMES = ('fontType firstChar lastChar invalidChar ascent descent width leading cellW cellH sheetSize sheetFormat '
         'sheetCol sheetRow sheetW sheetH widthTable sheetImage sheetFullSize c0 c1 c2 c3').split()

_tables = None


def tables(dol_path=None):
    """main.dol 에서 반각·전각 변환표를 읽는다."""
    global _tables
    if _tables is None:
        from dol import Dol
        D = Dol(dol_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'extract', 'main.dol'))
        han = struct.unpack('>192H', D.read(0x801AD6B8, 192 * 2))          # 0x20~0xDF
        zen = struct.unpack('>%dH' % (6 * 188), D.read(0x801AD878, 6 * 188 * 2))  # 0x81~0x86 행
        _tables = (han, zen)
    return _tables


def _trail(t):
    if t < 0x40 or t > 0xFC or t == 0x7F:
        return None
    j = t - 0x40
    return j - 1 if j >= 0x40 else j


def index(code):
    """SJIS 코드(또는 1바이트) → 칸 번호. 표시 불가면 0."""
    han, zen = tables()
    if 0x20 <= code <= 0xDF:
        return han[code - 0x20]
    if 0x889E < code <= 0x9872:
        j = _trail(code & 0xFF)
        return 0 if j is None else ((code >> 8) - 0x88) * 188 + j + 0x2BE
    if 0x8140 <= code < 0x879E:
        j = _trail(code & 0xFF)
        return 0 if j is None else zen[((code >> 8) - 0x81) * 188 + j]
    return 0


def load(path):
    raw = open(path, 'rb').read()
    d = yay0.decompress(raw) if raw[:4] == b'Yay0' else raw
    return dict(zip(NAMES, HDR.unpack_from(d, 0))), d


def cell_image(h, d, idx):
    """칸 하나를 0~3 값의 24x24 목록으로."""
    per = h['sheetCol'] * h['sheetRow']
    sheet, k = divmod(idx, per)
    row, col = divmod(k, h['sheetCol'])
    base = h['sheetImage'] + sheet * (h['sheetW'] * h['sheetH'] // 4)
    out = []
    for y in range(h['cellH']):
        line = []
        for x in range(h['cellW']):
            px, py = col * h['cellW'] + x, row * h['cellH'] + y
            tile = (py // 8) * (h['sheetW'] // 8) + px // 8
            pos = tile * 64 + (py % 8) * 8 + px % 8
            b = d[base + pos // 4]
            line.append((b >> (6 - 2 * (pos % 4))) & 3)
        out.append(line)
    return out


def set_cell(h, d, idx, px):
    """칸 하나에 0~3 값 24x24 를 쓴다(d 는 bytearray)."""
    per = h['sheetCol'] * h['sheetRow']
    sheet, k = divmod(idx, per)
    row, col = divmod(k, h['sheetCol'])
    base = h['sheetImage'] + sheet * (h['sheetW'] * h['sheetH'] // 4)
    for y in range(h['cellH']):
        for x in range(h['cellW']):
            gx, gy = col * h['cellW'] + x, row * h['cellH'] + y
            tile = (gy // 8) * (h['sheetW'] // 8) + gx // 8
            pos = tile * 64 + (gy % 8) * 8 + gx % 8
            sh = 6 - 2 * (pos % 4)
            o = base + pos // 4
            d[o] = (d[o] & ~(3 << sh)) | (px[y][x] << sh)


def render(font, ch, cell=24, size=22, dy=0):
    """글자를 cell x cell 의 0~3 농도로 그린다. (픽셀, 폭) 을 돌려준다."""
    from PIL import Image, ImageDraw
    im = Image.new('L', (cell * 4, cell * 4), 0)
    ImageDraw.Draw(im).text((cell * 2, cell * 2 + dy * 4), ch, fill=255, font=font, anchor='mm')
    im = im.resize((cell, cell), Image.LANCZOS)
    px = [[min(3, (im.getpixel((x, y)) + 42) // 85) for x in range(cell)] for y in range(cell)]
    return px


def build(base_path, glyphs, ttf, out_path, size=22):
    """base 폰트에 {SJIS 코드: 글자} 를 그려 넣고 Yay0 으로 저장. 압축 크기를 돌려준다."""
    from PIL import ImageFont
    h, d = load(base_path); d = bytearray(d)
    font = ImageFont.truetype(ttf, size * 4)
    for code, ch in glyphs.items():
        idx = index(code)
        assert idx, hex(code)
        set_cell(h, d, idx, render(font, ch, h['cellW'], size))
        d[h['widthTable'] + idx] = h['cellW']
    comp = yay0.compress(bytes(d))
    comp += bytes((-len(comp)) % 32)
    open(out_path, 'wb').write(comp)
    return len(comp)
