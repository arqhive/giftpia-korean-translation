"""배포용 파일 단위 패처 생성기 (게임큐브, disc-file-patcher 스킬의 기프트피아판).

이 게임의 빌드(build_iso.py)는
  - 바뀐 파일이 원래 자리에 들어가면 제자리, 커졌으면 앞쪽 빈 영역에 놓고(실행 파일 default.dol 도 옮겨짐 → 헤더 0x420),
  - 루트에 kofont.szs 를 추가하고(FST 가 길어짐 → 헤더 0x428·0x42C),
  - 새 파일에 쓰므로 파일 사이 여백은 0 이다.
그래서 사용자용 patch.ps1 은 0으로 채운 새 ISO 에
  원본 앞부분(헤더~첫 파일 전) → 안 바뀐 파일(원래 자리) → 바뀐·추가 파일(manifest 위치) → 새 FST → 헤더 16바이트
를 차례로 쓴다. 정본 ISO에 적용하면 빌드와 바이트까지 같은 ISO가 나온다.

사용:
  python tools/make_patcher.py --orig "Giftpia (Japan).iso" --build build/Giftpia_KO_v0.1.2.iso \\
      --out release/GGFJ_KPatch_v0.1 --version 0.1 --bin <wit·xdelta3 폴더> --readme patcher/README.txt
"""
import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_iso import read_fst, DISC_SIZE  # noqa: E402

BIN_FILES = ('wit.exe', 'cygwin1.dll', 'cygz.dll', 'cygcrypto-1.1.dll', 'cygncursesw-10.dll', 'wit-gpl-2.0.txt', 'xdelta3.exe')


def md5(b):
    return hashlib.md5(b).hexdigest()


def read_at(path, off, size):
    with open(path, 'rb') as f:
        f.seek(off)
        return f.read(size)


def disc(path):
    with open(path, 'rb') as f:
        dol, fst_off, fst, ents = read_fst(f)
    hdr = read_at(path, 0, 0x440)
    return dict(hdr=hdr, gid=hdr[:6].decode('ascii'), fst_off=fst_off, fst=bytes(fst),
                by_path={p: (o, s) for i, p, o, s in ents}, first=min(o for i, p, o, s in ents))


def main():
    ap = argparse.ArgumentParser()
    for k in ('orig', 'build', 'out', 'version', 'bin'):
        ap.add_argument('--' + k, required=True)
    ap.add_argument('--title', default='기프트피아')
    ap.add_argument('--result', default='Giftpia (Korean)')
    ap.add_argument('--readme')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    o, b = disc(a.orig), disc(a.build)
    out = Path(a.out)
    xdelta = str((Path(a.bin) / 'xdelta3.exe').resolve())   # 상대경로 그대로면 Windows에서 실행 파일을 못 찾음

    assert os.path.getsize(a.orig) == DISC_SIZE and os.path.getsize(a.build) == DISC_SIZE
    assert o['fst_off'] == b['fst_off'], 'FST 위치가 다름'
    assert set(o['by_path']) <= set(b['by_path']), '빌드에서 빠진 파일이 있음'
    added = sorted(set(b['by_path']) - set(o['by_path']))
    changed = [p for p, v in o['by_path'].items()
               if v != b['by_path'][p] or read_at(a.orig, *v) != read_at(a.build, *b['by_path'][p])]
    for p, v in o['by_path'].items():            # 안 바뀐 파일은 원래 자리 그대로여야 패처가 그대로 복사할 수 있음
        if p not in changed:
            assert v == b['by_path'][p], p
    # 앞부분(첫 원본 파일 전): 헤더 0x420~0x42F 와 FST 자리 말고는 원본과 같아야 함
    first = o['first']
    ho, hb = bytearray(read_at(a.orig, 0, first)), bytearray(read_at(a.build, 0, first))
    fo, fl = b['fst_off'], len(b['fst'])
    ho[0x420:0x430] = hb[0x420:0x430]; ho[fo:fo + fl] = hb[fo:fo + fl]
    # 빌드 파일이 앞부분(빈 영역)에 놓인 곳은 비교에서 뺀다
    for p, (bo, bs) in b['by_path'].items():
        if bo < first:
            ho[bo:min(bo + bs, first)] = hb[bo:min(bo + bs, first)]
    assert ho == hb, '앞부분 차이가 헤더·FST·옮긴 파일 말고도 있음'

    if out.exists():
        shutil.rmtree(out)
    (out / 'data').mkdir(parents=True)
    tmp = Path(tempfile.mkdtemp())
    lines = []
    items = [('fst', 'FST', o['fst'], b['fst'], fo)]
    items += [('raw', p, read_at(a.orig, *o['by_path'][p]), read_at(a.build, *b['by_path'][p]), b['by_path'][p][0])
              for p in sorted(changed, key=lambda q: b['by_path'][q][0])]
    items += [('new', p, b'', read_at(a.build, *b['by_path'][p]), b['by_path'][p][0]) for p in added]
    for i, (mode, p, A, B, pos) in enumerate(items):
        (tmp / 'a').write_bytes(A); (tmp / 'b').write_bytes(B)
        patch = f'{i:03d}.xdelta'
        # -A= : 헤더에 파일 경로(PC 사용자 이름 포함)를 적지 않음. -B : 큰 파일(giftpia.dat)도 원본 전체를 찾을 수 있게
        cmd = [xdelta, '-e', '-f', '-9', '-S', 'djw', '-A=', '-B', str(1 << 28)]
        if mode != 'new':
            cmd += ['-s', str(tmp / 'a')]
        subprocess.run(cmd + [str(tmp / 'b'), str(out / 'data' / patch)], check=True)
        lines.append('\t'.join((mode, patch, p, md5(A) if mode != 'new' else '-', md5(B), str(pos))))
        print(f'  {mode} {p}: {len(B):,} → 차분 {(out / "data" / patch).stat().st_size:,}')
    shutil.rmtree(tmp)
    (out / 'data' / 'manifest.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    h = hashlib.md5()
    with open(a.build, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 24), b''):
            h.update(chunk)
    (out / 'data' / 'config.txt').write_text(
        f'id={o["gid"]}\nrev={o["hdr"][7]}\ntitle={a.title}\nversion={a.version}\nresult={a.result}\n'
        f'disc_size={DISC_SIZE}\nfst_md5={md5(o["fst"])}\nfirst={first}\nhdr420={b["hdr"][0x420:0x430].hex()}\n'
        f'result_md5={h.hexdigest()}\n', encoding='utf-8')

    tpl = HERE.parent / 'patcher'
    shutil.copy2(tpl / 'patch.ps1', out / 'patch.ps1')
    shutil.copy2(tpl / '패치하기.bat', out / '패치하기.bat')
    if a.readme:
        shutil.copy2(a.readme, out / 'README.txt')
    (out / 'bin').mkdir()
    for f in BIN_FILES:
        shutil.copy2(Path(a.bin) / f, out / 'bin' / f)

    zpath = out.parent / (out.name + '.zip')   # with_suffix 는 'v0.1' 의 '.1' 을 확장자로 봄
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for dp, _, fs in os.walk(out):
            for f in sorted(fs):
                q = Path(dp) / f
                z.write(q, Path(out.name) / q.relative_to(out))
    size = sum(f.stat().st_size for f in (out / 'data').iterdir())
    print(f'FST + 바뀐 파일 {len(changed)}개 + 추가 {len(added)}개, 차분 합계 {size / 1e6:.2f} MB, zip {zpath.stat().st_size / 1e6:.2f} MB')
    print(f'결과 MD5(정본 기준) {h.hexdigest()}')
    print(f'패처: {out}')


if __name__ == '__main__':
    main()
