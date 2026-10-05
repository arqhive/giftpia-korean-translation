"""DOL 코드 역어셈블: python ppc.py <시작주소hex> <개수>"""
import os
import sys
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dol import Dol

md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)


def dis(D, a, n):
    out = []
    for k in range(n):
        w = D.read(a + 4 * k, 4)
        ins = list(md.disasm(w, a + 4 * k))
        out.append((a + 4 * k, (ins[0].mnemonic + ' ' + ins[0].op_str) if ins else '.word 0x' + w.hex()))
    return out


if __name__ == '__main__':
    D = Dol(sys.argv[3] if len(sys.argv) > 3 else 'extract/main.dol')
    for a, s in dis(D, int(sys.argv[1], 16), int(sys.argv[2])):
        print('%08X  %s' % (a, s))
