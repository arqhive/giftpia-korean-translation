"""GC 메모리 카드 이미지(.raw)에 GCI 파일을 넣는다(같은 게임 코드 파일은 먼저 지움).
python gci2raw.py <card.raw> <out.raw> <gamecode4> <a.gci> [b.gci ...]   (--list 만 주면 목록만)"""
import struct
import sys

B = 0x2000


def csum(data):
    a = b = 0
    for i in range(0, len(data), 2):
        w = struct.unpack('>H', data[i:i + 2])[0]
        a = (a + w) & 0xFFFF
        b = (b + (w ^ 0xFFFF)) & 0xFFFF
    return (0 if a == 0xFFFF else a), (0 if b == 0xFFFF else b)


def load(path):
    d = bytearray(open(path, 'rb').read())
    mbits = struct.unpack('>H', d[0x22:0x24])[0]
    nblk = mbits * 16
    assert len(d) >= nblk * B, (len(d), nblk)
    dirs = [d[B * i:B * (i + 1)] for i in (1, 2)]
    bats = [d[B * i:B * (i + 1)] for i in (3, 4)]
    for x in dirs:
        assert csum(x[:0x1FFC]) == struct.unpack('>HH', x[0x1FFC:0x2000]), 'dir checksum'
    for x in bats:
        assert csum(x[4:]) == struct.unpack('>HH', x[0:4]), 'bat checksum'
    di = 0 if struct.unpack('>h', dirs[0][0x1FFA:0x1FFC])[0] >= struct.unpack('>h', dirs[1][0x1FFA:0x1FFC])[0] else 1
    bi = 0 if struct.unpack('>h', bats[0][4:6])[0] >= struct.unpack('>h', bats[1][4:6])[0] else 1
    return d, nblk, bytearray(dirs[di]), bytearray(bats[bi])


def entries(dr):
    out = []
    for i in range(127):
        e = dr[i * 0x40:(i + 1) * 0x40]
        if e[:4] != b'\xff\xff\xff\xff':
            name = e[8:0x28].split(b'\0')[0].decode('ascii', 'replace')
            first, cnt = struct.unpack('>HH', e[0x36:0x3A])
            out.append((i, e[:4].decode('ascii', 'replace'), name, first, cnt))
    return out


def bat_get(bat, blk):
    return struct.unpack('>H', bat[0x0A + (blk - 5) * 2:0x0C + (blk - 5) * 2])[0]


def bat_set(bat, blk, v):
    bat[0x0A + (blk - 5) * 2:0x0C + (blk - 5) * 2] = struct.pack('>H', v)


def main():
    src = sys.argv[1]
    d, nblk, dr, bat = load(src)
    if len(sys.argv) == 2 or sys.argv[2] == '--list':
        for x in entries(dr):
            print(x)
        print('free', struct.unpack('>H', bat[6:8])[0], 'of', nblk - 5)
        return
    out, code, gcis = sys.argv[2], sys.argv[3].encode(), sys.argv[4:]
    # 같은 게임 파일 지우기
    for i, gc, name, first, cnt in entries(dr):
        if gc.encode() == code:
            b = first
            while True:
                nx = bat_get(bat, b)
                bat_set(bat, b, 0)
                if nx == 0xFFFF:
                    break
                b = nx
            dr[i * 0x40:(i + 1) * 0x40] = b'\xff' * 0x40
    # 넣기
    for g in gcis:
        raw = open(g, 'rb').read()
        ent = bytearray(raw[:0x40]); body = raw[0x40:]
        cnt = struct.unpack('>H', ent[0x38:0x3A])[0]
        assert len(body) == cnt * B, (g, len(body), cnt)
        free = [b for b in range(5, nblk) if bat_get(bat, b) == 0][:cnt]
        assert len(free) == cnt, 'not enough blocks'
        for k, b in enumerate(free):
            bat_set(bat, b, free[k + 1] if k + 1 < cnt else 0xFFFF)
            d[b * B:(b + 1) * B] = body[k * B:(k + 1) * B]
        ent[0x36:0x38] = struct.pack('>H', free[0])
        slot = next(i for i in range(127) if dr[i * 0x40:i * 0x40 + 4] == b'\xff\xff\xff\xff')
        dr[slot * 0x40:(slot + 1) * 0x40] = ent
        bat[8:0x0A] = struct.pack('>H', free[-1])
    bat[6:8] = struct.pack('>H', sum(1 for b in range(5, nblk) if bat_get(bat, b) == 0))
    # 갱신 번호·체크섬, 두 벌 모두
    dc = (struct.unpack('>h', dr[0x1FFA:0x1FFC])[0] + 1) & 0xFFFF
    dr[0x1FFA:0x1FFC] = struct.pack('>H', dc)
    dr[0x1FFC:0x2000] = struct.pack('>HH', *csum(dr[:0x1FFC]))
    bc = (struct.unpack('>h', bat[4:6])[0] + 1) & 0xFFFF
    bat[4:6] = struct.pack('>H', bc)
    bat[0:4] = struct.pack('>HH', *csum(bat[4:]))
    for i in (1, 2):
        d[B * i:B * (i + 1)] = dr
    for i in (3, 4):
        d[B * i:B * (i + 1)] = bat
    open(out, 'wb').write(d)
    _, _, dr2, bat2 = load(out)
    for x in entries(dr2):
        print(x)
    print('free', struct.unpack('>H', bat2[6:8])[0])


if __name__ == '__main__':
    main()
