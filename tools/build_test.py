"""2단계 출력 시험 빌드.

  1) evt 44개: 모든 대사를 한글 채움 문장으로(make_test)
  2) 폰트: 돌핀 폰트 바탕 + 한글 2,350자(한자 칸) + 1바이트 칸(히라가나·가타카나 칸) → kofont.szs
     + ext/font.tpl(가나 그래픽 폰트)의 1바이트 칸
  3) main.dol: ROM 폰트 대신 /kofont.szs 를 읽게 패치
  4) giftpia.dat 재조립 → ISO(루트에 kofont.szs 추가)

사용: python build_test.py <출력 ISO> [fill|ruler]
"""
import os
import subprocess
import sys

T = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(T, '..')
sys.path.insert(0, T)
import dol_patch
import fonttpl
import iplfont
import kochar
import make_test
import make_ruler

BASE_FONT = os.environ.get('GIFTPIA_BASE_FONT', os.path.join(ROOT, 'extract', 'font_japanese.bin'))   # 시험용(Dolphin 의 Sys/GC/font_japanese.bin)
TTF = os.path.join(T, 'fonts', 'NanumSquareRoundB.ttf')


def main(out_iso, mode='fill'):
    W = os.path.join(ROOT, 'build', 'test_' + mode)
    os.makedirs(os.path.join(W, 'dat', 'evt'), exist_ok=True)
    # 1) evt
    src = os.path.join(ROOT, 'extract', 'dat', 'evt')
    for fn in sorted(os.listdir(src)):
        d = open(os.path.join(src, fn), 'rb').read()
        open(os.path.join(W, 'dat', 'evt', fn), 'wb').write((make_ruler if mode == 'ruler' else make_test).convert(d))
    # 2) 폰트
    glyphs = dict(kochar.CODE_HANGUL)
    for ch, b in make_test.ONEBYTE.items():
        glyphs[kochar.slot_sjis(b)] = ' ' if ch in (' ', '\u3000') else ch
    n = iplfont.build(BASE_FONT, glyphs, TTF, os.path.join(W, 'kofont.szs'))
    assert n <= 0x4D000, '폰트가 ROM 폰트 버퍼(0x4D000)보다 큼: %d' % n
    print('font', n)
    # 2-2) font.tpl: 가나·전각 영숫자는 이 그래픽 폰트로 그려지므로 1바이트 칸을 여기에도 그린다
    os.makedirs(os.path.join(W, 'dat', 'ext'), exist_ok=True)
    fonttpl.build(os.path.join(ROOT, 'extract', 'dat', 'ext', 'font.tpl'),
                  {kochar.slot_sjis(b): (' ' if ch in (' ', '　') else ch) for ch, b in make_test.ONEBYTE.items()},
                  TTF, os.path.join(W, 'dat', 'ext', 'font.tpl'))
    # 3) dol
    dol_patch.patch(os.path.join(ROOT, 'extract', 'main.dol'), os.path.join(W, 'main.dol'))
    # 4) dat · iso
    py = sys.executable
    subprocess.check_call([py, os.path.join(T, 'u8.py'), 'build', os.path.join(ROOT, 'extract', 'giftpia.dat'),
                           os.path.join(W, 'giftpia.dat'), os.path.join(W, 'dat')])
    subprocess.check_call([py, os.path.join(T, 'build_iso.py'), os.path.join(ROOT, 'Giftpia (Japan).iso'), out_iso,
                           '--rep', 'default.dol=' + os.path.join(W, 'main.dol'),  # DOL 은 디스크 끝, FST 의 default.dol 과 같은 영역
                           'giftpia.dat=' + os.path.join(W, 'giftpia.dat'),  # --rep 는 한 번만(두 번 쓰면 뒤의 것만 남음)
                           '--add', 'kofont.szs=' + os.path.join(W, 'kofont.szs')])


if __name__ == '__main__':
    main(sys.argv[1], *sys.argv[2:])  # 두 번째 인자: fill(기본) / ruler(3단계 창 측정)
