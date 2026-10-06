# 기프트피아 (GC) 한글 패치

*ギフトピア* (게임큐브, 일본판 `GGFJ01`) 비공식 한국어 팬 패치입니다.

**제작: arqhive** · **최신 버전: [v0.1](../../releases/tag/v0.1)**

- 대사 15,197줄과 메뉴·스테이터스·도움말·소원 목록 등 실행 파일 문구 1,127개를 한글화했습니다.
- 그림 글씨 101장(디스크 안 258곳), 3D 글자 모델 2개, 오프닝 영상 자막 12장을 한글화했습니다.
- 한글 글꼴은 엄마까투리체이며, 게임 본래 글자와 같은 크기·4단계 농도로 그렸습니다.
- **원본과 같은 1.4GB 디스크 크기를 유지합니다.**

> 이 저장소에는 **게임 데이터(롬·디스크 이미지, 추출한 원문 대사, 그래픽, 스크린샷)가 들어 있지 않습니다.**
> 패치를 만들거나 적용하려면 본인이 소유한 게임에서 직접 덤프한 원본이 필요합니다.

## 사용자용: 패치 적용

### 준비물

- 일본판(`GGFJ01`) 이미지. ISO·GCM은 그대로, CISO·WIA·WDF·GCZ는 패처가 ISO로 바꿔서 적용합니다.
- Windows 10 이상(기본 PowerShell 사용). 다른 도구는 필요 없습니다.

| 원본 형식 | 결과 | 비고 |
|---|---|---|
| ISO, GCM | ISO | |
| CISO, WIA, WDF, GCZ | ISO | 동봉한 wit으로 ISO로 바꾼 뒤 적용 |
| RVZ | 지원 안 함 | Dolphin에서 ISO로 변환한 뒤 적용 |
| NKit | 지원 안 함 | NKit 도구로 원래 ISO로 되돌린 뒤 적용 |

패처가 게임 파일 하나하나를 원본과 비교하므로, 덤프 방식에 따라 ISO 전체 MD5가 달라도 게임 파일만 같으면 적용됩니다. 이미 한글 패치를 적용한 이미지에는 적용되지 않습니다.

### 적용 방법

1. [배포 페이지](../../releases/tag/v0.1)에서 `GGFJ_KPatch_v0.1.zip`을 받아 풉니다.
2. 풀린 폴더에 원본 이미지를 넣고 `패치하기.bat`을 더블클릭합니다. 원본 파일을 `패치하기.bat` 위에 끌어다 놓아도 됩니다.
3. 원본과 같은 폴더에 `Giftpia (Korean).iso`가 생깁니다. 원본 파일은 그대로 남습니다.

결과 파일 이름을 바꾸려면 두 번째 인자로 지정합니다. 오류 메시지와 자세한 방법은 ZIP에 들어 있는 `README.txt`를 참고하세요.

```bash
패치하기.bat "Giftpia (Japan).iso" "D:/Games/Giftpia (Korean).iso"
```

### 원본 확인값

Redump 정본 ISO의 값입니다. 다른 덤프도 게임 파일이 같으면 적용됩니다. 정본에 적용하면 패처가 마지막에 「정본(Redump) 원본 기준 결과와 일치합니다」를 출력합니다.

| 항목 | 원본 일본판 |
|---|---|
| 크기 | 1,459,978,240 바이트 |
| CRC32 | `C06AB1AF` |
| MD5 | `ac8f05741e690cc3873a7189bb08d989` |
| SHA-1 | `52d0610ae78a2a5bc4bdd79cf3bfcd97c7f0a638` |

원본 파일명 예: `Giftpia (Japan).iso`

### 실행 환경

- **확인함**: Dolphin, Wii U.

## 개발자용: 직접 빌드

### 요구 사항

- Python 3.11 이상과 numpy, Pillow, fontTools, scipy, capstone(`requirements.txt`).
- 일본판 ISO(`Giftpia (Japan).iso`)를 저장소 루트에.
- Dolphin의 `Sys/GC/font_japanese.bin`을 `extract/font_japanese.bin`에(한글 ROM 폰트의 칸 구조만 빌리고 글자는 전부 새로 그림). 다른 곳에 있으면 환경 변수 `GIFTPIA_BASE_FONT`로 지정합니다.
- 글꼴(`tools/fonts/`): 엄마까투리체(`AndongKaturi.ttf`), 나눔스퀘어라운드 B. 그림 글씨를 다시 만들 때는 아래 「크레딧」의 글꼴과 LaMa 인페인팅이 필요합니다.
- 배포용 패처를 만들 때만: xdelta3 3.1.0과 wit v3.05a(cygwin64판)를 `tools/bin/`에. 릴리즈 ZIP의 `bin/`에 든 것을 그대로 써도 됩니다.

### 빌드

```bash
python tools/dump.py "Giftpia (Japan).iso" extract       # ISO 풀기(main.dol 포함)
python tools/u8.py extract extract/giftpia.dat extract/dat   # 게임 데이터 아카이브(U8) 풀기
python tools/extract_text.py                             # 대사 원문 → translation/evt_texts.json
python tools/extract_dol.py                              # 실행 파일 문구 → translation/dol_texts.json
python tools/dol_missing.py && python tools/dol_missing_final.py   # 1차에서 빠진 문구 → translation/dol_texts2.json
python tools/model_ko.py && python tools/movie_ko.py build         # 3D 글자 모델·오프닝 영상 자막
python tools/build.py build/Giftpia_KO.iso v0.1          # 대사·폰트·실행 파일·그림 → ISO
python tools/make_patcher.py --orig "Giftpia (Japan).iso" --build build/Giftpia_KO.iso \
    --out release/Giftpia-KO-v0.1 --version 0.1 --bin tools/bin --readme patcher/README.txt
```

- 대사는 맵마다 하나인 `evt/*.evt` 바이트코드 안에 들어 있습니다. 파일 전체를 재배치하는 대신, 원래 대사 자리를 「파일 끝의 한글 대사로 건너뛰는 명령」으로 바꾸는 우회 방식으로 넣습니다(`tools/evt_patch.py`).
- 한자·한글은 본체 IPL ROM 폰트로 그려집니다. 실행 파일이 디스크의 `kofont.szs`를 읽도록 고치고(`tools/dol_patch.py`), 한글을 SJIS 한자 칸에 배정합니다.
- 히라가나·가타카나 1바이트 칸(그래픽 폰트 `font.tpl`) 137칸에는 번역문에서 가장 많이 쓰인 한글 음절을 넣어 대사 크기를 줄였습니다(`translation/onebyte_final.txt`).
- 원래 자리보다 긴 실행 파일 문구는 DOL에 새 섹션을 붙여 옮기고, 그 문구를 가리키는 데이터 포인터와 아레나 시작 주소를 고칩니다. 커진 DOL과 파일은 디스크 앞쪽 빈 영역에 놓습니다.
- 그림 확정본(`work/gfx/final/`), 3D 모델, 영상은 게임 데이터로 만든 것이라 저장소에 넣지 않았습니다. 그림은 `tools/gfx_g*.py`, 목록은 `translation/graphics_list.csv`, 위치 정보는 `work/gfx_survey/index.csv`에 있습니다.
- 검증: `python tools/verify_build.py <ISO> build/<버전 폴더>`, `python tools/verify_dol2.py build/<버전 폴더>`.

### 번역 수정

- 대사: `translation/evt_ko.json`(항목 id와 한국어). `python tools/tr.py next`·`apply`로 검사하며 반영합니다.
- 실행 파일 문구: `translation/dol_ko.json`, 1차에서 빠졌던 문구는 `translation/dol_ko2.json`. 도구는 `tools/dol_tr.py`.
- 용어·표기: [`translation/glossary.md`](translation/glossary.md), 창 크기: [`docs/windows.md`](docs/windows.md), 검수: [`docs/review.md`](docs/review.md).
- 일본어 원문은 게임 데이터라 넣지 않았습니다. 원문이 필요한 도구를 쓰려면 직접 가진 ISO에서 위 추출 명령으로 다시 뽑으세요.

### 폴더 구조

```
tools/          추출·역어셈블·번역 검사·폰트·그림·영상·모델·빌드·패처 도구
translation/    번역 JSON(id와 한국어), 용어집, 그림 목록, 영상 자막
docs/           분석·추출·창 크기·검수 보고서
patcher/        사용자용 패처(patch.ps1, 패치하기.bat)와 설명서 README.txt
work/gfx_survey/index.csv   그림 위치 목록
release/        (git 제외) make_patcher.py 가 만드는 배포 폴더·ZIP
extract/ build/ (git 제외) 원본 추출본·빌드 결과
```

## 변경 내역

전체 내역은 [`CHANGELOG.md`](CHANGELOG.md)에 있습니다.

## 크레딧·라이선스

- 이 저장소의 도구 코드, 한국어 번역문, 문서: [MIT License](LICENSE) (© 2026 arqhive).
- 글꼴(글자 그림으로만 들어가며 글꼴 파일은 배포하지 않음)
  - 대사·메뉴·영상 자막·3D 글자: 엄마까투리체 (안동시), 나눔스퀘어라운드 (네이버, OFL)
  - 그림 글씨: 블랙한산스·도현·주아 (OFL), 갈무리 (OFL), 송명 (OFL), 나눔손글씨 펜 (네이버, OFL), 연천 허목체 (연천군), 티머니 둥근바람 (티머니)

## 면책

비공식 팬 번역이며 Nintendo, skip Ltd.와 관련이 없습니다. 「기프트피아」 관련 상표·저작권은 각 권리자에게 있습니다.
패치를 적용한 게임 파일의 배포를 금지합니다.
