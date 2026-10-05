"""대사 넘침 검사(3단계 창 측정 결과 기준, docs/windows.md).

글자는 고정폭이라 글자 수 = 폭. 제어 코드는 폭 0, {10}(숫자)=5자, {11}(이름 끼워 넣기)=12자로 계산.
제어 코드 인자(예: {03}{02} 의 02)를 페이지 넘김·끼워 넣기로 오인하지 않도록 텍스트 문법대로 토큰을 나눈다.
"""
import re

LIMITS = {
    'dialog': {'hard': 28, 'soft': 20, 'lines': 3},   # 일반 대사(66/88, 주소형 77/7F/89)
    'choice': {'hard': 22, 'soft': 19},               # 선택지(7E, {12} 로 항목 구분)
}
INSERT_W = {'{10}': 5, '{11}': 12}
# evt.TXT_ARG 와 같음(제어 코드 뒤 인자 바이트 수). 표에 없는 코드는 인자 1개.
TXT_ARG = {0x01: 0, 0x02: 0, 0x07: 0, 0x10: 0, 0x11: 0, 0x13: 0, 0x0A: 0, 0x12: 0,
           0x03: 1, 0x04: 1, 0x05: 1, 0x06: 1, 0x09: 1, 0x0B: 1, 0x0C: 1, 0x0F: 1, 0x15: 1, 0x16: 1, 0x17: 1,
           0x08: 2, 0x0D: 2, 0x0E: 3}
TOK = re.compile(r'\{([0-9A-F]{2})\}|\n|.', re.S)


def tokens(text):
    """[(종류, 값)] 종류: 'ctl'(코드+인자 문자열), 'nl', 'ch'"""
    out = []; skip = 0; cur = None
    for m in TOK.finditer(text):
        if skip:
            cur[1] += m.group(0); skip -= 1
            if not skip:
                out.append(tuple(cur))
            continue
        if m.group(1):
            n = TXT_ARG.get(int(m.group(1), 16), 1)
            cur = ['ctl', m.group(0)]
            if n:
                skip = n
            else:
                out.append(tuple(cur))
        elif m.group(0) == '\n':
            out.append(('nl', '\n'))
        else:
            out.append(('ch', m.group(0)))
    return out


def pages(text):
    """페이지 목록(각 페이지 = 줄 목록, 줄 = 토큰 목록). 페이지 넘김은 인자 아닌 {01}·{02}."""
    pg = [[[]]]
    for t in tokens(text):
        if t[0] == 'ctl' and t[1] in ('{01}', '{02}'):
            pg.append([[]])
        elif t[0] == 'nl':
            pg[-1].append([])
        else:
            pg[-1][-1].append(t)
    return pg


def width(line_tokens):
    w = 0
    for k, v in line_tokens:
        if k == 'ch':
            w += 1
        elif v in INSERT_W:
            w += INSERT_W[v]
    return w


def is_ticker(text):
    return '{0C}{12}' in text  # 라디오 DJ 흐르는 자막: 길이 제한 없음


def check(text, op=0x66):
    """문제 목록 [(수준, 설명)]. 수준: 'error'(한도 초과) / 'warn'(권장 초과)."""
    out = []
    if is_ticker(text):
        return out
    if op == 0x7E:
        L = LIMITS['choice']; items = [[]]
        for t in tokens(text):
            if t == ('ctl', '{12}'):
                items.append([])
            else:
                items[-1].append(t)
        for i, item in enumerate(items):
            w = width(item)
            if w > L['hard']: out.append(('error', '선택지 %d번 %d자 > %d' % (i + 1, w, L['hard'])))
            elif w > L['soft']: out.append(('warn', '선택지 %d번 %d자 > 권장 %d' % (i + 1, w, L['soft'])))
        return out
    L = LIMITS['dialog']
    for pi, lines in enumerate(pages(text)):
        while lines and not any(k == 'ch' for k, v in lines[-1]):
            lines.pop()
        if len(lines) > L['lines']:
            out.append(('error', '%d쪽 %d줄 > %d' % (pi + 1, len(lines), L['lines'])))
        for li, line in enumerate(lines):
            w = width(line)
            if w > L['hard']: out.append(('error', '%d쪽 %d줄 %d자 > %d' % (pi + 1, li + 1, w, L['hard'])))
            elif w > L['soft']: out.append(('warn', '%d쪽 %d줄 %d자 > 권장 %d' % (pi + 1, li + 1, w, L['soft'])))
    return out
