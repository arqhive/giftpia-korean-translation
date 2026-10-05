"""ext/font.tpl(가나·전각 영숫자 그래픽 폰트, 28px 칸)에 1바이트 한글 칸을 그린다.

0번 그림: SJIS 0x8240~0x82FF (16열, 칸 번호 = 하위 바이트 - 0x40)
1번 그림: SJIS 0x8340~0x839F
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tpl

CELL = 28


def build(src_tpl, glyphs, ttf, out, size=21, cy=13.5):
    """glyphs: {SJIS 코드: 글자(' ' 는 빈칸)}"""
    d = bytearray(open(src_tpl, 'rb').read())
    imgs = {i: tpl.decode(d, doff, w, h, fmt).getchannel('R') for i, w, h, fmt, doff in tpl.images(d) if i in (0, 1)}
    font = ImageFont.truetype(ttf, size * 4)
    for code, ch in glyphs.items():
        i, base = (0, 0x8240) if code < 0x8340 else (1, 0x8340)
        r, c = divmod(code - base, 16)
        big = Image.new('L', (CELL * 4, CELL * 4), 0)
        if ch.strip():
            ImageDraw.Draw(big).text((CELL * 2, cy * 4), ch, fill=255, font=font, anchor='mm')
        imgs[i].paste(big.resize((CELL, CELL), Image.LANCZOS), (c * CELL, r * CELL))
    for i, im in imgs.items():
        tpl.replace_i4(d, i, im)
    open(out, 'wb').write(d)
    return imgs
