"""2단계 출력 시험용 evt 생성: 모든 대사를 같은 글자 수의 한글 채움 문장으로 바꾼다(제어 코드·줄바꿈 유지).

사용: python make_test.py <출력 폴더>   → <출력 폴더>/evt/*.evt
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evt
import evt_patch
import kochar

FILL = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'filler_test.txt'), encoding='utf-8').read()  # 실제 번역문 음절(빈도 현실화)
ONEBYTE = kochar.load_onebyte(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'onebyte_test.txt'))
TOK = re.compile(r'(?:\{[0-9A-F]{2}\})+|\n|.', re.S)


def filler(src):
    """원문 토큰 구조를 유지하고 글자만 채움 문장으로 바꾼다."""
    import zlib
    out = []; k = zlib.crc32(src.encode('utf-8'))  # 원문마다 다른 채움(공유 효과를 부풀리지 않게)
    for t in TOK.findall(src):
        if t.startswith('{') or t == '\n':
            out.append(t)
        elif t in '　 ':
            out.append(' ')
        elif t in '！？…、。「」『』（）～ー・':
            out.append({'ー': '-', '、': ','}.get(t, t))
        else:
            out.append(FILL[k % len(FILL)]); k += 1
    return ''.join(out)


def convert(d):
    inline = {}; ptr = {}
    for kind, p, o, v, live in evt.texts(d):
        if kind == 'inline':
            src = evt.text_decode(d[o:v - 1])
            new = kochar.encode(filler(src), ONEBYTE)
            room = v - p - 2 - len(new)
            if v - p < 5 and room < 0:
                continue  # 5바이트 미만이라 우회 점프도 못 넣는 짧은 대사는 시험에서 건너뜀
            inline[p] = new
        else:
            e = evt.text(d, v)
            ptr[o] = kochar.encode(filler(evt.text_decode(d[v:e - 1])), ONEBYTE)
    return evt_patch.patch(d, inline, ptr, fill=kochar.SPACE)


if __name__ == '__main__':
    out = os.path.join(sys.argv[1], 'evt'); os.makedirs(out, exist_ok=True)
    tot0 = tot1 = 0
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'extract', 'dat', 'evt')
    for fn in [os.path.join(src_dir, x) for x in sorted(os.listdir(src_dir)) if x.endswith('.evt')]:  # 경로의 [GC] 때문에 glob 금지
        d = open(fn, 'rb').read(); nd = convert(d)
        open(os.path.join(out, os.path.basename(fn)), 'wb').write(nd)
        tot0 += len(d); tot1 += len(nd)
        print('%-28s %7d -> %7d (+%d%%)' % (os.path.basename(fn), len(d), len(nd), 100 * (len(nd) - len(d)) // len(d)))
    print('합계', tot0, '->', tot1)
