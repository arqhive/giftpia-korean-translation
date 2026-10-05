"""빠진 실행 파일 문구 → translation/dol_texts2.json (id D2001~, 자리 = 다음 0 아닌 바이트까지, 데이터 포인터 참조 수)."""
import json
import re
import sys

sys.path.insert(0, 'tools')
from dol import Dol

D = Dol('extract/main.dol')
M = json.load(open('work/dol_missing.json', encoding='utf-8'))
KANA = re.compile(r'[぀-ヿ一-鿿ｦ-ﾟ]')
out = []
for m in M:
    t = m['jp']
    if not m['refs'] or not KANA.search(t):
        continue
    if m['addr'] in ('8016DA58', '80189D68', '801ABE1C', '801ABEAC'):     # 이름 입력 글자표(원문 유지)·숫자 데이터·프랑스어 오류문
        continue
    a = int(m['addr'], 16); n = m['len'] + 1
    while D.read(a + n, 1) == b'\0':
        n += 1
    out.append({'id': 'D%04d' % (2001 + len(out)), 'addr': m['addr'], 'len': m['len'], 'cap': n, 'code_refs': 0,
                'ptr_refs': m['refs'], 'suspect': False, 'jp': t, 'ko': ''})
json.dump(out, open('translation/dol_texts2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(out))
for x in out:
    print(x['id'], x['cap'], x['jp'].replace('\n', '⏎'))
