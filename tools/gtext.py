"""기프트피아 텍스트 1바이트/2바이트 혼합 인코딩 디코더."""


def decode(b):
    out = []; i = 0
    while i < len(b):
        c = b[i]
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF:
            out.append(b[i:i + 2].decode('cp932', 'replace')); i += 2; continue
        if 0x28 <= c <= 0x7A:
            out.append(bytes([0x82, 0x9F + c - 0x28]).decode('cp932'))
        elif 0xA1 <= c <= 0xDF:
            out.append(bytes([c]).decode('cp932'))
        elif c == 0x0A:
            out.append('\n')
        else:
            out.append('{%02X}' % c)
        i += 1
    return ''.join(out)
