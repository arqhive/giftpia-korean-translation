"""Yay0 압축 풀기·압축."""
import struct


def decompress(src):
    assert src[:4] == b'Yay0'
    size, link, chunk = struct.unpack('>III', src[4:16])
    dst = bytearray(); mask = 0; bits = 0; mp = 16
    while len(dst) < size:
        if bits == 0:
            mask = struct.unpack('>I', src[mp:mp + 4])[0]; mp += 4; bits = 32
        if mask & 0x80000000:
            dst.append(src[chunk]); chunk += 1
        else:
            v = struct.unpack('>H', src[link:link + 2])[0]; link += 2
            dist = (v & 0xFFF) + 1; n = v >> 12
            if n == 0:
                n = src[chunk] + 0x12; chunk += 1
            else:
                n += 2
            for _ in range(n):
                dst.append(dst[-dist])
        mask = (mask << 1) & 0xFFFFFFFF; bits -= 1
    return bytes(dst)


def compress(data):
    """단순 탐욕 Yay0 압축(창 4096, 해시 체인)."""
    n = len(data); masks = []; links = bytearray(); chunks = bytearray()
    cur = 0; nb = 0; i = 0; table = {}
    def flag(b):
        nonlocal cur, nb
        cur = (cur << 1) | b; nb += 1
        if nb == 32:
            masks.append(cur); cur = 0; nb = 0
    while i < n:
        best = 0; bpos = 0
        if i + 3 <= n:
            key = data[i:i + 3]
            for p in reversed(table.get(key, [])[-64:]):
                if i - p > 0x1000: break
                l = 3
                while l < 0x111 and i + l < n and data[p + l] == data[i + l]: l += 1
                if l > best: best = l; bpos = p
                if l == 0x111: break
        if best >= 3:
            dist = i - bpos - 1
            if best >= 0x12:
                links += struct.pack('>H', dist); chunks.append(best - 0x12)
            else:
                links += struct.pack('>H', ((best - 2) << 12) | dist)
            flag(0)
            for k in range(best):
                if i + k + 3 <= n: table.setdefault(data[i + k:i + k + 3], []).append(i + k)
            i += best
        else:
            chunks.append(data[i]); flag(1)
            if i + 3 <= n: table.setdefault(data[i:i + 3], []).append(i)
            i += 1
    if nb:
        masks.append(cur << (32 - nb))
    mbytes = b''.join(struct.pack('>I', m) for m in masks)
    link_off = 16 + len(mbytes); chunk_off = link_off + len(links)
    return b'Yay0' + struct.pack('>III', n, link_off, chunk_off) + mbytes + bytes(links) + bytes(chunks)
