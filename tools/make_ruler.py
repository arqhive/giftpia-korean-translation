"""3단계 창 측정용: 대사를 '자'로 바꾼다.

- 일반 대사(66/7E 제외): 앞머리 제어 코드는 그대로 두고, 28자 자 4줄 + 원래 끝 제어 코드
  줄마다 첫 글자로 줄 번호(１~４)를 넣어 몇 줄까지 보이는지 알 수 있게 한다.
- 선택지(7E): 항목 수는 그대로, 항목마다 22자 자
- 라디오 자막(화자 0C 12): 그대로 둔다
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evt
import evt_patch
import kochar

RULER = '가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허'   # 28자, 모두 다른 글자
NUM = '１２３４'


def ruler_text(src, op):
    m = re.match(r'((?:\{[0-9A-F]{2}\})*)', src); head = m.group(1)
    m2 = re.search(r'((?:\{[0-9A-F]{2}\})*)$', src); tail = m2.group(1)
    if '{0C}{12}' in src:
        return None
    if op == 0x7E:
        n = src.count('{12}') + 1
        return head + '{12}'.join(RULER[:22] for _ in range(n))
    lines = [NUM[i] + RULER[1:28] for i in range(4)]
    return head + '\n'.join(lines) + (tail if tail else '{02}')


def convert(d):
    inline = {}
    for kind, p, o, v, live in evt.texts(d):
        if kind != 'inline':
            continue
        src = evt.text_decode(d[o:v - 1])
        new = ruler_text(src, d[p])
        if new is None or v - p < 5:
            continue
        inline[p] = kochar.encode(new)
    return evt_patch.patch(d, inline, {}, fill=kochar.SPACE)
