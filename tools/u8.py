"""U8 아카이브(giftpia.dat) 목록·추출.

사용:
  python u8.py list <u8>            : 파일 목록(오프셋·크기·경로)
  python u8.py extract <u8> <outdir>
  python u8.py build <원본u8> <출력u8> [교체폴더]
"""
import os
import struct
import sys


def parse(data):
    assert data[:4] == b'\x55\xAA\x38\x2D', 'U8 아님'
    root_off, hdr_size, data_off = struct.unpack('>III', data[4:16])
    n = struct.unpack('>I', data[root_off + 8:root_off + 12])[0]
    nodes = [struct.unpack('>III', data[root_off + i * 12:root_off + i * 12 + 12]) for i in range(n)]
    strtab = root_off + n * 12

    def name(i):
        o = strtab + (nodes[i][0] & 0xFFFFFF)
        return data[o:data.index(b'\0', o)].decode('shift_jis')

    ents = []
    stack = [(n, '')]
    for i in range(1, n):
        while i >= stack[-1][0]:
            stack.pop()
        t, a, b = nodes[i]
        p = stack[-1][1] + name(i)
        if t >> 24:
            stack.append((b, p + '/'))
            ents.append((i, p + '/', None, None))
        else:
            ents.append((i, p, a, b))
    return (root_off, hdr_size, data_off), nodes, ents


def main():
    cmd, src = sys.argv[1], sys.argv[2]
    data = open(src, 'rb').read()
    hdr, nodes, ents = parse(data)
    if cmd == 'list':
        print('root 0x%X hdr 0x%X data 0x%X nodes %d' % (hdr + (len(nodes),)))
        for i, p, a, b in ents:
            if a is not None:
                print('%08X %9d %s' % (a, b, p))
    elif cmd == 'build':
        # build <원본u8> <출력> [교체폴더]: 원본 순서·32바이트 정렬·0 채움 그대로, 교체 파일만 바꿔 끼움
        dst = sys.argv[3]; rep = sys.argv[4] if len(sys.argv) > 4 else None
        root_off, hdr_size, data_off = hdr
        head = bytearray(data[:data_off])
        body = bytearray(); changed = 0
        for i, p, a, b in sorted([e for e in ents if e[2] is not None], key=lambda e: e[2]):
            blob = data[a:a + b]
            if rep and os.path.isfile(os.path.join(rep, p)):
                blob = open(os.path.join(rep, p), 'rb').read(); changed += 1
            body += bytes((-len(body)) % 0x20)
            struct.pack_into('>II', head, root_off + i * 12 + 4, data_off + len(body), len(blob))
            body += blob
        open(dst, 'wb').write(head + body)
        print('교체', changed, '크기', len(head) + len(body))
    elif cmd == 'extract':
        out = sys.argv[3]
        cnt = 0
        for i, p, a, b in ents:
            dst = os.path.join(out, p)
            if a is None:
                os.makedirs(dst, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, 'wb').write(data[a:a + b])
                cnt += 1
        print(cnt, 'files')


if __name__ == '__main__':
    main()
