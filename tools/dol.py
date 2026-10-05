"""DOL 섹션 파싱·주소 변환."""
import struct


class Dol:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        h = self.d[:0x100]
        offs = struct.unpack('>18I', h[0:72]); addrs = struct.unpack('>18I', h[72:144]); sizes = struct.unpack('>18I', h[144:216])
        self.secs = [(i, o, a, s) for i, (o, a, s) in enumerate(zip(offs, addrs, sizes)) if s]
        self.bss = struct.unpack('>II', h[0xD8:0xE0]); self.entry = struct.unpack('>I', h[0xE0:0xE4])[0]

    def a2o(self, a):
        for i, o, base, s in self.secs:
            if base <= a < base + s:
                return o + a - base
        return None

    def o2a(self, off):
        for i, o, base, s in self.secs:
            if o <= off < o + s:
                return base + off - o
        return None

    def is_text(self, a):
        return any(i < 7 and base <= a < base + s for i, o, base, s in self.secs)

    def u32(self, a):
        return struct.unpack('>I', self.d[self.a2o(a):self.a2o(a) + 4])[0]

    def read(self, a, n):
        o = self.a2o(a); return self.d[o:o + n]
