"""8단계 빌드: 번역·그림·모델·영상·폰트를 넣어 ISO 를 만든다.

  python tools/build.py <출력 ISO> [버전]

  1) 1바이트 한글 배정(실제 번역문 빈도) → translation/onebyte_final.txt
  2) evt 44개 재삽입(우회 점프)
  3) 폰트: ROM 폰트 대체 kofont.szs(엄마까투리체, 힌팅) + ext/font.tpl 1바이트 칸
  4) main.dol: 문구 956개(넘치는 258개는 새 섹션으로 옮기고 포인터 수정, 아레나 시작을 그 뒤로) + 폰트 읽기 패치
  5) 그림 101장(258곳) 써넣기, 3D 글자 모델 2개 교체
  6) giftpia.dat 재조립 → ISO(실행 파일·dat·오프닝 영상 교체, kofont.szs 추가)
"""
import csv
import json
import os
import re
import struct
import subprocess
import sys
import unicodedata
from collections import Counter

T = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(T, '..'))
sys.path.insert(0, T)
import dol_patch
import dol_tr
import evt
import evt_patch
import iplfont
import kochar
import texenc
import tpl
import yay0

TR = os.path.join(ROOT, 'translation')
EXT = os.path.join(ROOT, 'extract')
FONT = os.path.join(T, 'fonts', 'AndongKaturi.ttf')
FALLBACK = os.path.join(T, 'fonts', 'NanumSquareRoundB.ttf')
# 칸 구조만 빌림(쓰는 글자는 전부 새로 그림). Dolphin 의 Sys/GC/font_japanese.bin 을 extract/ 에 두거나 환경 변수로 지정
BASE_FONT = os.environ.get('GIFTPIA_BASE_FONT', os.path.join(ROOT, 'extract', 'font_japanese.bin'))
CTL = re.compile(r'\{[0-9A-F]{2}\}')


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- 1) 1바이트 한글

def onebyte_table():
    evt_items = json.load(open(os.path.join(TR, 'evt_texts.json'), encoding='utf-8'))
    ko = json.load(open(os.path.join(TR, 'evt_ko.json'), encoding='utf-8'))
    c = Counter()
    for e in evt_items:
        k = ko.get(e['id'], '')
        n = max(1, e['count'])                                   # 파일에 들어간 횟수만큼(공유되는 공용 대사는 여러 파일)
        for ch in CTL.sub('', k):
            if '가' <= ch <= '힣':
                c[ch] += n
    nslot = len([b for b in kochar.ONEBYTE_SLOTS if b != kochar.SPACE])
    s = ''.join(ch for ch, _ in c.most_common(nslot))
    p = os.path.join(TR, 'onebyte_final.txt'); open(p, 'w', encoding='utf-8').write(s)
    total = sum(c.values()); cover = sum(c[ch] for ch in s)
    log('1바이트 칸 %d개, 한글 음절 사용 중 %.1f%% 를 1바이트로' % (len(s), 100 * cover / total))
    return kochar.load_onebyte(p)


# ---------------------------------------------------------------- 2) evt

def build_evt(W, ONE):
    items = json.load(open(os.path.join(TR, 'evt_texts.json'), encoding='utf-8'))
    ko = json.load(open(os.path.join(TR, 'evt_ko.json'), encoding='utf-8'))
    key2id = evt_ids()
    assert len(key2id) == len(items), (len(key2id), len(items))
    for e in items[:50] + items[-50:]:                           # 짝 검증: 다시 매긴 id 의 원문 표기가 번역 파일과 같아야
        pass
    src = os.path.join(EXT, 'dat', 'evt'); out = os.path.join(W, 'dat', 'evt'); os.makedirs(out, exist_ok=True)
    tot0 = tot1 = 0; miss = []; short = []
    for fn in sorted(os.listdir(src)):
        d = open(os.path.join(src, fn), 'rb').read(); inline = {}; ptr = {}
        for kind, p, o, v, live in evt.texts(d):
            op = d[p]
            raw = d[o:v - 1] if kind == 'inline' else d[v:evt.text(d, v) - 1]
            i = key2id.get((op if kind == 'inline' else 'p%02X' % op, raw))
            if i is None:
                miss.append((fn, hex(p))); continue
            k = ko.get(i, '')
            if not k:
                continue
            new = kochar.encode(k, ONE)
            if kind == 'inline':
                if v - p < 5 and v - p - 2 - len(new) < 0:
                    short.append((fn, i, v - p, len(new))); continue
                inline[p] = new
            else:
                ptr[o] = new
        nd = evt_patch.patch(d, inline, ptr, fill=kochar.SPACE)
        open(os.path.join(out, fn), 'wb').write(nd)
        tot0 += len(d); tot1 += len(nd)
    log('evt %d개: %d → %d 바이트(+%d%%), 원문 짝 못 찾음 %d, 짧아서 못 넣음 %d' % (len(os.listdir(src)), tot0, tot1, 100 * (tot1 - tot0) // tot0, len(miss), len(short)))
    return miss, short


def used_codes(ONE):
    """번역문(evt·DOL)에 실제로 쓰인 2바이트 글자 코드 → 글자."""
    out = {}
    ko = json.load(open(os.path.join(TR, 'evt_ko.json'), encoding='utf-8'))
    L, dk = dol_tr.load()
    texts = list(ko.values()) + list(dk.values())
    for t in texts:
        for tok in re.findall(r'\{[0-9A-Fa-f]{2}\}|\n|.', CTL.sub('', t), re.S):
            if tok == '\n' or (tok in ONE):
                continue
            c = kochar.char_code(tok)
            out[c] = tok
    return out


def has_glyph(ttf, ch, _cache={}):
    from fontTools.ttLib import TTFont
    if ttf not in _cache:
        _cache[ttf] = set(TTFont(ttf).getBestCmap())
    return ord(ch) in _cache[ttf]


def draw_hinted(ch, cell, size, levels, cx=None, cy=None):
    """실제 크기로 그려 FreeType 힌팅을 받는다(엄마까투리체, 없으면 나눔스퀘어라운드). 0~levels-1 값 2차원 목록."""
    from PIL import Image, ImageDraw, ImageFont
    ttf = FONT if has_glyph(FONT, ch) else FALLBACK
    f = ImageFont.truetype(ttf, size)
    im = Image.new('L', (cell, cell), 0); d = ImageDraw.Draw(im); d.fontmode = 'L'
    d.text((cell / 2 if cx is None else cx, cell / 2 if cy is None else cy), ch, fill=255, font=f, anchor='mm')
    k = levels - 1
    return [[min(k, int(((im.getpixel((x, y)) / 255) ** 0.8) * k + 0.5)) for x in range(cell)] for y in range(cell)]


def build_fonts(W, ONE):
    """ROM 폰트 대체(kofont.szs): 한글 2,350자 + 번역문에 쓰인 기호 + 1바이트 칸. font.tpl: 1바이트 칸(가나 자리)."""
    from PIL import Image
    h, d = iplfont.load(BASE_FONT); d = bytearray(d)
    glyphs = dict(kochar.CODE_HANGUL)
    glyphs.update(used_codes(ONE))
    one = {kochar.slot_sjis(b): (' ' if ch in (' ', '　') else ch) for ch, b in ONE.items()}
    glyphs.update(one)
    nfb = 0
    skipped = []
    for code, ch in glyphs.items():
        try:
            idx = iplfont.index(code)
        except IndexError:
            idx = 0
        if not idx:                                               # ROM 폰트에 칸이 없는 코드(예: ①=0x8740, 원문도 같은 글자) → 원본과 같은 동작
            skipped.append(ch); continue
        if ch.strip():
            nfb += not has_glyph(FONT, ch)
            px = draw_hinted(ch, h['cellW'], 22, 4)
        else:
            px = [[0] * h['cellW'] for _ in range(h['cellH'])]
        iplfont.set_cell(h, d, idx, px)
        d[h['widthTable'] + idx] = h['cellW']
    comp = yay0.compress(bytes(d)); comp += bytes((-len(comp)) % 32)
    assert len(comp) <= 0x4D000, 'ROM 폰트 버퍼(0x4D000)보다 큼: %d' % len(comp)
    open(os.path.join(W, 'kofont.szs'), 'wb').write(comp)
    # font.tpl: 가나·전각 영숫자 그래픽 폰트(28px, I4). 1바이트 한글 칸만 다시 그린다.
    # 게임은 28px 칸을 24px ROM 칸 한가운데에 겹쳐 그리므로(가로·세로 2px 안쪽), ROM 과 같은 22px·같은 4단계 농도로
    # 중심만 (14,14) 에 그리면 화면에서 두 폰트 글자가 똑같다(v0.1 은 25px·16단계라 1바이트 글자가 더 크게 보였음).
    tp = bytearray(open(os.path.join(EXT, 'dat', 'ext', 'font.tpl'), 'rb').read())
    imgs = {i: tpl.decode(tp, doff, w, hh, fmt).getchannel('R') for i, w, hh, fmt, doff in tpl.images(tp) if i in (0, 1)}
    for code, ch in one.items():
        i, base = (0, 0x8240) if code < 0x8340 else (1, 0x8340)
        r, c = divmod(code - base, 16)
        px = draw_hinted(ch, 28, 22, 4, cx=14, cy=14) if ch.strip() else [[0] * 28 for _ in range(28)]
        cellim = Image.new('L', (28, 28))
        cellim.putdata([v * 85 for row in px for v in row])
        imgs[i].paste(cellim, (c * 28, r * 28))
    for i, im in imgs.items():
        tpl.replace_i4(tp, i, im)
    os.makedirs(os.path.join(W, 'dat', 'ext'), exist_ok=True)
    open(os.path.join(W, 'dat', 'ext', 'font.tpl'), 'wb').write(tp)
    log('폰트: ROM 폰트 %d자(대체 글꼴로 그린 기호 %d, 칸 없는 코드 건너뜀 %s) %d 바이트, font.tpl 1바이트 칸 %d'
        % (len(glyphs) - len(skipped), nfb, ''.join(skipped), len(comp), len(one)))


SEC_ADDR = 0x80508960          # 새 데이터 섹션: 디버거 스택 끝(0x80508958) 바로 뒤 = 원래 아레나 시작
ARENA_SETS = (0x801143E8, 0x80114420)   # OSInit 의 아레나 시작 lis/addi 두 곳(BootInfo 값이 0 일 때 · 일반 실행 때 스택 뒤)


def lis_addi(a):
    hi = (a >> 16) + (1 if a & 0x8000 else 0)
    return 0x3C600000 | (hi & 0xFFFF), 0x38630000 | (a & 0xFFFF)          # lis r3,hi ; addi r3,r3,lo


def build_dol(W):
    from dol import Dol
    src = os.path.join(EXT, 'main.dol'); D = Dol(src); d = bytearray(D.d)
    L, dk = dol_tr.load()
    blob = bytearray(); moved = {}; inplace = 0
    for x in L:
        k = dk.get(x['id'])
        if not k or x['id'] in dol_tr.KEEP:
            continue
        enc = dol_tr.encode(k) + b'\0'; a = int(x['addr'], 16); o = D.a2o(a)
        if len(enc) <= x['cap']:
            d[o:o + x['cap']] = enc + bytes(x['cap'] - len(enc)); inplace += 1
        else:
            while len(blob) % 4:
                blob.append(0)
            moved[a] = SEC_ADDR + len(blob); blob += enc
    while len(blob) % 32:
        blob.append(0)
    # 포인터 고치기: 데이터 섹션 안 u32 가 옛 주소인 곳
    npt = 0
    for i, o, base, s in D.secs:
        if i < 7:
            continue
        for k in range(0, s - 3, 4):
            v = struct.unpack('>I', d[o + k:o + k + 4])[0]
            if v in moved:
                struct.pack_into('>I', d, o + k, moved[v]); npt += 1
    assert set(moved) <= {struct.unpack('>I', D.d[o + k:o + k + 4])[0] for i, o, base, s in D.secs if i >= 7 for k in range(0, s - 3, 4)}
    # 새 섹션: 비어 있는 데이터 칸(7~17)에 파일 끝(32 정렬)
    slot = next(j for j in range(7, 18) if struct.unpack('>I', d[0x90 + 4 * j:0x94 + 4 * j])[0] == 0)
    while len(d) % 32:
        d.append(0)
    foff = len(d); d += blob
    struct.pack_into('>I', d, 4 * slot, foff); struct.pack_into('>I', d, 0x48 + 4 * slot, SEC_ADDR); struct.pack_into('>I', d, 0x90 + 4 * slot, len(blob))
    end = SEC_ADDR + len(blob)
    for at in ARENA_SETS:                                          # 원래 명령이 lis r3 / addi r3,r3 인지 확인하고 바꾼다
        o = D.a2o(at)
        w1, w2 = struct.unpack('>II', d[o:o + 8])
        assert w1 >> 16 == 0x3C60 and w2 >> 16 == 0x3863, hex(at)
        struct.pack_into('>II', d, o, *lis_addi(end))
    tmp = os.path.join(W, 'main_text.dol'); open(tmp, 'wb').write(d)
    dol_patch.patch(tmp, os.path.join(W, 'main.dol'))
    log('main.dol: 제자리 %d, 새 섹션(D%d @%08X, %d바이트)으로 옮김 %d, 포인터 %d곳, 아레나 시작 → %08X'
        % (inplace, slot - 7, SEC_ADDR, len(blob), len(moved), npt, end))


def build_gfx(W):
    """확정 그림을 담긴 파일(중복 포함 모든 위치)에 같은 형식으로 써넣고, 3D 글자 모델 2개를 바꾼다."""
    import shutil
    from PIL import Image
    conf = {os.path.normpath(r['png']): r for r in csv.DictReader(open(os.path.join(TR, 'graphics_list.csv'), encoding='utf-8-sig'))
            if r['status'] == '확정' and r['final'].endswith('.png')}
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, 'work', 'gfx_survey', 'index.csv'), encoding='utf-8'))
            if os.path.normpath(r['path']) in conf]
    files = {}; enc_cache = {}
    for r in rows:
        src = r['src']; rel = 'preload.cmb' if src.startswith('preload/') else src
        if rel not in files:
            cur = os.path.join(W, 'dat', rel)
            files[rel] = bytearray(open(cur if os.path.exists(cur) else os.path.join(EXT, 'dat', rel), 'rb').read())
        f = files[rel]
        off, w, h, fmt = texenc.locate(bytes(f), src, r['label'])
        c = conf[os.path.normpath(r['path'])]
        key = (c['n'], fmt)
        if key not in enc_cache:
            img = Image.open(os.path.join(ROOT, c['final'])).convert('RGBA')
            assert img.size == (w, h), (c['n'], img.size, (w, h))
            enc_cache[key] = texenc.encode(img, fmt)
        b = enc_cache[key]; assert len(b) == texenc.tsize(w, h, fmt)
        f[off:off + len(b)] = b
    for rel, f in files.items():
        p = os.path.join(W, 'dat', rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(f)
    for name in ('haraheri_endtxt.dat', 'dmy_endtxt.dat'):
        p = os.path.join(W, 'dat', 'map', 'worldmap'); os.makedirs(p, exist_ok=True)
        shutil.copy(os.path.join(ROOT, 'work', 'model', name), os.path.join(p, name))
    log('그림 %d장 → %d곳(파일 %d개), 3D 글자 모델 2개' % (len(conf), len(rows), len(files)))


def build_iso(W, out_iso):
    py = sys.executable
    subprocess.check_call([py, os.path.join(T, 'u8.py'), 'build', os.path.join(EXT, 'giftpia.dat'),
                           os.path.join(W, 'giftpia.dat'), os.path.join(W, 'dat')])
    subprocess.check_call([py, os.path.join(T, 'build_iso.py'), os.path.join(ROOT, 'Giftpia (Japan).iso'), out_iso,
                           '--rep', 'default.dol=' + os.path.join(W, 'main.dol'),
                           'giftpia.dat=' + os.path.join(W, 'giftpia.dat'),
                           'gift/mov/opening.thp=' + os.path.join(ROOT, 'work', 'movie', 'opening.thp'),
                           '--add', 'kofont.szs=' + os.path.join(W, 'kofont.szs')])


def main(out_iso, ver='v0.1'):
    W = os.path.join(ROOT, 'build', ver.replace('.', ''))
    os.makedirs(W, exist_ok=True)
    ONE = onebyte_table()
    build_evt(W, ONE)
    build_fonts(W, ONE)
    build_dol(W)
    build_gfx(W)
    build_iso(W, out_iso)


def evt_ids():
    """추출(extract_text.py)과 같은 순서로 훑어 (명령, 원문 바이트) → id. 원문 표기도 번역 파일과 대조한다."""
    import extract_text
    items = json.load(open(os.path.join(TR, 'evt_texts.json'), encoding='utf-8'))
    src = os.path.join(EXT, 'dat', 'evt'); key2id = {}; order = []
    for fn in extract_text.map_order():
        d = open(os.path.join(src, fn), 'rb').read()
        for kind, p, o, v, live in evt.texts(d):
            op = d[p]
            raw = d[o:v - 1] if kind == 'inline' else d[v:evt.text(d, v) - 1]
            key = (op if kind == 'inline' else 'p%02X' % op, raw)
            if key not in key2id:
                key2id[key] = 'E%05d' % (len(order) + 1); order.append(key)
    bad = [i for i, key in enumerate(order) if evt.text_decode(key[1]) != items[i]['jp']]
    assert not bad, '추출 순서와 번역 파일이 어긋남: %s' % bad[:5]
    return key2id


if __name__ == "__main__" and len(sys.argv) > 1:
    main(*sys.argv[1:])
