"""한글 → 게임 글자 코드.

- 한글 2,350자(KS X 1001 순서)를 SJIS 1수준 한자 코드 0x889F 부터 유효한 칸에 차례로 배정
- 그 밖의 글자는 전각 SJIS 로 바꿔 쓴다(1바이트 0x28~0x7A 는 히라가나라서 ASCII 를 그대로 쓸 수 없음)
- 제어 코드는 {XX} 꼴로 적는다(원문 텍스트 디코더 gtext 와 같은 표기)
"""
import re
import unicodedata

HANGUL = [bytes([hi, lo]).decode('euc-kr') for hi in range(0xB0, 0xC9) for lo in range(0xA1, 0xFF)]


def _kanji_codes():
    out = []
    for hi in range(0x88, 0x99):
        for lo in range(0x40, 0xFD):
            c = hi << 8 | lo
            if lo == 0x7F or c <= 0x889E or c > 0x9872:
                continue
            out.append(c)
    return out


KANJI = _kanji_codes()
assert len(KANJI) >= len(HANGUL)
HANGUL_CODE = {ch: KANJI[i] for i, ch in enumerate(HANGUL)}
CODE_HANGUL = {v: k for k, v in HANGUL_CODE.items()}

# 반각 → 전각(SJIS 에 있는 것만)
_FW = {' ': '　', '~': '～', '-': '－', "'": '’', '"': '”'}


def char_code(ch):
    if ch in HANGUL_CODE:
        return HANGUL_CODE[ch]
    if ch in _FW:
        ch = _FW[ch]
    elif '!' <= ch <= '}':
        ch = chr(ord(ch) + 0xFEE0)
    try:
        b = ch.encode('cp932')
    except UnicodeEncodeError:
        raise ValueError('표현할 수 없는 글자: %r (U+%04X %s)' % (ch, ord(ch), unicodedata.name(ch, '')))
    if len(b) != 2:
        raise ValueError('2바이트가 아닌 글자: %r' % ch)
    return b[0] << 8 | b[1]


# ── 1바이트 한글(evt 대사 전용) ──
# 0x28~0x7A: 히라가나 칸(SJIS 0x829F+), 0xA6~0xDD: 반각 가나 → 전각 가타카나 칸(0x8016B624 표).
# 0xB0(ｰ)은 전각 「ー」 칸을 함께 쓰므로 제외.
ONEBYTE_SLOTS = list(range(0x28, 0x7B)) + [b for b in range(0xA6, 0xDE) if b != 0xB0]
_H2F = str.maketrans('ｦｧｨｩｪｫｬｭｮｯｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ',
                     'ヲァィゥェォャュョッアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン')


SPACE = 0x28  # 1바이트 공백(빈 칸 글자). 남는 자리 채우기에도 쓴다.


def load_onebyte(path):
    """빈도순 음절을 한 줄로 적은 파일 → {글자: 바이트}. 첫 칸(0x28)은 공백."""
    s = open(path, encoding='utf-8').read().strip()
    slots = [b for b in ONEBYTE_SLOTS if b != SPACE]
    s = s[:len(slots)]
    assert len(set(s)) == len(s)
    m = {ch: slots[i] for i, ch in enumerate(s)}
    m[' '] = SPACE
    m['　'] = SPACE
    return m


def slot_sjis(b):
    """1바이트 칸이 실제로 그려지는 SJIS 코드."""
    if 0x28 <= b <= 0x7A:
        return 0x829F + b - 0x28
    e = bytes([b]).decode('cp932').translate(_H2F).encode('cp932')
    return e[0] << 8 | e[1]


def encode(s, onebyte=None):
    """'{05}{04}안녕\\n' 꼴 문자열 → 게임 바이트(끝의 0x00 제외). onebyte: {음절: 바이트}(evt 대사 전용)"""
    out = bytearray()
    for tok in re.findall(r'\{[0-9A-Fa-f]{2}\}|\n|.', s, re.S):
        if tok == '\n':
            out.append(0x0A)
        elif len(tok) == 4 and tok[0] == '{':
            out.append(int(tok[1:3], 16))
        elif onebyte and tok in onebyte:
            out.append(onebyte[tok])
        else:
            c = char_code(tok)
            out += bytes([c >> 8, c & 0xFF])
    return bytes(out)
