"""기프트피아 evt 바이트코드 역어셈블러.

- 해석기: main.dol 0x80049228, 명령표 0x80194080 (유효 명령 58개)
- 주소(u32 LE)는 모두 evt 파일 시작 기준(ctx+0x154 = 파일 시작)
- 헤더: LE u32 x12. [7]=공통 진입점 표, [8]=맵 진입점 표(0으로 끝남)
- 대사: 66/7E/88 인라인 텍스트(0x00 끝), 77/7F/89 u32 텍스트 주소, 6D C8 u32 텍스트 주소
"""
import struct

# ── 식(0x80048478) ──
EXPR_BIN = set(range(0x00, 0x06)) | set(range(0x07, 0x0F)) | {0x2B}
EXPR_UN = {0x06, 0x10, 0x11, 0x14, 0x15, 0x19, 0x1A, 0x24, 0x26, 0x27, 0x2E, 0x2F, 0x30, 0x35, 0x37}
EXPR_IMM = {0x0F: 2, 0x2A: 4, 0x12: 1, 0x34: 1}
EXPR_LEAF = {0x13, 0x16, 0x17, 0x18, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x21, 0x22, 0x23, 0x25, 0x28, 0x29,
             0x31, 0x32, 0x33, 0x36}
COND_EXPR = set(range(0x06, 0x15)) | set(range(0x16, 0x24)) | {0x27, 0x29, 0x2A, 0x2B} | set(range(0x2D, 0x35)) | {0x36, 0x37}
T_EXPR = {0x10, 0x11, 0x19, 0x1A, 0x27, 0x2E, 0x2F, 0x30}
T_BAD = {0x15, 0x24, 0x25, 0x26, 0x2A, 0x2C, 0x34, 0x35}


class ParseError(Exception):
    pass


def u16(d, p):
    return d[p] | d[p + 1] << 8


def u32(d, p):
    return struct.unpack_from('<I', d, p)[0]


def expr(d, p, refs):
    c = d[p]; p += 1
    if c in EXPR_BIN:
        return expr(d, expr(d, p, refs), refs)
    if c == 0x2D:  # 표 읽기: 크기, 색인, 데이터 주소
        p = expr(d, expr(d, p, refs), refs)
        refs.append(('data', p, u32(d, p)))
        return p + 4
    if c in EXPR_UN:
        return expr(d, p, refs)
    if c in EXPR_IMM:
        return p + EXPR_IMM[c]
    if c in EXPR_LEAF:
        return p
    raise ParseError('expr %02X @%X' % (c, p - 1))


def cond(d, p, refs):
    c = d[p]
    if c <= 5:
        return expr(d, expr(d, p + 1, refs), refs)
    if c in COND_EXPR:
        return expr(d, p, refs)
    raise ParseError('cond %02X @%X' % (c, p))


def stmt(d, p, refs):
    p = cond(d, p, refs) if d[p] <= 5 else expr(d, p, refs)
    t = d[p]; p += 1
    if t == 0x12:
        return p + 1
    if t in T_EXPR:
        return expr(d, p, refs)
    if t < 0x10 or t > 0x37 or t in T_BAD:
        raise ParseError('tgt %02X @%X' % (t, p - 1))
    return p


# ── 텍스트(0x8008EA44) ──
TXT_ARG = {0x01: 0, 0x02: 0, 0x07: 0, 0x10: 0, 0x11: 0, 0x13: 0, 0x0A: 0, 0x12: 0,
           0x03: 1, 0x04: 1, 0x05: 1, 0x06: 1, 0x09: 1, 0x0B: 1, 0x0C: 1, 0x0F: 1, 0x15: 1, 0x16: 1, 0x17: 1,
           0x08: 2, 0x0D: 2, 0x0E: 3}


def text(d, p):
    """인라인 텍스트를 0x00 까지 건너뛴다. 0x00 다음 위치를 돌려준다."""
    while True:
        c = d[p]
        if c == 0x00:
            return p + 1
        if c < 0x28:
            p += 1 + TXT_ARG.get(c, 1)  # 표에 없는 코드는 엔진처럼 2바이트로 읽는다
        elif c <= 0x7A or 0xA6 <= c <= 0xDD:  # 히라가나 1바이트, 반각 가나표(0x8016E5E8)
            p += 1
        else:  # 엔진은 나머지를 모두 2바이트 글자로 읽는다(0x8008ED48)
            p += 2


# ── 명령 ──
L69 = {0: [0xC9, 0xEE, 0xF6, 0xEF, 0xF7, 0xE5, 0xDE, 0xEB, 0xF9, 0xFB, 0xCB, 0xD3, 0xDA, 0xE3, 0xE9, 0xEA, 0xF3,
           0xF4, 0xFD, 0x1E, 0x1F, 0x20, 0x28, 0x21],
       2: [0xCC, 0xCD, 0xFC, 0xF1, 0xF2, 0xF8, 0x1C, 0xCE, 0xF5], 4: [0xC8, 0xE1]}
M69 = {s: n for n, l in L69.items() for s in l}
F6D = {0xC9: 10, 0xEE: 6, 0xF6: 6, 0xEF: 3, 0xF7: 3, 0xE5: 19, 0xE6: 16, 0xF0: 19, 0xEB: 4, 0xF9: 4, 0xFB: 4,
       0xC5: 0, 0xC6: 1, 0xC7: 1, 0xC3: 1}
SUB76 = {0xCC: 14, 0xD5: 14, 0xD4: 4, 0xDC: 2, 0xDD: 0, 0xF2: 0, 0xCD: 4, 0xD7: 4, 0xD8: 4, 0xDB: 4, 0xE7: 4,
         0xE2: 4, 0xD9: 2, 0xE4: 2, 0xED: 4}
FIXED = {0x71: 2, 0x85: 7, 0x78: 14, 0x79: 4, 0x7A: 8, 0x9D: 10, 0x7B: 17, 0x7C: 7, 0x7D: 7, 0x80: 3,
         0x81: 3, 0x86: 21, 0x8B: 2, 0x8C: 0, 0x92: 4, 0x97: 4, 0x9E: 1, 0x09: 0, 0x0A: 0, 0x74: 6}
END = {0x01, 0xFF, 0x68}  # 흐름이 끝나는 명령


def ins(d, p):
    """명령 하나를 해석. (다음 위치, refs, 이어서 실행?) 를 돌려준다.
    refs 항목: (종류, 피연산자 위치, 값). 종류: jmp/jcc/call/code(코드 주소), data, str(이름 문자열),
    txt(인라인 텍스트: 위치=텍스트 시작, 값=끝), tptr(텍스트 주소)"""
    op = d[p]; q = p + 1; R = []
    if op in (0x01, 0xFF):
        return q, R, False
    if op == 0x68:
        return q + 1, R, False
    if op in (0x02, 0x07):
        R.append(('jmp', q, u32(d, q))); return q + 4, R, False
    if op == 0x08:
        R.append(('call', q, u32(d, q))); return q + 4, R, True
    if op == 0x04:
        q = cond(d, q, R); R.append(('jcc', q, u32(d, q))); return q + 4, R, True
    if op in FIXED:
        return q + FIXED[op], R, True
    if op == 0x0B:
        return expr(d, q, R), R, True
    if op == 0x03:
        return stmt(d, q, R), R, True
    if op in (0x66, 0x7E, 0x88):
        e = text(d, q); R.append(('txt', q, e)); return e, R, True
    if op in (0x77, 0x7F, 0x89):
        R.append(('tptr', q, u32(d, q))); return q + 4, R, True
    if op == 0x9A:
        return d.index(b'\0', q) + 1, R, True
    if op == 0x83:
        return q + 2 + 4 * d[q + 1], R, True
    if op == 0x6C:
        return q + 3 + 4 * d[q + 2], R, True
    if op == 0x70:
        v = u32(d, q + 4)
        if v not in (0, 0xFFFFFFFF): R.append(('code', q + 4, v))
        return q + 10, R, True
    if op == 0x84:
        v = u32(d, q + 2)
        if v: R.append(('code', q + 2, v))
        return q + 6, R, True
    if op == 0x87:
        v = u32(d, q + 2)
        if v: R.append(('data', q + 2, v))
        return q + 6, R, True
    if op == 0x96:
        v = u32(d, q + 2)
        if v: R.append(('str', q + 2, v))
        return q + 6, R, True
    if op == 0x67:
        r = q + 9
        while u16(d, r) != 0xFFFF:
            r += 6
        return r + 2, R, True
    if op == 0x69:
        s = d[q]
        if s not in M69: raise ParseError('69 sub %02X @%X' % (s, p))
        return q + 1 + M69[s], R, True
    if op == 0x6D:
        s = d[q]
        if s in F6D: n = F6D[s]
        elif s == 0xDE: n = 5 if d[q + 1] else 1
        elif s == 0xE0: n = 2 if d[q + 1] in (1, 2) else 1
        elif s in (0xC8, 0xC4):
            if d[q + 2] == 0: n = 2
            else:
                n = 15 if s == 0xC8 else 14
                if s == 0xC8:
                    v = u32(d, q + 8)
                    if v: R.append(('tptr', q + 8, v))
        else: raise ParseError('6D sub %02X @%X' % (s, p))
        return q + 1 + n, R, True
    if op == 0x76:
        s = d[q]
        if s not in SUB76: raise ParseError('76 sub %02X @%X' % (s, p))
        if s == 0xED:
            v = u32(d, q + 1)
            if v: R.append(('data', q + 1, v))
        return q + 1 + SUB76[s], R, True
    if op == 0x93:
        s = d[q]
        if s not in (0, 1): raise ParseError('93 sub @%X' % p)
        return q + (8 if s == 0 else 14), R, True  # 93 00 id id2 u16 u8 / 93 01 id s32 s32 u16 u8
    if op == 0x9C:
        s = d[q]
        if s not in (0, 1): raise ParseError('9C sub @%X' % p)
        return q + (3 if s == 0 else 8), R, True  # 9C 00 id / 9C 01 id id2 u16 u8
    if op == 0x95:
        return q + 4 + d[q + 3], R, True
    if op == 0x82:
        s = d[q]
        r = q + 3 if s == 3 else (q + 9 if s == 4 else q)  # 82 04 u16 u32 s16 ... FF
        while d[r] != 0xFF:
            r += 1
        return r + 1, R, True
    if op == 0x8A:
        q = expr(d, q, R); v = u32(d, q)
        if v: R.append(('code', q, v))
        return expr(d, q + 4, R), R, True
    if op == 0x8D:
        v = u32(d, q); R.append(('data', q, v))
        return expr(d, expr(d, expr(d, q + 4, R), R), R), R, True
    if op == 0x90:
        return q + (7 if d[q + 1] == 0xEC else 1), R, True
    if op == 0x91:
        return q + (6 if d[q] < 2 else 1), R, True
    if op == 0x94:
        if u16(d, q + 2) == 0xFFFF: return q + 4, R, True
        return q + 0x11 + d[q + 0x10], R, True
    if op == 0x98:
        v = u32(d, q + 2)
        if v: R.append(('str', q + 2, v))
        return q + 7, R, True
    if op == 0x99:
        return q + 2 + 2 * d[q + 1], R, True
    if op == 0x9B:
        if d[q + 1] == 3: R.append(('data', q + 2, u32(d, q + 2)))
        return q + 6, R, True
    raise ParseError('op %02X @%X' % (op, p))


CODE_REFS = ('jmp', 'jcc', 'call', 'code')


def header(d):
    return struct.unpack_from('<12I', d, 0)


def entries(d):
    """진입점: 헤더 7·8번 표 + 헤더가 직접 가리키는 코드 구획(5·6·11) 시작."""
    h = header(d); out = [h[5], h[6], h[11]]
    for k in (7, 8):
        p = h[k]
        while True:
            v = u32(d, p)
            if v == 0 or v >= len(d): break  # map_02 는 0 종료 없이 문자열이 이어짐
            out.append(v); p += 4
    return out


def trace(d, starts=None):
    """진입점에서 재귀 추적. {위치: (다음, refs)} 와 오류 목록을 돌려준다."""
    todo = list(starts if starts is not None else entries(d))
    seen = {}; errs = []
    while todo:
        p = todo.pop()
        while p not in seen:
            try:
                n, R, ft = ins(d, p)
            except (ParseError, IndexError, ValueError, struct.error) as e:
                errs.append((p, str(e))); break
            seen[p] = (n, R)
            for k, o, v in R:
                if k in CODE_REFS and v not in seen:
                    todo.append(v)
            if not ft: break
            p = n
    return seen, errs


def sweep(d, seen):
    """추적이 닿지 않은 구간을 직선 해석(죽은 코드 후보). {위치: (다음, refs)} 를 돌려준다."""
    cov = bytearray(len(d))
    for p, (n, R) in seen.items():
        cov[p:n] = b'' * (n - p)
    h = header(d); out = {}
    for i in (5, 6, 10, 11):
        p = h[i]
        end = min([x for x in h if x > h[i]] + [len(d)])
        while p < end:
            if cov[p]:
                p += 1; continue
            q = p; got = {}
            try:
                while q < end and not cov[q]:
                    n, R, ft = ins(d, q)
                    got[q] = (n, R); q = n
            except (ParseError, IndexError, ValueError, struct.error):
                got = {}  # 깨끗하게 안 읽히는 구간은 버린다
            out.update(got)
            while p < end and not cov[p]:
                p += 1
    return out


def text_decode(b):
    """텍스트 바이트(0x00 제외) → '{XX}' 제어 표기 + 글자. 제어 코드 인자도 {XX} 로 쓴다."""
    out = []; p = 0
    while p < len(b):
        c = b[p]
        if c == 0x0A:
            out.append('\n'); p += 1
        elif c < 0x28:
            n = 1 + TXT_ARG.get(c, 1)
            out.append(''.join('{%02X}' % x for x in b[p:p + n])); p += n
        elif c <= 0x7A:
            out.append(bytes([0x82, 0x9F + c - 0x28]).decode('cp932')); p += 1
        elif 0xA6 <= c <= 0xDD:
            out.append(bytes([c]).decode('cp932')); p += 1
        else:
            pair = b[p:p + 2]
            try:
                out.append(pair.decode('cp932'))
            except UnicodeDecodeError:
                out.append('{%02X}{%02X}' % (pair[0], pair[1]))
            p += 2
    return ''.join(out)


def texts(d):
    """파일의 모든 대사 위치. [(종류, 명령 위치, 텍스트 시작, 텍스트 끝(0x00 다음), 살아있음?)]"""
    seen, E = trace(d)
    if E:
        raise ParseError('trace errors: %d' % len(E))
    sw = sweep(d, seen); out = []; ptr_done = set()
    for live, S in ((True, seen), (False, sw)):
        for p, (n, R) in sorted(S.items()):
            for k, o, v in R:
                if k == 'txt':
                    out.append(('inline', p, o, v, live))
                elif k == 'tptr' and v < len(d):
                    out.append(('ptr', p, o, v, live))  # o=u32 위치, v=텍스트 위치
    return out
