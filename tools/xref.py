"""lis/addi(ori) 쌍으로 만든 주소 참조 찾기: python xref.py <주소hex>..."""
import struct, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dol import Dol


def refs(D, targets):
    out = []
    for i, o, base, s in D.secs:
        if i >= 7: continue
        hi = {}
        for k in range(0, s, 4):
            w = struct.unpack('>I', D.d[o + k:o + k + 4])[0]
            op = w >> 26; rd = (w >> 21) & 31; ra = (w >> 16) & 31; imm = w & 0xFFFF
            if op == 15 and ra == 0:
                hi[rd] = (imm << 16, base + k)
            elif op in (14, 24, 32, 34, 36, 48, 40) and ra in hi:
                v = hi[ra][0] + (imm - 0x10000 if imm & 0x8000 and op != 24 else imm)
                v &= 0xFFFFFFFF
                if v in targets: out.append((v, base + k))
            if op == 18 and (w & 1) == 0: hi = {}
    return out


if __name__ == '__main__':
    D = Dol('extract/main.dol')
    for v, a in refs(D, {int(x, 16) for x in sys.argv[1:]}):
        print('%08X <- %08X' % (v, a))
