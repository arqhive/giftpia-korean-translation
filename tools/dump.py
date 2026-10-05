"""GameCube ISO 파일 시스템 추출: python dump.py <iso> <outdir>"""
import os
import struct
import sys


def main(iso, out):
    f = open(iso, 'rb')
    hdr = f.read(0x440)
    print('ID', hdr[:6].decode(), hdr[0x20:0x60].split(b'\0')[0].decode('shift_jis', 'replace'))
    dol_off, fst_off, fst_size = struct.unpack('>III', hdr[0x420:0x42C])
    f.seek(fst_off)
    fst = f.read(fst_size)
    n = struct.unpack('>I', fst[8:12])[0]
    strtab = fst[n * 12:]

    def name(i):
        off = struct.unpack('>I', fst[i * 12:i * 12 + 4])[0] & 0xFFFFFF
        return strtab[off:strtab.index(b'\0', off)].decode('shift_jis', 'replace')

    os.makedirs(out, exist_ok=True)
    f.seek(0); open(os.path.join(out, 'boot.bin'), 'wb').write(f.read(0x440))
    f.seek(0x440); open(os.path.join(out, 'bi2.bin'), 'wb').write(f.read(0x2000))
    f.seek(dol_off)
    d = f.read(0x100)
    offs = struct.unpack('>18I', d[:72]); sizes = struct.unpack('>18I', d[0x90:0x90 + 72])
    f.seek(dol_off)
    open(os.path.join(out, 'main.dol'), 'wb').write(f.read(max(o + s for o, s in zip(offs, sizes) if s)))
    open(os.path.join(out, 'fst.bin'), 'wb').write(fst)

    stack = [(n, out)]
    cnt = 0
    for i in range(1, n):
        while i >= stack[-1][0]:
            stack.pop()
        a, b = struct.unpack('>II', fst[i * 12 + 4:i * 12 + 12])
        p = os.path.join(stack[-1][1], name(i))
        if fst[i * 12]:
            os.makedirs(p, exist_ok=True)
            stack.append((b, p))
        else:
            f.seek(a)
            open(p, 'wb').write(f.read(b))
            cnt += 1
    print(cnt, 'files')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
