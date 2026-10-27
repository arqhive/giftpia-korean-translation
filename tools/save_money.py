"""돌핀 GCI 세이브 지갑에 마네를 더한다(사용자 요청 때만). 돌핀을 끈 뒤 실행.
python tools/save_money.py <더할 마네> [슬롯 0|1]
- 지갑: 본문 0x221C (u32 BE)
- 체크섬: 본문 0x2200 부터 0x8518 바이트 합(버전≥4 면 0xA634~0xA637 제외) → 0x2040, ~체크섬 → 0xA634
- 원본은 같은 폴더에 <이름>.bak_<날짜시각> 으로 남긴다"""
import os
import shutil
import struct
import subprocess
import sys
import time

H = 0x40
CARD = os.path.join(os.environ['APPDATA'], 'Dolphin Emulator', 'GC', 'JAP', 'Card A')


def csum(b):
    s = sum(b[H + 0x2200:H + 0x2200 + 0x10A3 * 8])
    if struct.unpack('>I', b[H + 0xA620:H + 0xA624])[0] >= 4:
        s -= sum(b[H + 0xA634:H + 0xA638])
    return s & 0xFFFFFFFF


def valid(b):
    c = csum(b)
    return (struct.unpack('>I', b[H + 0x2040:H + 0x2044])[0] == c and
            struct.unpack('>I', b[H + 0xA634:H + 0xA638])[0] == (~c & 0xFFFFFFFF))


def main():
    add = int(sys.argv[1]); slot = sys.argv[2] if len(sys.argv) > 2 else '0'
    if b'Dolphin.exe' in subprocess.run(['tasklist'], capture_output=True).stdout:
        sys.exit('돌핀이 켜져 있음 — 끄고 다시 실행')
    path = os.path.join(CARD, '01-GGFJ-GIFTPIA(%s).gci' % slot)
    raw = bytearray(open(path, 'rb').read())
    assert valid(raw), '원래 세이브 검사값이 안 맞음 — 손대지 않음'
    old = struct.unpack('>I', raw[H + 0x221C:H + 0x2220])[0]
    new = old + add
    assert 0 <= new < 0x80000000
    struct.pack_into('>I', raw, H + 0x221C, new)
    c = csum(raw)
    struct.pack_into('>I', raw, H + 0x2040, c)
    struct.pack_into('>I', raw, H + 0xA634, ~c & 0xFFFFFFFF)
    assert valid(raw)
    bak = path + '.bak_' + time.strftime('%m%d_%H%M%S')
    shutil.copy2(path, bak)
    open(path, 'wb').write(raw)
    print('슬롯 %s 지갑 %d → %d 마네, 백업 %s' % (slot, old, new, os.path.basename(bak)))


if __name__ == '__main__':
    main()
