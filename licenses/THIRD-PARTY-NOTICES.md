# 라이선스와 외부 자료 고지

현재 한글 패치 빌드는 프로젝트의 빌드 코드, HANME 자모 폰트, FreeTOWNSOS 부팅 환경과 원본 게임 자료를 함께 사용한다. 각 항목의 적용 범위와 고지를 아래에 정리한다. 빌드 사용법은 [한글 빌드 안내](../doc/Alltynex-Korean-Build.md)를 참조한다.

## 적용 범위

| 구분 | 현재 빌드에서의 사용 | 라이선스·고지 |
| --- | --- | --- |
| 프로젝트 코드·문서 | 빌드 도구, 한글 출력 후크, 자체 작성 분석·사용 안내 | licenses/LICENSE (MIT) |
| HANME 자모 폰트 | 원형 자모를 24×24로 변환하고 게임에서 음절을 합성 | SIL Open Font License 1.1 |
| FreeTOWNSOS | 생성 ISO의 부팅·BIOS·DOS 확장 환경 | 상위 라이선스와 ORICON·Free386 고지 |
| xdelta3 | 원본 ZIP에서 완성 ISO를 복원하는 배포 패치 생성 | 공식 v3.2.1의 Apache License 2.0 |
| liblzma·BLAKE3 | 공식 xdelta3 실행 파일에 정적 링크된 구성 요소 | 아래 xdelta3 항목의 상위 라이선스 고지 |
| 원본 게임 자료·원문 | 게임 실행 이미지·그래픽·음악·대조 문자열 | 원래 권리자의 권리 유지 |

## 프로젝트 코드와 문서

프로젝트에서 작성한 빌드 도구, 출력 후크와 자체 작성 문서에는 [MIT LICENSE](LICENSE)를 적용한다. 이 라이선스는 외부 소프트웨어·폰트와 원본 게임 자료·원문에 적용하지 않는다.

## HANME 폰트

원형 `font/han_hanme.fnt`는 16×16 자모 360개다. 빌드가 이를 메모리에서 24×24로 변환하여 생성 ISO의 게임 디렉터리에 `HANME.FNT`로 넣는다. 게임은 이 파일을 적재한 뒤 초성·중성·종성 비트맵을 합성해 본문을 출력한다.

- 저작권 고지: Copyright (c) 2025 Dongsu Jang <iolo@kakao.com>.
- 라이선스: SIL Open Font License 1.1.
- 전체 고지: [LICENSE-OFL.txt](LICENSE-OFL.txt).
- 원본 저장소: [iolo/8x4x4-fonts](https://github.com/iolo/8x4x4-fonts/tree/main/src).

24×24로 변환한 폰트에도 OFL 조건을 적용한다. 원형 또는 변환 폰트를 함께 제공할 때 폰트 저작권·라이선스 고지를 보존한다.

## FreeTOWNSOS

빌드는 준비된 부팅 입력에서 운영체제 파일과 TESTS 자료를 가져온다. AUTOEXEC의 시작 명령을 바꾸고 KRSTART 배치를 추가하여 게임을 자동 실행한다. 그 밖의 OS 바이너리와 TESTS 자료는 보존한다. 현재 빌드는 FreeTOWNSOS 소스를 다시 컴파일하지 않는다.

- 상위 프로젝트: [captainys/FreeTOWNSOS](https://github.com/captainys/FreeTOWNSOS).
- 참조 소스 기준: commit `b72f4066b20b08d78fbfaf876e4f629c77cbb56f`.
- 전체 상위 고지: [FreeTOWNSOS LICENSE](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/LICENSE.md).
- 로컬 고지 사본: [FreeTOWNSOS-LICENSE.md](FreeTOWNSOS-LICENSE.md).

상위 고지의 기본 조건은 BSD 3-Clause 형식이다. ORICON은 개발자들의 허락으로 포함되었다는 별도 설명이 있고, Free386은 Public Domain Software로 명시되어 있다. 이 설명을 프로젝트 MIT 라이선스로 대체하지 않는다. OS 바이너리가 포함된 결과물을 제공할 때 상위 고지를 함께 제공한다.

## xdelta3

xdelta 생성은 [jmacd/xdelta](https://github.com/jmacd/xdelta)의 외부 실행 도구를 별도 프로세스로 호출한다. `tools/xdelta3.exe`는 공식 v3.2.1 Windows x64 배포본이다. 상위 설명은 [tools/xdelta3-README.md](../tools/xdelta3-README.md), 라이선스 원문은 [xdelta3-LICENSE.txt](xdelta3-LICENSE.txt)에 보존한다. [원본 소스와 라이선스](https://github.com/jmacd/xdelta/tree/v3.2.1/xdelta3)를 참조할 수 있다. 이 실행 파일은 생성 ISO에 넣지 않는다. 직접 설치한 다른 버전을 사용할 때는 그 버전의 상위 고지를 따른다.

- 상위 저작권 고지: Copyright 2016 Joshua MacDonald.
- 라이선스: Apache License, Version 2.0. 프로젝트의 MIT 라이선스는 이 실행 파일에 적용하지 않는다.
- 배포본: [xdelta3-3.2.1-windows-x86_64.zip](https://github.com/jmacd/xdelta/releases/download/v3.2.1/xdelta3-3.2.1-windows-x86_64.zip). 실행 파일을 수정하지 않고 추출했다.
- 배포 ZIP SHA-256: `8754db3a662156d0c13dcef140d94b36b2a5aadd6aa6b4f65bf30ff036724924`.

공식 배포본에는 liblzma와 BLAKE3가 정적으로 링크되어 있다. [v3.2.1 빌드 설정](https://github.com/jmacd/xdelta/blob/v3.2.1/xdelta3/CMakeLists.txt)의 기준 버전과 고지는 다음과 같다.

| 구성 요소 | 상위 버전·출처 | 라이선스 원문 |
| --- | --- | --- |
| liblzma | [XZ Utils v5.8.3](https://github.com/tukaani-project/xz/tree/v5.8.3), 상위 개발자들의 저작권 유지 | 0BSD: [라이선스](xdelta3-liblzma-LICENSE.txt), [적용 범위 설명](xdelta3-liblzma-COPYING.txt) |
| BLAKE3 | [BLAKE3 1.8.5](https://github.com/BLAKE3-team/BLAKE3/tree/1.8.5), 상위 개발자들의 저작권 유지 | 상위 선택 라이선스 원문: [Apache 2.0](xdelta3-BLAKE3-LICENSE.txt), [Apache 2.0 with LLVM Exceptions](xdelta3-BLAKE3-LICENSE-A2LLVM.txt), [CC0](xdelta3-BLAKE3-LICENSE-CC0.txt) |

실행 파일을 함께 배포할 때는 위 라이선스 원문과 상위 저작권·출처 고지도 함께 보존한다.

## 원본 게임 자료와 문자열

원본 `alltynex_fmtowns.zip`는 개발자가 [SITER SKAIN의 과거 작품 배포 페이지](https://www.siterskain.com/artifact/)에서 무료로 배포하고 있다. 해당 페이지의 **ALLTYNEX for FM TOWNS** 링크로 받을 수 있다.

게임 실행 이미지, 그래픽·맵·음악 자료, 일본 원문과 영문 패치 원문은 프로젝트 자체 코드 라이선스의 적용 대상이 아니다. 번역 CSV나 분석 문서에 원문이 포함되어 있어도 원본 자료의 권리는 해당 권리자에게 남는다.
