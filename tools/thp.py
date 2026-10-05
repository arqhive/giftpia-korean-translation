"""THP(v1.1, 영상 JPEG + 소리) 읽기·다시 묶기.

  프레임 = [다음 프레임 크기, 이전 프레임 크기, 영상 크기, 소리 크기](u32 BE) + JPEG + 소리, 전체 32바이트 정렬.
  JPEG 는 스캔 데이터에 0xFF 뒤 0x00 채움이 없는 형태 → 읽을 때 채워 넣고, 쓸 때 다시 뺀다.

  python tools/thp.py info <thp>
  python tools/thp.py roundtrip <thp> <out>     무변경 재조립(원본과 바이트 비교)
  python tools/thp.py frames <thp> <dir> a b [step]   프레임 a~b 를 png 로
"""
import io
import os
import struct
import sys

SOI, EOI = b'\xff\xd8', b'\xff\xd9'
FF00, FF = b'\xff\x00', b'\xff'


class Thp:
    def __init__(self, path):
        self.f = open(path, 'rb'); self.path = path
        h = self.f.read(0x60); self.head = bytearray(h)
        (self.magic, self.ver, self.maxbuf, self.maxaudio, self.fps, self.n, self.first_size, self.datasize,
         self.comp_off, self.offs_off, self.movie_off, self.last_off) = struct.unpack('>4sIIIfIIIIIII', h[:0x30])
        self.w, self.h = struct.unpack('>II', h[0x44:0x4C])
        self.frames = []                                  # (오프셋, 전체 크기, 영상 크기, 소리 크기)
        o, sz = self.movie_off, self.first_size
        for i in range(self.n):
            self.f.seek(o); nxt, prv, vs, aus = struct.unpack('>4I', self.f.read(16))
            self.frames.append((o, sz, vs, aus)); o += sz; sz = nxt

    def raw_jpeg(self, i):
        o, sz, vs, aus = self.frames[i]; self.f.seek(o + 16); return self.f.read(vs)

    def audio(self, i):
        o, sz, vs, aus = self.frames[i]; self.f.seek(o + 16 + vs); return self.f.read(aus)

    def image(self, i):
        from PIL import Image
        return Image.open(io.BytesIO(stuff(self.raw_jpeg(i)))).convert('RGB')


def _scan_start(j):
    p = j.find(b'\xff\xda'); L = struct.unpack('>H', j[p + 2:p + 4])[0]
    return p + 2 + L


def stuff(j):
    """THP JPEG → 표준 JPEG(스캔 안 0xFF 뒤에 0x00)."""
    s = _scan_start(j); end = j.rfind(EOI)
    return j[:s] + j[s:end].replace(FF, FF00) + j[end:]


def unstuff(j):
    """표준 JPEG → THP JPEG. 원본 THP 와 같은 배치로 맞춘다:
    SOI, DQT 1개(표 0·1), SOF0, DHT 1개(표 00·01·10·11 순서), SOS, 스캔(0xFF00 → 0xFF), EOI. APPn·COM 은 뺀다."""
    p = 2; dqt = {}; dht = {}; sof = sos = None
    while True:
        assert j[p] == 0xFF
        m = j[p + 1]; L = struct.unpack('>H', j[p + 2:p + 4])[0]; body = j[p + 4:p + 2 + L]
        if m == 0xDB:
            q = 0
            while q < len(body):
                n = 65 if body[q] >> 4 == 0 else 129
                dqt[body[q] & 15] = body[q:q + n]; q += n
        elif m == 0xC4:
            q = 0
            while q < len(body):
                n = 17 + sum(body[q + 1:q + 17]); dht[body[q]] = body[q:q + n]; q += n
        elif m == 0xC0:
            sof = j[p:p + 2 + L]
        elif m == 0xDD:
            raise AssertionError('재시작 표지 없이 인코딩해야 함')
        elif m == 0xDA:
            sos = j[p:p + 2 + L]; s = p + 2 + L; break
        p += 2 + L
    out = bytearray(SOI)
    qb = b''.join(dqt[k] for k in sorted(dqt)); out += b'\xff\xdb' + struct.pack('>H', len(qb) + 2) + qb
    out += sof
    hb = b''.join(dht[k] for k in (0x00, 0x01, 0x10, 0x11)); out += b'\xff\xc4' + struct.pack('>H', len(hb) + 2) + hb
    out += sos
    end = j.rfind(EOI); scan = j[s:end]
    assert b'\xff\xd0' not in scan.replace(FF00, b'')
    out += scan.replace(FF00, FF) + EOI
    return bytes(out)


def encode(img, maxsize, q=90):
    """PIL 이미지 → THP JPEG(4:2:0 기준선). maxsize 안에 들어올 때까지 품질을 낮춘다."""
    while True:
        b = io.BytesIO(); img.save(b, 'JPEG', quality=q, subsampling=2, optimize=False, progressive=False)
        j = unstuff(b.getvalue())
        if len(j) <= maxsize or q <= 30:
            return j, q
        q -= 3


def rebuild(t, out, replace):
    """replace = {프레임 번호: THP JPEG 바이트}. 소리·나머지 프레임은 그대로. 머리(최대 버퍼·데이터 크기·첫/끝 프레임)를 다시 계산."""
    frames = []
    for i in range(t.n):
        j = replace.get(i) or t.raw_jpeg(i); a = t.audio(i)
        size = 16 + len(j) + len(a); size += (-size) % 32
        frames.append((j, a, size))
    head = bytearray(t.head)
    total = sum(s for _, _, s in frames)
    maxbuf = max(s for _, _, s in frames)
    last = t.movie_off + total - frames[-1][2]
    struct.pack_into('>I', head, 0x08, max(maxbuf, t.maxbuf))
    struct.pack_into('>I', head, 0x18, frames[0][2])
    struct.pack_into('>I', head, 0x1C, total)
    struct.pack_into('>I', head, 0x2C, last)
    with open(out, 'wb') as f:
        f.write(head)
        for i, (j, a, size) in enumerate(frames):
            nxt = frames[i + 1][2] if i + 1 < len(frames) else frames[0][2]
            prv = frames[i - 1][2] if i else frames[-1][2]
            blob = struct.pack('>4I', nxt, prv, len(j), len(a)) + j + a
            f.write(blob + bytes(size - len(blob)))
    return maxbuf


if __name__ == '__main__':
    cmd = sys.argv[1]; t = Thp(sys.argv[2])
    if cmd == 'info':
        print('ver %x  %dx%d  fps %.3f  frames %d  maxbuf %d  data %d  last %x' % (t.ver, t.w, t.h, t.fps, t.n, t.maxbuf, t.datasize, t.last_off))
    elif cmd == 'roundtrip':
        rebuild(t, sys.argv[3], {})
        a = open(sys.argv[2], 'rb').read(); b = open(sys.argv[3], 'rb').read()
        print('같음' if a == b else '다름: %d vs %d, 첫 차이 %s' % (len(a), len(b), next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), None)))
    elif cmd == 'frames':
        d = sys.argv[3]; os.makedirs(d, exist_ok=True)
        a, b = int(sys.argv[4]), int(sys.argv[5]); step = int(sys.argv[6]) if len(sys.argv) > 6 else 1
        for i in range(a, b, step):
            t.image(i).save(os.path.join(d, '%05d.png' % i))
