"""main.dol 패치: IPL ROM 폰트 대신 디스크의 폰트 파일을 읽는다.

0x80117A5C(__OSReadROM 반복 함수, OSLoadFont 의 두 경로에서만 호출)를 통째로 덮어쓴다.
호출 규약은 원래와 같다: r3 = 버퍼(32바이트 정렬), r4 = 크기, r5 = ROM 주소 (r4·r5 는 무시).
  entry = DVDConvertPathToEntrynum(PATH); DVDFastOpen(entry, &fi);
  DVDReadPrio(&fi, buf, roundup32(fi.length), 0, 2); DVDClose(&fi)
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dol import Dol

FUNC = 0x80117A5C
FUNC_END = 0x80117AE8          # 다음 함수(OSLoadFont) 시작
CONV = 0x80104560              # DVDConvertPathToEntrynum
FASTOPEN = 0x80104854          # DVDFastOpen
READPRIO = 0x80104A3C          # DVDReadPrio
CLOSE = 0x801048C8             # DVDClose
FONT_PATH = b'/kofont.szs\0'


def bl(at, target):
    off = target - at
    assert -0x2000000 <= off < 0x2000000
    return 0x48000001 | (off & 0x3FFFFFC)


def b(at, target):
    return bl(at, target) & ~1


def build_loader():
    code = []
    a = lambda: FUNC + 4 * len(code)
    code += [0x7C0802A6,            # mflr r0
             0x90010004,            # stw r0,4(r1)
             0x9421FFB0,            # stwu r1,-0x50(r1)
             0x93E1004C,            # stw r31,0x4c(r1)
             0x7C7F1B78]            # mr r31,r3
    i_lis = len(code); code += [0, 0]  # lis r3,hi / addi r3,r3,lo
    code.append(bl(a(), CONV))
    code.append(0x38810008)         # addi r4,r1,8   (DVDFileInfo 0x3C 바이트)
    code.append(bl(a(), FASTOPEN))
    code.append(0x2C030000)         # cmpwi r3,0
    i_beq = len(code); code.append(0)
    code += [0x38610008,            # addi r3,r1,8
             0x7FE4FB78,            # mr r4,r31
             0x80A1003C,            # lwz r5,0x3c(r1)  (fi.length = fi+0x34)
             0x38A5001F,            # addi r5,r5,0x1f
             0x54A50034,            # rlwinm r5,r5,0,0,26  (& ~0x1f)
             0x38C00000,            # li r6,0
             0x38E00002]            # li r7,2
    code.append(bl(a(), READPRIO))
    code.append(0x38610008)         # addi r3,r1,8
    code.append(bl(a(), CLOSE))
    done = a()
    code += [0x80010054,            # lwz r0,0x54(r1)
             0x83E1004C,            # lwz r31,0x4c(r1)
             0x38210050,            # addi r1,r1,0x50
             0x7C0803A6,            # mtlr r0
             0x4E800020]            # blr
    code[i_beq] = 0x41820000 | ((done - (FUNC + 4 * i_beq)) & 0xFFFC)  # beq done
    path_at = a()
    hi, lo = path_at >> 16, path_at & 0xFFFF
    if lo & 0x8000:
        hi += 1
    code[i_lis] = 0x3C600000 | hi                     # lis r3,hi
    code[i_lis + 1] = 0x38630000 | lo                 # addi r3,r3,lo
    blob = b''.join(struct.pack('>I', w) for w in code) + FONT_PATH
    assert FUNC + len(blob) <= FUNC_END, '코드가 원래 함수보다 큼'
    return blob + bytes(FUNC_END - FUNC - len(blob))


def patch(src, dst):
    D = Dol(src); d = bytearray(D.d)
    blob = build_loader()
    o = D.a2o(FUNC)
    d[o:o + len(blob)] = blob
    open(dst, 'wb').write(d)
    return len(blob)


if __name__ == '__main__':
    print(patch(sys.argv[1], sys.argv[2]))
