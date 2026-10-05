"""evt 대사 교체(우회 점프 방식).

인라인(66/7E/88): 원래 명령 자리를 `02 <새 위치>` 로 바꾸고, 파일 끝에 `<명령> <새 텍스트> 00 02 <원래 끝>` 을 붙인다.
  (share: 10바이트 이상이면 `08 <본문> 02 <원래 끝>` + 공유 본문 `<명령> <텍스트> 00 01`)
주소형(77/7F/89/6D C8): 파일 끝에 `<새 텍스트> 00` 을 붙이고 u32 만 고친다.
원래 바이트·주소는 하나도 옮기지 않는다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evt


def pad_tail(b, n, fill):
    """마지막 글자 바로 뒤(끝에 붙은 제어 코드들 앞)에 fill 바이트를 n 개 넣는다.
    제어 코드 인자(예: 05 01)를 페이지 넘김으로 오인하지 않도록 텍스트 문법대로 토큰을 나눈다."""
    k = 0; p = 0
    while p < len(b):
        c = b[p]
        if c < 0x28 and c != 0x0A:
            p += 1 + evt.TXT_ARG.get(c, 1)
            continue
        p += 1 if (c == 0x0A or c <= 0x7A or 0xA6 <= c <= 0xDD) else 2
        if c != 0x0A:
            k = p  # 마지막 글자 끝
    return b[:k] + bytes([fill]) * n + b[k:]


def patch(d, inline=None, ptr=None, share=True, fill=None):
    """inline: {명령 위치: 새 텍스트 바이트(0x00 제외)}, ptr: {u32 위치: 새 텍스트 바이트}

    share=True: 원래 자리가 10바이트 이상이면 `08 <본문>` + `02 <원래 끝>` 으로 바꾸고,
    본문 `<명령> <텍스트> 00 01` 은 같은 내용끼리 한 번만 붙인다(호출 후 복귀).
    """
    d = bytearray(d); tail = bytearray(); base = len(d); shared = {}
    base += (-base) % 4
    pad = bytes(base - len(d))

    def here():
        return base + len(tail)

    for p, new in sorted((inline or {}).items()):
        op = d[p]
        assert op in (0x66, 0x7E, 0x88), hex(p)
        end = evt.text(d, p + 1)
        room = end - p - 2 - len(new)  # 명령 1 + 텍스트 + 00 1
        if 1 <= room <= 4 and fill is not None:  # 1~4바이트 남으면 마지막 줄 끝(맨 끝 제어 코드 앞)에 공백을 채운다
            new = pad_tail(new, room, fill); room = 0
        if room == 0 or room >= 5:     # 제자리: 딱 맞거나, 남는 자리를 02 <원래 끝> 으로 건너뜀
            d[p + 1:p + 2 + len(new)] = new + b'\0'
            if room:
                d[p + 2 + len(new):p + 7 + len(new)] = b'\x02' + struct.pack('<I', end)
            continue
        assert end - p >= 5, '대사 명령이 5바이트보다 짧음 @%X' % p
        if share and end - p >= 10 and op != 0x88:
            key = bytes([op]) + new
            if key not in shared:
                shared[key] = here()
                tail += key + b'\0' + b'\x01'
            d[p:p + 10] = b'\x08' + struct.pack('<I', shared[key]) + b'\x02' + struct.pack('<I', end)
            continue
        at = here()
        tail += bytes([op]) + new + b'\0' + b'\x02' + struct.pack('<I', end)
        d[p:p + 5] = b'\x02' + struct.pack('<I', at)
    for o, new in sorted((ptr or {}).items()):
        at = here()
        tail += new + b'\0'
        d[o:o + 4] = struct.pack('<I', at)
    return bytes(d) + pad + bytes(tail)
