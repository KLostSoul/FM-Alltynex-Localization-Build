# Alltynex 소스 분석

- 통합일: 2026-10-05 (Asia/Seoul)
- 분석 대상: 일본 원판 게임 파일, 영문 패치 EXP, 초기 FreeTOWNSOS 변환 ISO, 로컬 FreeTOWNSOS BIOS/Free386 소스.
- 근거 범위: 파일 정적 분석과 사용자가 제공한 Tsugaru 디버거 관찰. 게임 실행 테스트는 사용자가 수행했다.
- 주소: 별도 표기가 없으면 P3를 해제한 **runtime 이미지 오프셋**이다. `raw EXP`는 압축 파일 바이트 오프셋이다. 두 주소 공간은 위치별 P3 literal 매핑으로 연결하며 상수 차이를 전체 파일에 적용하지 않는다.

## 분석의 기준

영문 패치는 일본 ZIP의96개 게임 파일 중 EXP 하나의 문자열 데이터만 변경했다. EGB 문장은 `0x33C94`→AH=60h→시스템 폰트 ROM, 게임 UI는 `0x26C9C`→SPR 속성/위치 호출, 배경은 M 인덱스→32K 타일→EGB AH=25h다. ENE 이벤트와 객체 descriptor는 별도 스테이지 처리기·상태 점프표를 사용한다.

이 문서는 원본의 실행·리소스·저장·음원·화면 출력 구조를 주제별로 통합한 기준 문서다. FNT 조합 토큰·후크·ISO 생성·성공 결과와 최종 메모리 배치는 [Alltynex 한글 빌드](Alltynex-Korean-Build.md)에 기록한다.

## 읽는 순서

1. 분석 자료·입력 동일성·부팅 계보
2. P3 실행 이미지·초기화·EUP/FMB/PMB 음원
3. 그래픽·맵 파일 적재 및 소비 범위
4. 파일 읽기·CFGDAT·옵션·플레이어 상태
5. EGB/SPR 문자 규약 및 EGB 호출 후보/확정 수량
6. 장면·데모·ENE·객체 descriptor와 raw attribute
7. 일본 원문·영문 패치의 상세 문자열 대조

## 분석 자료와 신뢰 범위

일본 원판 게임 자료, 영문 패치의 실행 이미지, 초기 FreeTOWNSOS 변환본과 FreeTOWNSOS BIOS/Free386 소스를 대조했다. 다음 절은 분석 결과와 원본 구조를 기록하며 로컬 보관 파일의 이름이나 경로를 자료 안내로 사용하지 않는다.

FreeTOWNSOS 참조 소스는 commit `b72f4066b20b08d78fbfaf876e4f629c77cbb56f`, TOWNSROM은 `7c0aa28be7a75d632564dc356cc5672cc16e7f20`을 기준으로 했다.

### `ALLTYNEX.EXE` 설치 컨테이너와 실행용 EXP는 별개

FreeTOWNSOS 이미지의 `ALLTYNEX.EXE`는 바깥쪽이 MZ 실행 파일이고, 파일 오프셋 `0x664`부터 96개의 `-lh5-` LHA 항목이 이어진다. 각 항목 헤더의 이름, 원본 길이, LHA CRC-16을 일본 원판 자료의 같은 이름 파일과 대조했을 때 96개 모두 일치했다. 특히 컨테이너 안에도 일본 원판 `ALLTYNEX.EXP` 항목이 들어 있다. 즉 EXE 안의 설치 자료는 일본 원판 ZIP 계보이며, 별도 파일인 `/ALLTYNEX/ALLTYNEX.EXP`가 공개 영문 패치본이다. FreeTOWNSOS 실행 배치는 후자를 `FREE386`으로 시작한다. 설치 컨테이너 내부의 EXP와 ISO 디렉터리에서 실행하는 EXP를 같은 파일로 취급하면 안 된다.

이 대조는 LHA 헤더 CRC와 길이에 기반한다. LHA 페이로드를 전부 풀어 바이트 단위 SHA 해시를 대조한 것은 아니다. 이름·크기·CRC 검증은 컨테이너 안에 일본 원판의 동일한 96개 릴리스 파일이 수록됐다는 것을 강하게 뒷받침한다.

### 세 입력의 정확한 계보와 ISO 파일 계층

여기서 “원판”은 일본어 게임 자료 96개를 뜻한다. 영문 패치본은 그 자료의 문자열을 바꾼 판본이고, 초기 FreeTOWNSOS 변환본은 영문 패치본의 게임 자료를 유지한 채 부팅 환경을 바꾼 결과다.

| 입력 | ISO/ZIP에서 직접 센 일반 파일 | 배치 |
|---|---:|---|
| 일본어 원판 ZIP | 96 | `alltynex_fmtowns/` 디렉터리 |
| 영문 패치 ISO | 130 | 루트 103개와 하위 5개 디렉터리 27개 (`HCOPY` 5, `SYS` 4, `SYSINIT` 5, `TBIOS` 10, `T_TOOL` 3) |
| FreeTOWNSOS ISO9660-fixed | 145 | 루트 17개, `/ALLTYNEX` 98개, `/TESTS` 30개 |

일본어 ZIP의 파일명 96개가 영문 ISO 루트에도 전부 있다. 그 96개를 내용 대조하면 95개는 바이트 단위로 동일하고, 유일한 차이는 같은 크기(267,304 bytes)의 `ALLTYNEX.EXP`다. 일본판 EXP MD5는 `2FBAD7774E13CDD6B662BD7A3C814EAA`, 영문 패치 EXP MD5는 `B192EA9EE7EE2912B95877312602208A`다. 영문 ISO 루트에서 ZIP과 이름이 겹치지 않는 파일은 `ALLTYNEX.EXE`, `AUTOEXEC.BAT`, `CFGDAT.SAV`, `CONFIG.SYS`, `IO.SYS`, `RUN386.EXE`, `TOWNS.SYS` 일곱 개다.

FreeTOWNSOS 변환본의 `/ALLTYNEX` 98개는 영문 ISO 루트의 98개 파일과 모두 내용이 같다. 변환 때 기존 영문 ISO에서 빠진 것은 `AUTOEXEC.BAT`, `CONFIG.SYS`, `IO.SYS`, `RUN386.EXE`, `TOWNS.SYS` 다섯 파일이고, 그 자리는 FreeTOWNSOS 부팅 파일로 대체됐다. `ALLTYNEX.EXE`와 `CFGDAT.SAV`는 게임 디렉터리에 남아 있으며 양쪽 MD5도 각각 `996AA4F71DDAD7684321B093C820EB33`, `21E852BD20B9563115138D847D7CCF39`로 동일하다. `/ALLTYNEX/ALLTYNEX.EXP` 역시 영문 패치 기준본과 크기·MD5가 같다. 즉 FreeTOWNSOS 이미지의 게임 파일은 일본 원판 ZIP에서 새로 복사한 것이 아니라, 사용자가 지적한 대로 영문 패치 ISO를 변환한 결과다.

### 실행 이미지 대조 결과

일본 원판 실행 이미지와 영문 패치 실행 이미지를 구분하여 대조했다. 초기 FreeTOWNSOS 변환본의 게임 실행 이미지는 영문 패치본과 바이트가 같았다. 원판 자료와 영문 패치의 차이를 운영체제 변환 과정의 변경으로 취급하지 않는다.

| 그래픽 파일 | 크기 | 영문·FreeTOWNSOS 공통 SHA-256 |
|---|---:|---|
| `ALLTY_1.PAT` | 32,768 bytes | `6EABD45FBC6F8792F759B42D914BCA4F05F751E198CDED4852BDCDD38EDE6E86` |
| `ALLTY_2.PAT` | 32,768 bytes | `BE843F69FA681B62536A97B91307B0C18C19218EAD88849A4308CA6779B9EFE9` |
| `ALLTY_P.PAT` | 32,768 bytes | `698CCADF86FF3B6457527F0D7CF9796D7A8DF3ACA51FE69114F7E352A981B0A8` |


## 실행 구조

FreeTOWNSOS용 ISO의 실제 배치와 부팅 스크립트에서 확인한 흐름:

1. CONFIG.SYS가 REPLACE.SYS, MINVCPI.SYS, FAKENSDD.SYS, TGBIOS.SYS와 RAMDRIVE.SYS를 적재한다. REPLACE.SYS의 매핑은 RUN386.EXE를 R:\FREE386.COM으로 대체한다.
2. AUTOEXEC.BAT가 TGDRV로 CD 드라이브를 설정하고 FREE386.COM을 RAM 드라이브 R:에 복사한다. 이어 PATH, SYSXXXX0를 설정하고 ORICON YAMAND.COM /E:40 /K FORCE31K.COM을 실행한다. ORICON이 새 YAMAND 명령 인터프리터를 띄우므로 그 뒤의 배치 줄은 이어서 실행되지 않는다.
3. 사용자가 확인한 Q:\> 셸에서 RUNALL.BAT을 실행하면 CD \ALLTYNEX 다음 RUN386.EXE -nocrt ALLTYNEX를 호출한다. 이 ISO에서 게임 실행 명령은 ALLTYNEX.EXE가 아니라 ALLTYNEX.EXP를 Free386로 실행한다.
4. ALLTYNEX.EXP가 실행된 뒤 게임 공용 파일 로더가 PAT/DAT/EUP 등 자료를 읽고, 게임은 장면별 EGB 또는 SPR 렌더 경로를 사용한다.

영문 패치 ISO는 게임 파일이 ISO 루트에 놓인 반면, 그 ISO를 바탕으로 만든 FreeTOWNSOS 변환본은 루트에 운영체제 파일과 RUNALL.BAT이 있고 게임 자료를 /ALLTYNEX 아래에 둔다. ALLTYNEX.EXE도 보존되어 있지만 변환본의 배치 파일은 ALLTYNEX.EXP를 지정한다. ALLTYNEX.EXE 내부 동작을 완전히 역공학한 것은 아니므로 세부 책임은 단정하지 않는다.

### FreeTOWNSOS ISO의 ISO9660 주의점

이 프로젝트에서 실제로 발생했던 “파일이 이미지에 있는데 DIR에서 보이지 않는” 문제는 게임 데이터나 운영체제 호환성 문제가 아니었다. ISO9660 디렉터리 레코드가 2,048-byte 섹터 경계를 가로질러 기록되어 경계를 넘은 뒤의 항목을 찾지 못한 것이 원인이었다. 수정 이미지는 디렉터리 레코드를 섹터 안에 배치했고, 사용자는 수정 이미지에서 Alltynex가 정상 실행됨을 확인했다. 현재 ISO 생성 규칙은 [한글 빌드](Alltynex-Korean-Build.md)에 기록한다.

## 게임 파일과 실행 이미지

일본 원판 ZIP과 영문 패치 ISO에는 대응되는 게임 파일 96개가 있다. FreeTOWNSOS용 ISO의 /ALLTYNEX에는 영문 패치본에서 가져온 ALLTYNEX.EXE 598,678 bytes, ALLTYNEX.EXP 267,304 bytes와 게임 리소스가 들어 있다.

### ALLTYNEX.EXP의 P3 구조

ALLTYNEX.EXP는 단순한 평면 코드 덩어리가 아니라 P3 형식 헤더 뒤에 압축된 32-bit 실행 이미지가 오는 파일이다. Free386가 이를 메모리에 적재하며, 정적 파일 오프셋과 디버거의 000C: 이미지 기준 주소를 혼동하면 패치 위치가 어긋난다.

| 필드 | 확인값 | 의미 |
|---|---:|---|
| 서명 | P3 01 00 | P3 실행 파일 식별 |
| 파일 길이 | 헤더 +0x06 = 0x41428 | 267,304 bytes |
| +0x0A 필드 | 0x01801236 | 원시 필드값. 의미/검증 역할은 미확정이며 체크섬으로 단정하지 않음 |
| 파일 내 이미지 시작 | +0x26 = 0x200 | 헤더 뒤 이미지 데이터 시작 |
| 압축 이미지 크기 | +0x2A = 0x41228 | 기준 영문판 이미지 페이로드 크기 |
| 최소 데이터 메모리 | +0x56 = 0x27100 | P3 헤더의 메모리 필드 |
| 최대 데이터 메모리 | +0x5A = 0xFFFFFFFF | 헤더 원시값 |
| 로드 오프셋 | +0x5E = 0 | 헤더 원시값 |
| 초기 ESP | +0x62 = 0xF7F00 | 런타임 초기 스택 위치 값 |
| 초기 EIP | +0x68 = 0x34C24 | 압축 해제 이미지 기준 진입 오프셋 |
| 압축 플래그 | +0x72 bit 0 = 1 | 기준 EXP에서는 압축됨 |
| 압축 해제 이미지 크기 | +0x74 = 0xD0E00 | 게임의 런타임 이미지 크기 |

이 값은 기준 EXP와 현재 빌더의 파서에서 일치한다. Free386 적재 구현 전체를 완전히 역공학한 것은 아니다. 한글 빌드의 P3 갱신은 별도 빌드 문서에 정리한다.

**EXP 주소 좌표:** `EXP:file+0x…`는 압축된 P3 파일 자체의 바이트 오프셋이고, `EXP:img+0x…`는 P3를 풀어 얻는 런타임 이미지 오프셋(디버거의 `000C:오프셋`)이다. P3 압축 때문에 두 좌표의 차이는 위치마다 달라진다. 예를 들어 타이틀은 파일 `0x3F32E` → 이미지 `0x3F1FC`, EGB 날짜 레코드는 파일 `0x3E910` → 이미지 `0x3E700`에 있다. 이후 두 표기를 명시해 혼동을 막는다.

### P3 진입점에서 게임 초기화까지

헤더의 +0x68 진입 오프셋 `0x34C24`에서 실제 런타임 바이트는 `EB 56`(짧은 점프)이며 다음 실행 주소는 `0x34C7C`다. 이 영역은 게임 기능보다 High C 런타임 부트스트랩 코드로 식별된다. 실행 이미지 `0x34C26`에는 별도 호출 스텁 `CALL 0x2AA54`가 있고, 뒤이어 EAX를 정리 루틴 `0x36D7C`에 넘긴 다음 DOS `INT 21h`로 돌아가는 코드가 있다. 사용자가 보낸 콜스택도 `0x34C26 → 0x2AA54`를 관찰했다. 따라서 `0x2AA54`는 C 런타임이 호출하는 게임 초기화/진입 함수다. 부트스트랩에서 이 스텁까지 가는 모든 분기와 메모리 초기화를 함수 단위로 완전히 복원한 것은 아니다.

게임 초기화 함수 `0x2AA54`에서 확인한 직접 호출 순서는 `0x33900`, `0x2ED88`, `0x33CBC`, `0x2A784`, `0x3A468`이다. 이때 전역값 `0x3FC20`을 `0x119`로 설정하고, 후속 UI/리소스 초기화 함수를 호출한다. 코드 주소만으로 앞 다섯 함수의 구체적인 업무 이름을 붙이지는 않는다. 이어 `0x33514`에 `(7, 0x3DFDC)`, `(6, 0x3DFE8)`, `(5, 0x3DFF4)` 인자를 넘긴다. 이 주소들은 각각 `AL_OVER.EUP`, `ALERT.EUP`, `NAME.EUP` 문자열이며 `0x33514`는 `0x3F230`의 `"rb"` 모드로 이 파일을 열고 인덱스별 내부 구조를 준비한다. 이후 초기화는 다시 `0x2A944`, `0x2A784`와 SPR 등록 경로로 이어진다. 파일 이름/읽기/인덱스는 직접 확인됐으나 게임 중 어떤 시점에 각 음악을 재생하는지는 별도 추적이 필요하다.

### EUP 파일 적재와 게임 내부 재생 디스패처

초기화와 스테이지 자료표에서 보이는 `0x33514(filename, slot)`은 EUP 전용 적재 함수다. 슬롯 배열은 `0x926F4 + slot × 0x1E4`의 484-byte 레코드다. 함수는 `"rb"`로 파일을 열고 크기를 구해 `0x806` 이하 파일을 거부한다. 음악 파일의 시작 부분에는 `NAME ENTRY`, `MAKE AN ASSAULT ON ENEMY` 같은 트랙명이 저장돼 있다. 적재 함수는 헤더 여러 위치에서 제어 자료를 슬롯의 `+0x1A4`와 `+0x1C4` 배열로 복사하고, 파일의 `0x806` 오프셋 이후 길이(파일 크기 − `0x806`)만큼 동적 버퍼를 할당해 읽는다. 따라서 EUP를 게임 공용 고정 길이 로더 `0x2AA10`으로 읽는 게 아니라 별도 seek/크기/할당 경로로 적재한다.

공용 재생 함수 `0x33730(slot)`은 먼저 내부 서비스 `AH=03h`를 호출해 이전 EUP 스트림을 중지한다. 슬롯의 첫 번째 32-byte 제어 배열(`+0x1A4`)은 내부 서비스 `AH=14h`에 채널별로 1 byte씩, 두 번째 배열(`+0x1C4`)은 `AH=13h`에 전달한다. 이 내부 서비스 테이블 `0x3A714`에서 각각 `0x3ABC8`과 `0x3ABA0`으로 가며, 32개 채널의 전역 보정 배열 `0xCFE20` 및 `0xCFE40`을 설정한다. 슬롯 `+0x10`은 `AH=09h`로 전달되고, `+0`의 EUP 데이터 포인터·`+4`의 길이·`+8`의 재생 옵션은 `AH=02h`로 전달된다. 내부 서비스 점프 테이블은 게임 자체 기능이며 TBIOS SND BIOS의 호출 번호표와 별개다.

서비스 AH=02h의 성공 경로는 EUP 스트림 포인터와 재생 상태를 설정하고 전역 byte [`0xCFD9A`]를 0xFF로 만든다. 서비스 AH=06h는 이 byte를 반환 DX의 DH에 복사하고, 게임 래퍼 0x3A4C4는 DH를 부호 확장해 반환한다. 따라서 호출 결과 -1은 활성 표시, 0은 표시 해제를 뜻한다. 서비스 AH=03h는 활성 스트림을 중지하고 이 표시를 지운다. STAFF.EUP의 종료 경로도 확인했다. EUP 파서 0x3B150은 FE를 특수 이벤트 0x3B1EA로 보내며, 종료/반복 설정 [`0xCFD9D`]가 0이면 대기 종료 byte [`0xCFD9B`]를 세운다. 이 설정은 플레이어 초기화 때 0으로 설정되며 STAFF.EUP 적재 옵션은 여기에 전달되지 않는다. 주기 처리기 0x3B10C는 종료 대기 byte가 있고 6-byte 지연 이벤트 큐 개수 [`0xCFDA4`]가 0이 되면 정지 보조 함수 0x3ACA8를 불러 활성 표시 [`0xCFD9A`]를 지운다. 최종 크레딧의 AH=06h 폴링은 그 뒤 0을 받아 다음 selector로 넘어간다. 이에 따라 STAFF.EUP의 FE 끝 이벤트 → 지연 큐 비움 → 스트림 정지 → 활성 표시 해제 → 크레딧 전환이 정적으로 연결된다. STAFF.EUP에는 파일 절대 오프셋 0x6C70부터 0x6F70 직전까지 6-byte FE FF FF FF FF FF 레코드가 128개 연속한다. 전체 EUP 토큰/타이머 상태 기계와 32쌍 제어 바이트의 파트별 의미는 아직 미확정이다.

#### EUP 헤더가 지정하는 FMB·PMB 보조 자료

`0x33348(filename, slot)`은 `0x33514`의 EUP 적재 뒤 같은 파일 핸들을 사용해 파일 오프셋 `0x6D4`의 14-byte 제어 헤더를 읽고, 이어 `0x6E2`의 8 bytes와 `0x6EA`의 8 bytes를 차례로 읽는다. 이 두 고정 길이 필드는 코드 내 파일명 리터럴이 아니라 각 EUP 안에 든 NUL 종료 stem이다. 로더는 이를 각각 `.fmb`, `.pmb`와 결합해 보조 파일명을 만들고 `0x39480` 및 `0x395C4` 파서에 넘긴다.

일본 원판 자료의 EUP 22 개를 이 두 오프셋에서 직접 읽어 보면 모두 FMB stem `st_2`를 가리킨다. PMB stem은 `satoshi`와 `sat_2` 두 종류다. `NAME.EUP`, `OP_1.EUP`, `STAFF.EUP`는 `sat_2`를, 나머지 19 개 EUP는 `satoshi`를 지정한다. ZIP에 실제로 든 보조 파일은 `ST_2.FMB`(6,152 bytes), `SATOSHI.PMB`(67,828 bytes), `SAT_2.PMB`(64,270 bytes)이며, 모두 이 헤더 참조와 일치한다. 영문판과 FreeTOWNSOS 변환본은 EXP 외 게임 데이터가 동일하므로 같은 관계가 유지된다.

FMB 파서 `0x39480`은 파일의 선두 8 bytes를 읽은 뒤 48-byte 레코드를 최대 128개 읽어 내부 서비스 래퍼 `0x3934C`에 순번과 함께 전달한다. 8 + 128×48 = 6,152 bytes이므로 `ST_2.FMB`의 크기와 정확히 맞는다. 래퍼는 `AH=05h`, `BL=0`(FM 채널), `DH=레코드 순번`, `DS:ESI=레코드 주소`를 SND BIOS에 전달하고, FreeTOWNSOS `SND_INST_WRITE`는 이를 `FMInst[순번]`에 복사한다.

PMB 파서 `0x395C4`는 처음 4,104 bytes(8-byte 선두 필드 + 128-byte 레코드 32 개)를 읽고, 각 레코드를 `0x3934C`에 `BL=0x40`(PCM 채널), `DH=레코드 순번`으로 전달해 `PCMInst[순번]`에 등록한다. 이어 `0x3938C(AH=23h, EDX=0xFFFFFFFF)`로 기존 PCM 음성 목록을 비운 뒤 32-byte 제어 블록을 읽는다. 그 블록의 오프셋 `+12` dword가 뒤따르는 스트림 데이터 길이이며 상한은 65,536 bytes다. 해당 데이터는 32-byte 블록과 함께 `0x3937C(AH=22h)`에 공급되고, 0 반환이 나올 때까지 반복한다. 두 PMB의 총 크기가 서로 다르므로 이 길이 필드는 각 파일의 실제 payload 길이를 구분한다. 이 결과로 FMB/PMB의 참조·로딩·내부 서비스 전달을 확인했다. 개별 48/128-byte 레코드의 음색 파라미터 평가는 악기 인덱스·샘플 선택 연결과 구별한다.
EUP 슬롯은 초기 공통 효과/음악 `AL_OVER.EUP`=7, `ALERT.EUP`=6, `NAME.EUP`=5 와 스테이지 음악·보스 음악 0–4 를 같이 보관한다. 스테이지마다 이름표 호출에서 확인된 매핑은 slot 0=`STAGE_nA.EUP`, slot 1=`STAGE_nB.EUP`, slot 2=각 구역 보스 트랙, 이후 구역은 추가 보스 트랙을 slot 3/4 에도 적재한다. 구체적인 재생 함수 호출의 게임 중 상황 분기는 일부 미확정이다.


#### EUP 헤더 제어 배열과 6-byte 이벤트 스트림

일본 원판 ZIP의 EUP 22개를 비교하면 파일 오프셋 `0x6D4`의 14-byte 제어 블록은 전부 `00 01 02 … 0D`이고, `0x6E2`/`0x6EA`의 두 8-byte 파일 stem만 FMB/PMB 뱅크 선택에 쓰인다. 오프셋 `0x394`의 32-byte 배열은 `00..0F`가 두 번 반복되고, `0x3B4`의 32-byte 배열은 전부 0이다. EUP 로더는 각 배열을 슬롯의 `+0x1A4`/`+0x1C4`로 복사한다. 재생 함수가 첫 배열을 `AH=14h`로 `0xCFE20`에, 둘째 배열을 `AH=13h`로 `0xCFE40`에 채운다.

이 배열의 기능은 바이너리 처리기를 따라 확인했다. `0x3B434`는 이벤트 음량 byte에 부호 있는 `0xCFE20[channel]`을 더하고 범위를 1–127로 제한한다. `0x3B400`은 노트 byte에 부호 있는 `0xCFE40[channel]`을 더한 뒤 12씩 더하거나 빼서 0–127 범위로 되돌린다. 따라서 이 게임의 공통 배열은 모든 곡에서 음량 보정 `0..15`를 채널 번호에 순환 적용하고, 음높이 보정은 0으로 둔다. `0x3B3E4`는 상태 byte의 high nibble을 유지하면서 `0xCFE00[channel]`의 하위 4비트를 low nibble에 합친다. 이 조작으로 EUP 이벤트의 채널 nibble·음량·노트 값을 보정한다. 여기서 말하는 채널 재매핑은 EUP/MIDI 처리기 값이며, FM 악기 슬롯 선택을 뜻하지 않는다.

EUP 데이터는 파일 오프셋 `0x806`부터 고정 6-byte 단위로 처리된다. 내부 스트림 포인터 `0xCFD6C`는 매 기록마다 6 증가하고 끝 경계를 넘으면 스트림 시작 `0xCFD72`로 되돌아간다. 서비스 `AH=02h`는 새 스트림을 시작하기 전 이전 활성 스트림을 중지하므로 곡은 슬롯 8개에 적재할 수 있어도 동일 EUP 플레이어에서 동시에 재생되는 활성 트랙은 하나다. 별도 BIOS 효과음 호출은 이 음악 스트림과 독립적으로 진행한다.

`0x3B150`의 이벤트 분기는 상태 byte family `0x90–0xEF`를 분리한다. 확인된 핸들러는 `0x90` 계열 `0x3B350`, `0xA0` 계열 `0x3B2AC`, `0xB0`/`0xE0` 계열 `0x3B318`, `0xC0`/`0xD0` 계열 `0x3B2E8`이다. 각 이벤트는 위 채널 low nibble 재구성과 함께 6-byte 레코드의 데이터 byte를 소비한다. `0xF0`은 별도 SysEx 처리기 `0x3B4B4`를 쓰며, `0xF2`, `0xF8`, `0xFC`는 각각 재생/시간/채널 보정 보조 상태를 조정한다. `0xFE`는 스트림 끝 처리, `0xFF`와 `0xF7`은 포인터 진행 경로, `0xFD`는 별도 표시 상태 처리다. 파서 스케줄러는 자체 주기 카운터를 사용하지만 카운터 한 단위를 게임 화면 프레임이나 실제 초로 환산할 근거는 확인되지 않았다.


#### EUP 이벤트에서 내부 MIDI 디코더와 FMB/PMB까지

앞의 이벤트 분기 중 `0xC0`는 MIDI Program Change다. 이벤트 채널(`[ESI+1]`)이 32 미만이고 활성 배열 `0xCFDC0[channel]`이 0이 아니면 `0x3B2E8`은 라우팅 byte `0xCFDE0[channel]`을 `BL`로 가져온다. 상태 채널은 `0x3B3E4`에서 `0xCFE00[channel]`에 따라 조정되고, `0x3989C`에 상태 byte와 프로그램 번호(`[ESI+4]`)가 전달된다.

`0x3AE72`의 초기화 코드는 `0xCFDC0[0..31]`을 `0xFF`, `0xCFDE0[0..15]`를 `0xFF`, `0xCFDE0[16..31]`을 `0x01`로 채운다. `0xCFE00`은 0–15를 반복하는 항등 채널표로 시작한다. 일본 원판 EUP 22개의 실제 이벤트 채널은 0–13 및 15다. 0–13 채널은 각 EUP의 14-byte 사용 채널 배열에서 활성 값이 지정되고, 라우팅 byte 초기값 `0xFF`를 사용한다. 채널 15 레코드는 합계 18,344개이며 전부 상태 `0x80`(Note Off)이다. 이 파일들에는 `0xFC` 라우팅 변경 이벤트가 없으므로 게임 데이터가 실행 중 이 기본 경로를 외부 MIDI 경로로 바꾸는 경우도 확인되지 않았다.

`0x3989C`는 라우팅 byte `BL`의 상위 nibble을 검사한다. 상위 nibble이 `0xF`이면 내부 MIDI byte 디코더 `0x3B6F4`로 간다. 제공된 EUP의 0–13 채널은 `0xCFDE0[channel]=0xFF`이므로 실제 음악 이벤트는 이 내부 디코더로 들어간다. 상위 nibble이 0인 경우에만 별도 32-byte 링 큐(채널별 구조체 `0xD0648`부터)를 통해 MIDI 카드 송신 IRQ/포트 경로로 들어간다. 상위 nibble 1은 준비된 콜백 `0xD0018`을 호출하는 별도 분기다. INT 44h의 MIDI 송신 IRQ 설치와 `0xE50` 계열/FMT-401 `0x4A0` 계열 송신 포트는 이 선택 가능한 일반 송신 경로다. INT 45h는 별도 MIDI 타이머 경로다. 둘을 기본 EUP 이벤트 라우팅과 혼동하지 않는다.

#### EUP 재생 스케줄러와 타이머 콜백

재생 파서 `0x3AFA0`의 주소 정렬·명령 경계를 대조한 직접 호출은 INT 45h 처리기 `0x3A0C4`의 타이머 조건부 경로와 TBIOS 사운드 인터럽트의 post-EOI 콜백 `0x3A3E0`에서 확인된다.

EUP 내부 서비스 디스패처 `0x3A6F0`은 `AH`를 인덱스로 `0x3A714` 점프표를 선택한다. `AH=0`은 초기화 `0x3A7EB`, `AH=0x30`은 종료 `0x3A86D`, `AH=0x32`는 전달된 경과량을 `0x3A2B4`에 반영하고, `AH=0x33`은 서비스 펌프 `0x3A3E0`을 실행한다. 초기화는 `0xCFFE0`이 1 인지에 따라 시간원을 나눈다. 1 이 아니면 `0x39AF0`이 TBIOS SNDINT `AH=06h`에 `AL=0` 콜백 `0x3A268`과 `AL=2` 콜백 `0x3A3E0`을 등록한다. FreeTOWNSOS의 `SNDINT_06H_REGISTER_INT_PROC` 구현에서 이 AL 값은 각각 Timer A pre-EOI와 post-EOI 콜백이다. FreeTOWNSOS [SNDINT.C](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tgbios/SNDINT.C)의 INT 4Dh 처리기는 YM Timer A 만료 시 pre-EOI 콜백을 실행하고, PIC EOI 뒤 인터럽트를 허용한 상태에서 post-EOI 콜백을 실행한다. 따라서 기본 경로에서 `0x3A268`은 시간 누산, `0x3A3E0`은 실제 이벤트 처리 작업을 맡는다.

대체 경로인 `0xCFFE0==1`에서는 초기화 함수 `0x39A0F`이 DOS-Extender 인터럽트 벡터 `45h`를 조회·교체해 `0x3A0C4`를 설치하고, 일반 FM-Towns 타이머 포트 `0xE73–0xE77` 또는 FMT-401 의 `0x4A3–0x4A7`을 선택한다. `0x3A0C4`는 인터럽트 원인 레지스터를 읽어 시간 카운터를 보정하고, 승인 조건이 참이며 재진입 가드 `0xD0021`이 비어 있을 때 `0x3AFA0`을 호출한다. INT 44h 설치 루틴 `0x3996F`는 별개이며 MIDI 송신 인터럽트다. FreeTOWNSOS [IODEF.H](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tgbios/IODEF.H)는 `0xE70/0xE71`을 MIDI 송신/수신 인터럽트 마스크, `0xE73–0xE77`을 MIDI 타이머 인터럽트/카운터/제어 포트로 정의한다.

공통 작업자 `0x3AFA0`은 진입 직후 사용자 콜백 `[0xD001C]`을 호출하고 MIDI 인터럽트 큐 상태와 보류 중인 `F8`, `FA/FB/FC` 메시지를 비운다. 그 뒤 누산 예산 `[0xCFDB4]`이 양수인 동안 하나씩 감소시키며 시간 보정기 `0x3B124`를 호출한다. 재생 플래그 `[0xCFD9A]`가 꺼져 있으면 이벤트 파싱을 건너뛴다. 켜져 있으면 보류 음성 해제 `0x3B590`, 6-byte 이벤트 파서 `0x3B150`, 종료 검사 `0x3B10C`를 반복하고, 처리 뒤 사용자 콜백과 제어 메시지 플러시를 다시 수행한다. 즉 타이머 인터럽트 자체가 EUP 레코드를 직접 실행하는 구조가 아니라, 시간 예산을 쌓고 콜백 작업자가 예산만큼 스트림 이벤트를 처리하는 구조다.

`0x3A268`과 대체 시간 경로의 `0x3A1E4`는 Timer A 카운트/위상 잔여값을 이용해 완료된 단위를 `[0xCFDB4]`에 더한다. `0x3B124`는 tempo byte `[0xCFD91]`을 환산표 `0x3AD00`에 넣어 하위 위상 카운터 `[0xCFD8C]`를 누적하고, 임계값에 도달하면 스트림 시계 `[0xCFD88]`을 증가시킨다. 이벤트 파서는 레코드의 시간 필드를 이 시계와 비교한다. 따라서 내부 카운터와 실제 파일 이벤트의 시간 순서는 연결됐지만, 현재 설정·하드웨어별 Timer A 값·게임 메인 루프 반복을 실시간 초 또는 화면 프레임으로 환산한 값은 아직 확정하지 않았다.

내부 디코더의 `0x3B5F0` 초기화는 MIDI 논리 채널 0–5를 TBIOS SND 채널 `BL=0..5`(FM), 논리 채널 6–13을 `BL=0x40..0x47`(PCM)로 잇는 양방향 음성 할당표를 `0xD09E0`/`0xD09F0`에 설정한다. 이벤트 상태의 채널 번호는 기본 `0xCFE00`에서 유지되며, 이 음성표가 이를 실제 SND 채널 코드로 바꾼다. 그러므로 EUP의 MIDI 채널 번호, 채널 재매핑 배열, TBIOS FM/PCM 채널 코드는 서로 다른 단계의 값이다.

C0 처리기 `0x3B820 → 0x3BA20`은 선택된 TBIOS 채널 코드를 `BL`, 프로그램 번호를 `DH`에 넣고 SND BIOS `AH=04h`(악기 변경)를 호출한다. FreeTOWNSOS `SND_INST_CHANGE`는 `BL=0..5`이면 `FMInst[DH]`를 FM 채널에 적용하고, `BL=0x40..0x47`이면 `PCMCh[BL-0x40].instrument=DH`로 설정한다. 따라서 FMB와 PMB는 EUP C0 이벤트가 실제 선택하는 내부 악기 뱅크다. FMB 로더 `0x39480`은 48-byte 레코드 128개를 `AH=05h`, `BL=0`, `DH=인덱스`로 등록하고, PMB 로더 `0x395C4`는 128-byte 악기 레코드 32개를 `BL=0x40`로 등록한다. 같은 SND source의 `SND_INST_WRITE`가 각각 `FMInst[]`와 `PCMInst[]`에 복사하는 것까지 일치한다.

채널별 원판 C0 값도 뱅크와 맞는다. 논리 채널 0–5 는 FMB 인덱스 범위 안의 프로그램 값을 사용하고, 채널 6–13 은 PMB의 0–7 번 범위 값을 사용한다. 22 개 EUP 전체의 고유 프로그램 값은 `00 01 02 03 04 06 07 0C 0D 0F 23 24 3F 40 42 48 49 4A 4F 50 52 54 55 56 57`이다. 원판 EUP 22 개에서 19,343 개의 FM과 11,823 개의 PCM Note On을 프로그램 상태→악기 인덱스까지 따라갔다. PMB는 악기별 노트 분할→soundID→음성 헤더/샘플 payload까지 실제 파일 레코드로 연결했다. 두 집합의 Note On은 모두 velocity가 0 보다 컸다. EUP별 C0 와 실제 악기/음성 사용표는 이 절의 악기·PCM 샘플 표에 기록했다. 이로써 원판 데이터의 프로그램-샘플 선택 경로는 연결됐다. 다만 개별 FM 레코드의 청감상 음색 평가와 샘플 발생을 화면 효과의 ENE/상태에 귀속하는 일은 남아 있다.

나머지 MIDI 이벤트도 내부 디코더에서 TBIOS SND 서비스로 연결된다. Note On은 `0x3B8C8`에서 `AH=01h`(KEY_ON), Note Off는 `0x3B874`에서 `AH=02h`(KEY_OFF), 음량은 `0x3B950`에서 `AH=08h`, 팬은 `0x3B988`에서 `AH=03h`를 호출한다. Program Change 뒤 `0x3BA20`은 `AH=07h`로 pitch를 초기화한다. FreeTOWNSOS `SND.C`의 FM 경로는 `SND_Change_FMInst`에서 YM2612 레지스터를 갱신하고, PCM 경로는 선택된 PMB 인덱스를 PCM 채널 상태에 보관한다. 별도 효과음 호출이 존재한다는 이유로 음악 FMB/PMB 경로를 분리해 해석하면 안 된다.

TBIOS의 `MIDI` BIOS 엔트리는 `HEADER.ASM`에서 `TSUGARU_BREAK`로 표시된 인터페이스다. 다만 게임 EUP 재생이 그 엔트리를 통과한다는 뜻은 아니다. 이 실행 파일은 자체 6-byte EUP 이벤트 파서 → 내부 MIDI 상태 디코더 → SND BIOS FM/PCM 서비스 경로를 가진다. 외부 MIDI 카드 IRQ/포트 경로는 별도 선택지로 남는다.

각 EUP 스트림은 `0x806` 이후 길이가 `6×N+2`이며, 첫 `0xFE` 종료 레코드까지의 인덱스는 다음과 같다. 종료 레코드 뒤의 패딩은 정상적인 종료 경로에서 이벤트로 소비되지 않는다.

| EUP 파일 | 첫 `0xFE` 절대 오프셋 | 스트림 내 레코드 인덱스 |
|---|---:|---:|
| `ALERT.EUP` | `0xBEA` | 166 |
| `AL_OVER.EUP` | `0xCC2` | 202 |
| `BOS_01_A.EUP` | `0x70A0` | 4463 |
| `BOS_02_A.EUP` | `0x47C0` | 2719 |
| `BOS_03_A.EUP` | `0x15E0` | 591 |
| `BOS_03_B.EUP` | `0x7472` | 4626 |
| `BOS_05_A.EUP` | `0x3E30` | 2311 |
| `BOS_05_B.EUP` | `0xE7E` | 276 |
| `BOS_05_C.EUP` | `0x85BE` | 5364 |
| `NAME.EUP` | `0x4DFC` | 2985 |
| `OP_1.EUP` | `0x4436` | 2568 |
| `STAFF.EUP` | `0x6962` | 4154 |
| `STAGE_1A.EUP` | `0x10DC` | 377 |
| `STAGE_1B.EUP` | `0x7DD8` | 5027 |
| `STAGE_2A.EUP` | `0x18EC` | 721 |
| `STAGE_2B.EUP` | `0x7B74` | 4925 |
| `STAGE_3A.EUP` | `0x1814` | 685 |
| `STAGE_3B.EUP` | `0x73B8` | 4595 |
| `STAGE_4A.EUP` | `0x1154` | 397 |
| `STAGE_4B.EUP` | `0xF476` | 10088 |
| `STAGE_5A.EUP` | `0x1E44` | 949 |
| `STAGE_5B.EUP` | `0x8BDC` | 5625 |

`0x3389C`는 예약 재생 전환기다. mode 1 에서 요청 슬롯·enable 값을 보관하고, main loop의 mode 0 호출은 enable 값이 1 이며 `0x3A4C4`가 “현재 활성 스트림 없음”을 반환할 때 보관 슬롯을 `0x33730`에 전달한다. 직접 재생 호출과 별도라서 스테이지 B곡/추가 보스곡의 전환을 상태 번호만으로 임의 추정하지 않고 호출자 주소와 같이 기록한다.

#### PMB 악기표·음성 헤더·파형 경계

FreeTOWNSOS `SND.H`의 `PMB_INSTRUMENT`는 128 bytes다: 이름 8, 미사용 8, 8 개 `uint16 split`, 8 개 `uint32 soundID`, 8 개 8-byte envelope. `SND.C`의 PCM KEY_ON 경로는 첫 `note <= split[i]` 항목을 고르고 해당 soundID와 envelope를 복사한 뒤, 등록된 `PCMSound[]`에서 같은 soundID를 찾는다. 즉 악기 인덱스→음역 구간→파형 ID→개별 voice header의 연결을 바이트 단위로 확인할 수 있다. `soundID=0`인 잔여 split은 실제 파형 참조가 아니다.

두 PMB는 8-byte 접두 뒤 32 개 악기 레코드(4,096 bytes)가 오고, `0x1008`부터 `(32-byte PCM_Voice_Header + totalBytes 파형)` 블록이 이어진다. 헤더 필드는 이름[8], soundID(+8), totalBytes(+0xC), loopStart(+0x10), loopLength(+0x14), sampleFreq(+0x18), signed sampleFreqCorrection(+0x1A), baseNote(+0x1C), padding[3]이다. 파일에서 블록을 순회하면 각각 마지막 byte가 파일 끝과 정확히 맞아 남는 데이터가 없다.

| 뱅크 | 파일 크기 | 실제 voice 블록 수 | 등록 soundID |
|---|---:|---:|---|
| `SATOSHI.PMB` | 67,828 | 16 | `1–16` |
| `SAT_2.PMB` | 64,270 | 13 | `1–5, 7–12, 14, 16` |

실제 길이 필드도 BIOS 소비와 맞는다. `sampleFreq`는 `SND.C`가 `sampleFreq×1000/0x62` Hz로 환산하므로 490/784/980/1960 은 각각 5/8/10/20 kHz 기준이다. 재생 주파수는 여기에 signed 보정과 `baseNote−rootKey` 음정 차이를 반영한다. loop 값이 있는 샘플은 SATOSHI soundID 12 `(162+1440=1602)`, 13 `(537+670=1207)` 및 SAT_2 soundID 4, 5, 9, 10, 11, 12 에서 `loopStart+loopLength==totalBytes`다. SAT_2 soundID 7 은 길이 8192, loopStart 4974, loopLength 0 이라 BIOS 조건상 반복 샘플로 취급되지 않는다.

FreeTOWNSOS `SND_22H_PCM_SOUND_SET`은 header를 등록하고 `(totalBytes+32+255)&~255`만큼 파형 RAM을 예약한다. loopLength가 0 이 아니면 파형을 `min(totalBytes, loopStart+loopLength)`까지 복사하고 32-byte loop-stop 마커를 기록한다. BIOS는 원래 loop header도 보관하며 KEY_ON에서 loopLength와 loopStart를 확인해 재생 시작점을 설정한다. 이로써 음성 헤더의 수치가 파일 경계에 맞는 단순 장식이 아니라 실제 PCM RAM 점유·주파수·반복 범위 계산에 쓰임을 코드와 자료 양쪽에서 확정했다.

SATOSHI.PMB의 비영 악기표는 게임 효과음 레이블을 포함한다(`自機弾撃`, `弾命中！`, `剣を振る`, `1up`, `damage!!`, `変形音`, 폭발 1–3 등). SAT_2.PMB에는 `korus`, `hand`, `BASS`, `STRINGS`, `guitar`, `PIANO` 등의 레이블과 `変形音`, `爆発１`이 있다. 다만 레이블이 있어도 어떤 화면의 어느 이벤트가 해당 인덱스를 호출하는지는 PCM KEY_ON의 실제 게임 호출 인자 전수 연결을 거쳐서만 확정한다.
게임 효과음은 EUP 스트림 플레이어와 별도 경로다. 0x337B0 은 호출 인자로부터 채널, 악기 번호, 팬, 노트, 음량을 받아 최근 이벤트/대기 타이머를 확인한 뒤 BIOS 호출을 순서대로 한다. 먼저 AH=02h KEY_OFF, AH=04h INST_CHANGE, AH=03h PAN_SET, 마지막에 AH=01h KEY_ON을 호출한다. 인자 레지스터 배치는 0x392B0–0x392EC 래퍼에서 확인된다. FreeTOWNSOS HEADER.ASM의 SND 점프 테이블과 SND.C 구현은 이 번호를 각각 KEY_ON, KEY_OFF, PAN_SET, INST_CHANGE로 정의한다. TBIOS 호출은 FS:[0x80]을 통해 이뤄지며 게임 자체 EUP 명령은 0x3A714 의 별도 내부 테이블이다. 0x3387C는 8 개의 음향 대기 카운터를 매회 감소시킨다. 동일/우선순위 판단의 전체 규칙과 논리 채널 ID의 게임상 이름은 호출 인자 전수 대조 전까지 미확정이다.

초기 그래픽 적재 블록 `0x2AB20`–`0x2AB8A`의 인자와 리소스 포인터를 대조했다. `0x2AA10`은 `[filename, buffer, item_size, count]`를 받아 파일을 여는 공용 리더다. `ALLTYNEX.PAL`은 문자열 포인터 `0x3E000`에서 버퍼 `0x4022C`로 `0x2000` bytes 읽는다. `ALLTY_1.PAT`은 `0x3E010`에서 `0x94CE4`로 `0x8000` bytes 읽은 뒤 SPR_DEFINE 래퍼 `0x33CF4`에 AL=0, 시작 슬롯 ECX=0x80, 크기 DH:DL=0x10:0x10을 넘겨 16색 패턴 256개를 등록한다. `ALLTY_2.PAT`은 `0x3E01C`에서 `0x4222C`로 읽고 같은 수를 슬롯 `0x180`부터 등록한다. 이어 `ALLTY_P.PAT`(`0x3E028`)은 같은 `0x94CE4` 임시 버퍼로 읽혀 플레이어 애니메이션 루틴이 패턴을 조회해 재등록한다. `GAJE.PAT`(`0x3E034`)은 `0x9CCE4`로 읽히며 런타임 경로가 블록별 3패턴을 SPR에 재등록한다. 이 두 리소스의 구체적인 그림 의미는 별도 미확정이지만, 실제 소비 경로는 확인됐다.

#### EUP별 프로그램 변경 이벤트

각 셀은 C0 프로그램 번호 순서이며 `—`는 C0가 없음을 뜻한다. 동일 프로그램 재선택은 ×횟수로 표시한다.

| EUP | PMB | FM 채널 0–5 | PCM 채널 6–13 |
|---|---|---|---|
| `ALERT.EUP` | `SATOSHI.PMB` | 0: 4<br>1: 4<br>2: 3<br>5: 15 | 6: 4<br>7: 4 |
| `AL_OVER.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 74<br>3: 36<br>4: 36<br>5: 15 | 6: 0<br>7: 0 |
| `BOS_01_A.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 86<br>3: 86<br>4: 66<br>5: 15 | 6: 0<br>7: 0 |
| `BOS_02_A.EUP` | `SATOSHI.PMB` | 0: 66<br>1: 66<br>2: 13×2,87<br>3: 86,84<br>4: 86,84<br>5: 15 | 6: 0<br>7: 0 |
| `BOS_03_A.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 73<br>3: 82,84<br>4: 82,84<br>5: 15 | 6: 0<br>7: 0 |
| `BOS_03_B.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 73×2,36<br>3: 82×2,36<br>4: 82×2,36<br>5: 15 | 6: 0<br>7: 0 |
| `BOS_05_A.EUP` | `SATOSHI.PMB` | 0: 84<br>1: 84<br>2: 35×3,63,66<br>3: 85×2,63,66<br>4: 85×2,63,66<br>5: 15 | 6: 0<br>7: 0 |
| `BOS_05_B.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 64,85<br>3: 87,85<br>4: 87<br>5: 15,12 | 6: 0<br>7: 0 |
| `BOS_05_C.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 64×2,84,2<br>3: 87,64<br>4: 87<br>5: 15 | 6: 0<br>7: 0 |
| `NAME.EUP` | `SAT_2.PMB` | 0: 84<br>1: 84 | 6: 0<br>7: 0<br>8: 3<br>9: 6<br>10: 6<br>11: 1 |
| `OP_1.EUP` | `SAT_2.PMB` | 0: 2,79<br>1: 2,79<br>2: 84×2,1<br>3: 84<br>4: 84<br>5: 15 | 6: 0<br>7: 0<br>8: 1×2,4×2<br>9: 1×2,4×2<br>10: 3<br>12: 6×2,7<br>13: 6×2,7 |
| `STAFF.EUP` | `SAT_2.PMB` | 0: 63<br>2: 86 | 6: 0<br>7: 0<br>8: 1,6<br>9: 6<br>10: 6<br>11: 4<br>12: 4<br>13: 3 |
| `STAGE_1A.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 2<br>3: 36<br>4: 36<br>5: 15 | 6: 0<br>7: 0 |
| `STAGE_1B.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 2<br>3: 36<br>4: 36<br>5: 15 | 6: 0<br>7: 0 |
| `STAGE_2A.EUP` | `SATOSHI.PMB` | 0: 3<br>1: 3<br>2: 72<br>3: 79<br>4: 79<br>5: 15 | 6: 0<br>7: 0 |
| `STAGE_2B.EUP` | `SATOSHI.PMB` | 0: 3<br>1: 3<br>2: 72<br>3: 79<br>4: 79<br>5: 15 | 6: 0<br>7: 0 |
| `STAGE_3A.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 73<br>3: 36<br>4: 36<br>5: 15 | 6: 0<br>7: 0 |
| `STAGE_3B.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 73<br>3: 36<br>4: 36<br>5: 15 | 6: 0<br>7: 0 |
| `STAGE_4A.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 72<br>3: 72<br>4: 72<br>5: 15 | 6: 0<br>7: 0 |
| `STAGE_4B.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 72×2,66<br>3: 72×3,85×2<br>4: 72×3,85×2<br>5: 15×3,72×2 | 6: 0<br>7: 0 |
| `STAGE_5A.EUP` | `SATOSHI.PMB` | 0: 2×2,80<br>1: 2×2,80<br>2: 73×2,87<br>3: 86,85<br>4: 86,85<br>5: 15 | 6: 0<br>7: 0 |
| `STAGE_5B.EUP` | `SATOSHI.PMB` | 0: 2<br>1: 2<br>2: 73<br>3: 86×2,85×2<br>4: 86×2,85×2<br>5: 15 | 6: 0<br>7: 0 |

#### 실제 선택된 FMB 악기

| ID | FMB 레코드명 | 0x90 Note On | velocity>0 | 음높이 범위 | EUP 파일 |
|---:|---|---:|---:|---:|---|
| 1 | `E.Guit2` | 1 | 1 | 40–40 | `OP_1.EUP` |
| 2 | `E.guit3` | 8003 | 8003 | 45–76 | `AL_OVER.EUP`, `BOS_01_A.EUP`, `BOS_03_A.EUP`, `BOS_03_B.EUP`, `BOS_05_B.EUP`, `BOS_05_C.EUP`, `STAGE_1A.EUP`, `STAGE_1B.EUP`, `STAGE_3A.EUP`, `STAGE_3B.EUP`, `STAGE_4A.EUP`, `STAGE_4B.EUP`, `STAGE_5A.EUP`, `STAGE_5B.EUP` |
| 3 | `E.guit4` | 1157 | 1157 | 45–58 | `ALERT.EUP`, `STAGE_2A.EUP`, `STAGE_2B.EUP` |
| 4 | `E.Guit5` | 8 | 8 | 48–52 | `ALERT.EUP` |
| 12 | `S.Bass1` | 2 | 2 | 28–40 | `BOS_05_B.EUP` |
| 13 | `S.Bass2` | 224 | 224 | 36–43 | `BOS_02_A.EUP` |
| 15 | `SlpBass` | 5095 | 5095 | 36–64 | `ALERT.EUP`, `AL_OVER.EUP`, `BOS_01_A.EUP`, `BOS_02_A.EUP`, `BOS_03_A.EUP`, `BOS_03_B.EUP`, `BOS_05_A.EUP`, `BOS_05_C.EUP`, `OP_1.EUP`, `STAGE_1A.EUP`, `STAGE_1B.EUP`, `STAGE_2A.EUP`, `STAGE_2B.EUP`, `STAGE_3A.EUP`, `STAGE_3B.EUP`, `STAGE_4B.EUP`, `STAGE_5A.EUP`, `STAGE_5B.EUP` |
| 35 | `Piano 5 ` | 191 | 191 | 64–76 | `BOS_05_A.EUP` |
| 36 | `A.PIANO1` | 392 | 392 | 57–74 | `AL_OVER.EUP`, `BOS_03_B.EUP`, `STAGE_1B.EUP`, `STAGE_3A.EUP`, `STAGE_3B.EUP` |
| 63 | `KeyBoar3` | 47 | 47 | 62–72 | `BOS_05_A.EUP`, `STAFF.EUP` |
| 64 | `ANRSYNT1` | 106 | 106 | 60–72 | `BOS_05_C.EUP` |
| 66 | `OKESYNT2` | 853 | 853 | 58–74 | `BOS_01_A.EUP`, `BOS_02_A.EUP`, `BOS_05_A.EUP`, `STAGE_4B.EUP` |
| 72 | `Fantasy` | 663 | 663 | 57–81 | `STAGE_2B.EUP`, `STAGE_4B.EUP` |
| 73 | `Lyricon` | 753 | 753 | 60–83 | `BOS_03_B.EUP`, `STAGE_3A.EUP`, `STAGE_3B.EUP`, `STAGE_5B.EUP` |
| 74 | `Sitar   ` | 8 | 8 | 53–62 | `AL_OVER.EUP` |
| 79 | `Fantasy` | 154 | 154 | 52–70 | `OP_1.EUP`, `STAGE_2A.EUP`, `STAGE_2B.EUP` |
| 80 | `Chorale` | 18 | 18 | 49–53 | `STAGE_5A.EUP` |
| 82 | `BellSing` | 160 | 160 | 60–69 | `BOS_03_B.EUP` |
| 84 | `STRINGS2` | 372 | 372 | 50–82 | `BOS_02_A.EUP`, `BOS_03_A.EUP`, `BOS_05_A.EUP`, `BOS_05_C.EUP`, `NAME.EUP`, `OP_1.EUP` |
| 85 | `ORCH_HIT` | 644 | 644 | 60–72 | `BOS_05_A.EUP`, `BOS_05_B.EUP`, `STAGE_4B.EUP`, `STAGE_5A.EUP`, `STAGE_5B.EUP` |
| 86 | `アー1` | 383 | 383 | 60–74 | `BOS_01_A.EUP`, `BOS_02_A.EUP`, `STAFF.EUP`, `STAGE_5A.EUP`, `STAGE_5B.EUP` |
| 87 | `ア－２` | 109 | 109 | 62–74 | `BOS_02_A.EUP`, `BOS_05_C.EUP`, `STAGE_5A.EUP` |

#### 실제 선택된 PMB 악기와 PCM 음성

`soundID`와 음성 헤더명은 PMB 원문이다. Note On velocity 0도 악기 split/soundID를 조회하므로 전체 0x90 수에 포함한다. `velocity>0` 열은 0이 아닌 세기로 들어온 부분집합이다.

| PMB | 악기 ID | 악기명 | soundID | 음성 헤더명 | Note On | velocity>0 | 실제 음높이 | EUP 파일 |
|---|---:|---|---:|---|---:|---:|---:|---|
| `SATOSHI.PMB` | 0 | `DRUM` | 2 | `バスドラ` | 2808 | 2808 | 24–24 | `AL_OVER.EUP`, `BOS_01_A.EUP`, `BOS_02_A.EUP`, `BOS_03_A.EUP`, `BOS_03_B.EUP`, `BOS_05_A.EUP`, `BOS_05_B.EUP`, `BOS_05_C.EUP`, `STAGE_1A.EUP`, `STAGE_1B.EUP`, `STAGE_2A.EUP`, `STAGE_2B.EUP`, `STAGE_3A.EUP`, `STAGE_3B.EUP`, `STAGE_4A.EUP`, `STAGE_4B.EUP`, `STAGE_5A.EUP`, `STAGE_5B.EUP` |
| `SATOSHI.PMB` | 0 | `DRUM` | 3 | `スネア` | 1144 | 1144 | 36–36 | `AL_OVER.EUP`, `BOS_01_A.EUP`, `BOS_02_A.EUP`, `BOS_03_B.EUP`, `BOS_05_B.EUP`, `BOS_05_C.EUP`, `STAGE_1A.EUP`, `STAGE_1B.EUP`, `STAGE_2A.EUP`, `STAGE_2B.EUP`, `STAGE_3A.EUP`, `STAGE_3B.EUP`, `STAGE_4B.EUP`, `STAGE_5A.EUP`, `STAGE_5B.EUP` |
| `SATOSHI.PMB` | 0 | `DRUM` | 4 | `タム` | 116 | 116 | 57–67 | `BOS_01_A.EUP`, `BOS_05_C.EUP`, `STAGE_1B.EUP`, `STAGE_2B.EUP`, `STAGE_3A.EUP`, `STAGE_3B.EUP`, `STAGE_4B.EUP` |
| `SATOSHI.PMB` | 0 | `DRUM` | 14 | `ｸﾗｯｼｭ` | 3601 | 3601 | 84–96 | `AL_OVER.EUP`, `BOS_01_A.EUP`, `BOS_03_A.EUP`, `BOS_05_A.EUP`, `BOS_05_B.EUP`, `BOS_05_C.EUP`, `STAGE_1A.EUP`, `STAGE_1B.EUP`, `STAGE_2A.EUP`, `STAGE_2B.EUP`, `STAGE_3A.EUP`, `STAGE_3B.EUP`, `STAGE_4A.EUP`, `STAGE_4B.EUP`, `STAGE_5A.EUP`, `STAGE_5B.EUP` |
| `SATOSHI.PMB` | 4 | `AREAT` | 13 | `ﾚ-ｻﾞ-2` | 8 | 8 | 40–48 | `ALERT.EUP` |
| `SAT_2.PMB` | 0 | `DRUM` | 1 | `バスドラ` | 326 | 326 | 24–24 | `NAME.EUP`, `OP_1.EUP`, `STAFF.EUP` |
| `SAT_2.PMB` | 0 | `DRUM` | 2 | `スネア` | 242 | 242 | 36–36 | `NAME.EUP`, `OP_1.EUP`, `STAFF.EUP` |
| `SAT_2.PMB` | 0 | `DRUM` | 3 | `タム` | 56 | 56 | 57–67 | `NAME.EUP`, `OP_1.EUP`, `STAFF.EUP` |
| `SAT_2.PMB` | 0 | `DRUM` | 8 | `ｸﾗｯｼｭ` | 391 | 391 | 84–96 | `NAME.EUP`, `OP_1.EUP`, `STAFF.EUP` |
| `SAT_2.PMB` | 1 | `korus` | 4 | `Chorus` | 217 | 217 | 48–72 | `NAME.EUP`, `OP_1.EUP`, `STAFF.EUP` |
| `SAT_2.PMB` | 3 | `BASS` | 9 | `BASS` | 939 | 939 | 28–50 | `NAME.EUP`, `OP_1.EUP`, `STAFF.EUP` |
| `SAT_2.PMB` | 4 | `STRINGS` | 12 | `STRNG` | 248 | 248 | 59–84 | `OP_1.EUP`, `STAFF.EUP` |
| `SAT_2.PMB` | 6 | `guitar` | 10 | `GUitar` | 1713 | 1713 | 47–72 | `NAME.EUP`, `OP_1.EUP`, `STAFF.EUP` |
| `SAT_2.PMB` | 7 | `PIANO` | 11 | `A_PIANO` | 14 | 14 | 52–59 | `OP_1.EUP` |

#### 사용 악기의 노트 분할

`split[i]`는 상한이다. 해당 상한 이하의 첫 항목에서 `soundID[i]`를 고른다.

##### `SATOSHI.PMB`

| 악기 ID | 레코드명 | 노트 상한 → soundID (음성명) |
|---:|---|---|
| 0 | `DRUM` | 35 → 2 (`バスドラ`); 47 → 3 (`スネア`); 71 → 4 (`タム`); 95 → 14 (`ｸﾗｯｼｭ`); 127 → 14 (`ｸﾗｯｼｭ`) |
| 4 | `AREAT` | 127 → 13 (`ﾚ-ｻﾞ-2`) |

##### `SAT_2.PMB`

| 악기 ID | 레코드명 | 노트 상한 → soundID (음성명) |
|---:|---|---|
| 0 | `DRUM` | 35 → 1 (`バスドラ`); 47 → 2 (`スネア`); 71 → 3 (`タム`); 95 → 8 (`ｸﾗｯｼｭ`); 127 → 8 (`ｸﾗｯｼｭ`) |
| 1 | `korus` | 127 → 4 (`Chorus`) |
| 3 | `BASS` | 47 → 9 (`BASS`); 59 → 9 (`BASS`); 71 → 9 (`BASS`); 83 → 9 (`BASS`); 95 → 9 (`BASS`); 127 → 9 (`BASS`) |
| 4 | `STRINGS` | 64 → 12 (`STRNG`); 76 → 12 (`STRNG`); 86 → 12 (`STRNG`); 119 → 12 (`STRNG`) |
| 6 | `guitar` | 47 → 10 (`GUitar`); 71 → 10 (`GUitar`); 83 → 10 (`GUitar`); 127 → 10 (`GUitar`) |
| 7 | `PIANO` | 64 → 11 (`A_PIANO`); 76 → 11 (`A_PIANO`); 86 → 11 (`A_PIANO`); 119 → 11 (`A_PIANO`) |

#### PMB 파일 경계 검산

`SATOSHI.PMB`의 헤더+파형은 63,724 bytes, 끝 `0x108F4`; `SAT_2.PMB`는 60,166 bytes, 끝 `0xFB0E`다. 앞서 기록한 파일 크기·voice 블록 수와 함께 파일 끝까지 일치한다.

#### 소스 근거

- 실행 이미지: `0x3A6F0`/`0x3A714` EUP 서비스 디스패처, `0x3B150` 이벤트 파서, `0x3B2E8` Program Change, `0x3B350` Note On, `0x3B5F0` FM/PCM 채널 할당, `0x3B820`/`0x3BA20` 내부 SND 서비스 전달, `0x39480` FMB 로더, `0x395C4` PMB 로더.
- [FreeTOWNSOS SND.H](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tgbios/SND.H): `FMB_INSTRUMENT`, `PMB_INSTRUMENT`, `PCM_Voice_Header` 구조체.
- [FreeTOWNSOS SND.C](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tgbios/SND.C): `SND_INST_CHANGE`, `SND_INST_WRITE`, `SND_KEY_ON`의 split/soundID 선택 및 PCM RAM 적재.

### 게임 자료 그룹

FreeTOWNSOS 이미지의 /ALLTYNEX 디렉터리에서 다음 자료를 확인했다. 이름과 확장자는 분류 단서이며, 모든 파일의 내부 형식과 사용 장면을 각각 역공학했다는 뜻은 아니다.

| 묶음 | 파일·크기 | 확인된 형식/역할과 한계 |
|---|---|---|
| 스프라이트 패턴 | `ALLTY_1.PAT`, `ALLTY_2.PAT`, `ALLTY_P.PAT` 각 32,768 bytes; 대부분 PAT 32,768 bytes; `ROLL_G.PAT` 49,152 bytes | FreeTOWNSOS `SPR_DEFINE`의 16색 패턴은 1개당 128 bytes다. 따라서 32 KB는 256패턴, 48 KB는 384패턴 크기와 일치한다. `PRINT SPRPTN4 0xA0`의 패턴 RAM 128 bytes는 `ALLTY_1.PAT` 오프셋 `0x1000`과 일치하고, 사용자 캡처에서 타이틀의 P가 실제 표시된다. 이 게임 경로의 AH=05h raw 값 `0xA0`와 패턴 entry `0xA0`의 대응은 확인됐다. FreeTOWNSOS `sprite01.c`도 등록 번호와 attribute 번호를 같은 값으로 쓴다. 임의의 raw attribute word 전체의 비트 해석은 별도 미확정이며 `_P` 접미사의 구체적 용도도 미확정이다. |
| 팔레트 | `ALLTYNEX.PAL` 8,192 bytes | SPR BIOS 팔레트 블록 한 항목이 32 bytes이므로 정확히 256개 블록 크기다. 공용 로더는 `0x2AB20`–`0x2AB8A` 구간에서 버퍼 `0x4022C`로 읽고, `0x2AB1B`의 `0x33D20`이 SPR 팔레트 블록으로 등록한다. |
| EUP 음악 | EUP 22개; 파일 시작에 `ALERT`, `MAKE AN ASSAULT...`, `TYRANNY`, `ETERNAL BLUE`, `NAME ENTRY` 같은 트랙/시퀀스 이름이 보임 | `.EUP`는 FM TOWNS의 EUPHONY 음악 연주 데이터 형식이다([EUPHONY 설명 및 오픈소스 플레이어](https://github.com/gzaffin/eupmini)). 파일명·헤더 문자열과 EXP 리소스 표가 스테이지/보스/오프닝/이름 입력/스태프 장면용 음악임을 가리킨다. 모든 재생 호출의 장면별 귀속은 미확정이다. |
| FM 악기 뱅크 | `ST_2.FMB` 6,152 bytes | 크기는 8-byte 접두 + 128개 × 48-byte `FMB_INSTRUMENT`와 정확히 일치한다. EUP 보조 로더 `0x39480`이 접두 뒤 각 레코드를 읽어 `0x3934C`→SND BIOS AH=05h(`SND_INST_WRITE`)로 전달한다. 전달 인자는 `BL=FM 채널 0`, `DH=악기 인덱스 0–127`, `DS:ESI=레코드`다. FreeTOWNSOS [`SND.C`](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tgbios/SND.C)의 구현은 이 레코드를 `SND_Status.FMInst[index]`에 복사한다. |
| PCM 악기·파형 뱅크 | `SATOSHI.PMB` 67,828 bytes, `SAT_2.PMB` 64,270 bytes | PMB 로더는 32개 악기표를 BIOS `AH=05h`, `BL=0x40`으로 등록하고 `AH=23h`로 기존 음성 목록을 비운 뒤, 실제 `PCM_Voice_Header`와 파형 블록을 `AH=22h`로 공급한다. 악기표의 8개 split/ID/envelope와 voice header 경계, BIOS PCM RAM 예약·루프·주파수 사용은 앞의 PMB 악기표·음성 헤더·파형 경계 절에서 파일 바이트와 함께 정리한다. |
| 스테이지/게임 데이터 | `32K_*.DAT` 131,072 bytes; `ENE_*.DAT` 각 16,000 bytes; `M*_*.DAT` 64–4,096 bytes; `MTITLE.DAT` 256 bytes; `PLAYDEMO.DAT` 16,384 bytes | `M*_1`·`M*_2`는 비영 byte를 `0x280+ID` 값으로 SPR AH=05h 속성 호출에 보내는 오버레이 경로이고, `M*_3`는 32K DAT를 참조하는 EGB 배경 경로임을 코드에서 확인했다. 타이틀 P에서 raw `0xA0`와 실제 pattern entry `0xA0`가 대응하는 예를 확인했고, 동일 번호 관례가 `0x280+ID`에도 적용된다는 근거가 강하다. 개별 M ID/ENE 객체와 PAT 도형의 시각적 이름은 미확정이다. ENE의 1-byte 명령 디스패치와 가로 16칸 처리도 연결했다. |
| 실행/설정 | `ALLTYNEX.EXE` 598,678 bytes, `ALLTYNEX.EXP` 267,304 bytes, `CFGDAT.SAV` 3,337 bytes, `README.DOC` | EXP는 앞에서 설명한 P3 32-bit 실행 이미지다. README는 조작/화면 흐름을 설명하며, CFGDAT.SAV의 헤더와 128개 레코드 크기는 별도 절에서 분석한다. |

EXP의 문자열 표에는 `.FMB`·`.PMB` 완성 파일명이 없지만, 이는 리터럴을 코드에 저장하지 않고 EUP 헤더의 두 8-byte stem으로부터 동적으로 만든다. 로더 호출과 `SND_INST_WRITE`·`SND_22H_PCM_SOUND_SET` BIOS 인자를 FreeTOWNSOS 원본 구현과 대조해 FMB 악기 표와 PMB 악기/파형을 실제 사용하는 경로를 확정했다. PMB의 32-byte 파형 헤더 개수와 상세 필드는 앞의 악기·파형 경계 절에서 확인한다.



### 스테이지 파일의 실제 로드 주소와 PAT 등록 범위

파일명 문자열표만 묶어 보지 않고, 각 파일명을 넘기는 공용 로더 `0x2AA10` 호출의 인자를 디코딩했다. 이 로더 호출들은 count=1이며, 아래 크기는 항목 크기로 전달된다. PAT는 로드 뒤 `SPR_DEFINE`에 전달되는 버퍼, 시작 패턴, 가로×세로 개수를 함께 대조했다.

공용 임시 버퍼와 자료 주소:

| 실행 이미지 주소 | 자료/용도 | 코드에서 확인한 최대 사용 크기 |
|---:|---|---:|
| `0x04022C` | `ALLTYNEX.PAL` | `0x2000` bytes |
| `0x04222C` | PAT/타이틀 그래픽 임시 버퍼 | 파일·호출별 `0x4000` 또는 `0x8000`; `ROLL_G.PAT`은 `0xC000` |
| `0x05222C` | `32K_*.DAT` 타일 픽셀 버퍼 | `0x20000` bytes |
| `0x07222C` | `ENE_*.DAT` 이벤트 스트림 | `0x3E80` (=16,000) bytes |
| `0x07622C`–`0x08C22C` | `M*_*.DAT` 맵 자료 버퍼 | 파일별 `0x80`–`0x1000`, 주소는 8 KiB 간격 |

각 스테이지의 요청한 파일·주소·길이는 다음과 같다. 표에서 주소와 길이는 16진수다. PAT와 맵의 의미는 아래 한 단계 더 코
드에서 확인한 내용만 적고, 파일명만으로 `M` 자료를 완전한 화면/프레임이라고 부르지 않는다.

| 구역 | `M` 파일 → 목적지/요청 길이 |
|---|---|
| 1 | `M1_1_1.DAT` → `07622C/1000`; `M1_1_2.DAT` → `07822C/800`; `M1_1_3.DAT` → `07A22C/400`; `M1_2_3.DAT` → `08022C/100`; `M1_3_1.DAT` → `08222C/800`; `M1_3_2.DAT` → `08422C/400`; `M1_3_3.DAT` → `08622C/200`; `M1_4_3.DAT` → `08C22C/100` |
| 2 | `M2_1_1.DAT` → `07622C/100`; `M2_1_2.DAT` → `07822C/200`; `M2_1_3.DAT` → `07A22C/400`; `M2_2_1.DAT` → `07C22C/1000`; `M2_2_2.DAT` → `07E22C/1000`; `M2_2_3.DAT` → `08022C/800`; `M2_3_3.DAT` → `08622C/80` |
| 3 | `M3_1_1.DAT` → `07622C/200`; `M3_1_2.DAT` → `07822C/100`; `M3_1_3.DAT` → `07A22C/200`; `M3_2_3.DAT` → `08022C/400`; `M3_3_3.DAT` → `08622C/800`; `M3_4_3.DAT` → `08C22C/40` |
| 4 | `M4_1_3.DAT` → `07A22C/400`; `M4_1_2.DAT` → `07822C/400`; `M4_1_1.DAT` → `07E22C/800`; `M4_2_3.DAT` → `08022C/400` |
| 5 | `M5_1_1.DAT` → `07622C/800`; `M5_1_3.DAT` → `07A22C/1000`; `M5_2_3.DAT` → `08022C/200`; `M5_3_3.DAT` → `08622C/200` |

구역별 초기 맵 포인터와 이후에 확인된 소비 경로를 별도로 기록한다. 표의 “직접 소비”는 디스어셈블리에서 해당 구역 처리기 내부의 직접 `CALL`을 확인한 함수만 뜻한다. 다른 간접 경로나 미확인 호출까지 없다고 단정하지 않는다.

| 구역 처리기 | 초기 전역 포인터 대입 | 자료와 실제 소비 근거 | 전환 중 확인된 재대입 |
|---|---|---|---|
| 1 (`0x0000`) | `EEDC=0x7622C`, `EEE0=0x7822C`, `EEE4=0x7A22C` | 각각 M1_1_1, M1_1_2, M1_1_3. 초기화 `0x48E8`는 M1_2_3(`0x8022C`)을 EGB 블록으로 채운다. 별도 stage-1 helper `0x58D4`는 `[0x58D4,0x5A6F)` 범위이며 caller `0x7E4/0x8F4/0xA1F/0xB64/0xC0B`에서 호출된다. cadence 통과 시 EEE0와 EEDC에서 각각 16 bytes를 소비해 SPR descriptor를 만든다. `0x48E8`는 EEDC/EEE0를 읽지 않는다. | M1_3 계열의 `0x8222C/0x8422C/0x8622C`, M1_4_3의 `0x8C22C` 등으로 이동. 일부 `_3` 포인터는 페이지/구간 시작 주소에 재설정됨. |
| 2 (`0x5C30`) | `EEDC=0x7622C`(M2_1_1), `EEE0=0x7822C`(M2_1_2), `EEE4=0x7A22C`(M2_1_3) | EGB helper callsites `0x610C/0x6180` use `EEE4`; the M2_1_3 cursor reaches candidate `[0,0x200)` before the `B0>=0x200` transition (`0x6130`, `0x6153–0x6167`), leaving its loaded `[0x200,0x400)` tail outside this mapped path. `_1` callsites `0x6124/0x6198` use `EEE0`; M2_1_2's exact ending offset before pointer replacement remains unresolved. `_2` callsite `0x61B0` uses `EEDC` after `0x6167` resets it to `0x7C22C` (M2_2_1), so no direct byte-read from loaded M2_1_1 at `0x7622C` is confirmed. M2_2_3 at `0x8022C` is consumed conditionally through first threshold boundary `[0,0x6E0)`; file tail `[0x6E0,0x800)` is not reached by this mapped caller. M2_2_2 (`0x7E22C`) and M2_2_1 (`0x7C22C`) rewind when their counters reach `0x800`, so each lap covers `[0,0x800)` and the file tail `[0x800,0x1000)` is unused by these callers. | At `EEB0>=0x200`, pointers are rebased to `EEE4=0x8022C` (M2_2_3), `EEE0=0x7E22C` (M2_2_2), `EEDC=0x7C22C` (M2_2_1); at `EEB0>=0x6D6`, `EEE4=0x8622C` (M2_3_3). The row helper has callers `0x6255/0x62FA/0x63CD/0x6564`; the same base is reassigned at `0x627C/0x631B/0x6412`, with B0 reset. Thus `[0,0x80)` is a repeatable per-handler candidate window, but actual laps depend on selector/cadence re-entry; the later pointer resets do not prove a fixed number of full-page visits. |
| 3 (`0xAC44`) | `EEDC=0x7622C`(M3_1_1), `EEE0=0x7822C`(M3_1_2), `EEE4=0x7A22C`(M3_1_3) | Entry fill `0xAE64` uses EGB from `EEE4`; at `EEB0>=0x80` it resets `EEE4` to `0x7A22C`, so the `0x100`-byte initial fill reads M3_1_3 offsets `0..0x7F` twice. State 3 uses `_1` at `0xB2A3` via EEE0 and `_2` at `0xB2CA` via EEDC. The M3_1_2 cursor starts at `+0x10`, covers `[0x10,0x100)`, then may rewind and repeat `[0,0x100)`; M3_1_1 loops over `[0,0x200)`. M3_1_3 reinitializes at its `0x80`-byte page boundary and these loops do not reach its file tail `[0x80,0x200)`. | State changes set `EEE4=0x8022C` (M3_2_3), later `0x8622C`/`0x8682C` (M3_3_3 base/+`0x600`) and `0x8C22C` (M3_4_3). M3_2_3 is conditionally consumed over `[0,0x300)`; `[0x300,0x400)` is not reached by the mapped path. M3_3_3 is closed for the analyzed path: direct reads cover `[0,0x100)`, a helper covers `[0x100,0x700)`, and after the `+0x600` rebase the next/rewind path covers `[0x600,0x800)`. The unique range is `[0,0x800)`, `[0x600,0x700)` is read twice, and total visits are `0x900` bytes. M3_4_3 repeatedly consumes `[0,0x40)`; this is the mapped loop window, not a claim that later bytes are absent from every path. |
| 4 (`0x13A1C`) | `EEDC=0x7622C`, `EEE0=0x7822C`, `EEE4=0x7A22C` | `M4_1_1` is loaded at `0x7E22C`, then EEE0 is overwritten by `M4_1_2+0xC0` before any mapped `_1` read from that loaded buffer; load alone is not proof of use. `M4_1_2` (`0x7822C`) `_1` callers conditionally consume `[0xC0,0x240)`, rewind and revisit `[0x140,0x240)`, then continue toward `[0x340)`; unique mapped range `[0xC0,0x340)`, with `[0,0xC0)` and `[0x340,0x400)` not reached in this path. `M4_1_3` (`0x7A22C`) cursor reaches unique offsets `[0,0x3C0)`, with resets making `[0x40,0xC0)` and `[0x280,0x3C0)` repeatable; actual visit counts are cadence/path dependent. `M4_2_3` (`0x8022C`) direct EGB fills read `[0,0x100)`, `[0x140,0x240)`, `[0x240,0x340)`. Separately, common EGB row callers can conditionally advance a base cursor through candidate offsets up to `[0,0x210)` and may bridge the `[0x100,0x140)` direct-fill gap; cadence and selector reachability prevent claiming every candidate byte is fetched. No later EEE4 write after the `+0x240` page is mapped, so `[0x340,0x400)` has no mapped reader in this stage body. | `EEE0` rebases through `0x7836C` and `0x7E22C`; `EEE4` through `0x7A4AC`, then M4_2_3 base `0x8022C`, `+0x140` (`0x8036C`), and `+0x240` (`0x8046C`). `0x7A26C` belongs to M4_1_3 base `0x7A22C+0x40`, not M4_2_3. |
| 5 (`0x1C8AC`) | `EEDC=0x7622C`(M5_1_1), `EEE0=0x7822C`(no corresponding M5 input), `EEE4=0x7A22C`(M5_1_3) | Loader operands confirm M5_1_1 `0x800` bytes→`0x7622C`, M5_1_3 `0x1000`→`0x7A22C`, M5_2_3 `0x200`→`0x8022C`, M5_3_3 `0x200`→`0x8622C`. EGB direct fill `0x1CAC2` reads M5_1_3 `[0,0x100)`. EEE4 cursor handlers compare thresholds `0x240/0x280`, `0x380`, then later `0x480`; mapped windows include `[0x100,0x240)`, `[0x240,0x280)`, repeated `[0x280,0x380)` and later a conditional path toward `[0x280,0x480)`. Rewinds at `0x1D090/0x1D134/0x1D1A2` prevent treating selector counts as unique consumption. `_2` helper `0x2A540` callers `0x1CFBD/0x1D052/0x1D0F7` each consume 16-byte windows from EEDC. The first unique file window is `[0,0x140)`; each rebase restarts at `+0x80` and revisits `[0x80,0x140)`. Repetition ends when the `EEB0` selector transition is reached; the number of laps varies with runtime cadence. Tail `[0x140,0x800)` is not consumed by these mapped callers. `EEE0` has no loaded M5 file and no direct `_1` caller is confirmed. | EEE4 moves within M5_1_3 to `+0x280`, then M5_2_3 base `0x8022C` (conditional EGB row cursor candidate `[0,0x100)`, compare `B0>=0x100` at `0x1D2A6`; no mapped path reads `[0x100,0x200)`), and M5_3_3 base/`+0x40` at `0x8622C/0x8626C`. For M5_3_3, the exhaustive Stage 5 row-helper callsites are `0x1D445` and `0x1D4C2`. The latter is followed by a conditional rebase to EEE4=`0x8626C` (+`0x40`) and B0=`0x40` (`0x1D4E1/0x1D4EB`), but no subsequent Stage 5 common row-helper call is mapped; therefore consumption of `[0x40,0x80)` is unproven. The mapped calls support only a candidate `[0,0x80)` window, subject to cadence. No later cursor consumption is mapped; file tail `[0x80,0x200)` is not reached in this inspected caller path. |

### M 맵을 화면으로 바꾸는 두 경로

초기 그래픽 단계 `0x2A78A`는 EGB `AH=01h RESOLUTION` 래퍼를 페이지 0 과 1 에 각각 `DX=8`로 호출한다. FreeTOWNSOS `EGBDATA.C` mode 8 은 표시 영역 256×240, VRAM size 256×512, 16-bit 픽셀, 행당 512 bytes다. 따라서 `32K_*.DAT`의 131,072 bytes는 256 개의 16×16 타일(각 512 bytes)로 정확히 나뉜다. 이는 초기 DAT 그래픽 단계다. 뒤이어 공용 helper `0x2A864`가 EGB를 다시 초기화하고 `(page0,page1)=(3,5)`로 설정하므로, 이 초기 mode 8 을 최종 AH=60 문자열 출력 모드로 보면 안 된다.

`0x27CA4`는 `_3` 맵 셀 하나를 그리는 helper다. 입력 byte ID를 `ID×0x200 + 0x5222C`에 더해 타일 원본을 선택하고, EGB 블록 설명자 `0x8E22C`에 원본의 far pointer와 포함 좌표를 기록한다. 타일 좌표는 `x=열×16`, `y=([0x8EEB4] ring row)×16`, 끝점은 각각 `+15`다. 그 뒤 `0x33C40` 래퍼가 EGB `AH=25h PUTBLOCK`을 호출한다. FreeTOWNSOS EGB.C도 Mode 8 에서 폭 16 의 소스 행 stride를 `16×2=32` bytes로 계산해 16 행을 복사한다. 따라서 `M*_3`의 1-byte ID → 32K DAT의 512-byte 16-bit 타일 → 16×16 화면 블록이라는 자료 변환이 파일 크기, 게임 명령, BIOS 구현에서 모두 맞는다.

배경 갱신기 `0x28FC0`는 `[0x8EE90]&0x3F==0`일 때만 위 helper를 한 행에 적용한다. `[0x8EEB4]`는 0 아래로 넘어가면 32 로 돌아가는 0–31 ring index다. 한 번의 갱신에서 `[0x8EEE4]`의 16-byte 구간을 소비하고 포인터/카운터를 `+0x10` 전진시키지만, helper 호출은 열 인덱스 0–14, 즉 15 개 셀에만 하며 16 번째 byte는 출력하지 않는다. 현재 코드에서 확정되는 것은 “행 갱신당 16 bytes 소비, 15 개 타일 출력”까지다. 남는 열의 의도는 경계/패딩이라고 임의로 단정하지 않는다. M 파일 크기가 16 의 배수인 것은 이 고정폭 커서 이동과 일치한다.

`_1`/`_2` 맵은 같은 EGB 경로가 아니다. stage 1 entry helper `0x48E8`는 `[0x48E8,0x49C1)` 안에서 `0x8022C + EEB0`의 M1_2_3 byte를 읽어 16×16 EGB 타일 셀을 채우며, EEB0 의 source interval은 `[0,0x100)`이다. 별도 `0x58D4`는 `[0x58D4,0x5A6F)`이며 callers `0x7E4/0x8F4/0xA1F/0xB64/0xC0B`에서 호출된다. 각 caller의 cadence divisor는 차례로 32/32/32/16/8 이고, `[0x8EEA4] % divisor != 0`이면 자료를 읽지 않고 반환한다. cadence 통과 시 selector `[0x8EED0]` 기준 EEE0 와 `[0x8EED4]` 기준 EEDC에서 각각 연속 16 bytes를 소비한다. 첫 호출은 EEDC=0x7622C (M1_1_1 offset 0), EEE0=0x7822C (M1_1_2 offset 0)일 때 발생하고, 이후 M1_3_1/3_2 의 file offset 0 을 가리키도록 두 포인터가 재배치된다. 후보 read window는 호출마다 `[cursor,cursor+0x10)`이며 helper 자체에는 파일 끝 확인이 없다. 출력 cap은 EEE0 쪽 20 descriptor(`[0x8EECC]>=0x14`)와 EEDC 쪽 28 descriptor(`[0x8EEC8]>=0x1C`)다. 0 ID이거나 cap에 도달해도 포인터와 대응 카운터 `[0x8EEB8]`/`[0x8EEBC]`는 바이트마다 전진하므로 cap은 소비 범위가 아니다. 허용된 비영 ID는 `0x28F6C`로 가 SPR descriptor를 만든다. 따라서 `0x48E8`은 `_3` 배경 초기 채움이고 `0x58D4`는 `_1/_2` 오버레이 처리이며, 둘은 함수·호출시점·자료 흐름이 다르다. 0x58D4 caller 반복 횟수는 selector 활성기간과 cadence에 달려 있어 파일별 총소비량은 닫히지 않았다.

Stage 1 의 첫 paired 구간을 더 좁히면 `0x7E4 → 0x58D4`만 M1_1_1/1_2 버퍼가 교체되기 전에 두 파일을 함께 읽는다. 이 호출은 divisor 32 이며 각 통과에서 두 파일의 cursor를 16 bytes씩 전진시킨다. 이후 EEE0/EEDC는 각각 M1_3_2/1 의 시작 주소로 교체되고, Stage 1 경로에서는 이전 M1_1_1/1_2 주소로 되돌아가는 할당이 없다. 따라서 첫 구간의 정적 소비 형태는 파일별 비반복 prefix `[0,16N)`이며, 실제 N은 cadence 통과·selector 활성기간에 따라 달라 아직 확정되지 않았다. M1_3 포인터는 `0x9AB/0x9B5`에서 다시 파일 시작으로 되감기지만 누적 cursor `[0x8EEB8]/[0x8EEBC]`는 초기화되지 않는다. 뒤의 `0xC0B` 호출까지 실제 원본 파일 오프셋은 pointer base와 누적 cursor를 함께 계산해야 하며, 마지막 paired call 뒤의 threshold reset은 그 다음에 paired read가 없어 전체 페이지 재독을 입증하지 않는다. M1_3_3 은 EEE4 를 `0x8622C`에 두고 row cursor B0 를 0 으로 초기화한 뒤 `0x9F0`에서 EGB row helper를 부른다. `B0>=0x1FF` 분기는 16-byte cadence와 결합해 후보 `[0,0x200)` 한 페이지 순회를 나타내며, M1_4_3 으로 포인터가 바뀌기 전 재할당/rewind는 확인되지 않았다. 이들은 정적 후보 범위이고 동적 cadence에 따른 실제 방문 여부와 회수는 구분한다.

Stage 1 후반의 callback은 `0xBF8`에서 common EGB row helper `0x28FC0`를 부르고, paired helper `0x58D4`는 `0xC0B`에 호출된다. Timeline 비교 `0xB6C` 뒤 selector 8 은 `0xB7C`에서 설정되고, EEE4=`0x8C22C` (M1_4_3)은 `0xBD2`, B0=0 은 `0xBAA`에서 설정된다. M1_4_3 row cursor는 `0xC5D`에서 B0>=`0x100` 비교를 거치며, 분기 `0xC67` 뒤 B0=0 (`0xC6D`)과 EEE4 재설정 (`0xC77`)을 수행한다. 따라서 매 reset cycle의 M1_4_3 row source 후보는 `[0,0x100)`이며 반복 방문이 가능하나 cadence에 따른 실제 회수는 별도다. paired helper `0xC0B` 뒤 BC/B8 counter reset 및 source-base 재설정도 발생한다 (`0xC13–0xC49`). `0xC86`부터 시작하는 다음 handler는 이전 callback의 fallthrough가 아니다. 이 handler는 스크롤 이동량 `[0x8EE98]=1`을 `0xC90`에서 쓰고 row helper를 `0xC9A`에서 부른다. B0 compare `0xC9F`/JLE `0xCA9` 뒤 reset `0xCAB`와 EEE4=M1_1_3(`0x7A22C`) 재지정 `0xCB5`가 가능하다. 이어지는 63-iteration loop (`CMP EDI,0x3F` at `0xCC1`; JGE `0xCC4`)는 EEE4 를 읽지 않으므로 이 재지정만으로 M1_1_3 의 소비를 주장할 수 없다. Stage1 helper `0x27CA4`는 확인된 호출점 `0x28B` 하나다. 포인터 할당은 자원 사용 증거와 구분한다.

스테이지 진행 중 일반 `_1/_2` 점진 출력은 `0x2A464`(맵 포인터 `[0x8EEE0]`, selector `[0x8EED0]`)와 `0x2A540`(`[0x8EEDC]`, `[0x8EED4]`)가 담당한다. 구역 1 의 별도 paired path는 위의 `0x58D4`다. cadence gate를 통과할 때마다 일반 helper들은 각자의 맵 포인터에서 16 bytes를 읽고 포인터와 대응 카운터를 각각 `+0x10` 전진시킨다. 이 16-byte 소비는 ID가 0 이거나 sprite cap을 넘어서 실제 SPR 출력을 건너뛰어도 동일하다. 0 이 아닌 ID가 cap 안에 있으면 `0x28F6C`로 보내 위치/raw attribute를 설정하고 AH=05h 값 `0x280+ID`를 기록한다. caller의 selector 범위/cadence mask는 출력 가능한 슬롯과 실행 틱을 제한한다. 따라서 포인터가 진행한 byte 수와 실제로 화면에 만든 SPR 수는 같지 않다. `0x2A61C`와 `0x2A6D0`은 각각 생성된 sprite descriptor 구간을 후처리한다. 구역별 caller와 포인터 재설정은 위 표처럼 따로 기록한다. 패턴 그림의 장면 의미나 raw attribute의 하드웨어 슬롯 해석은 별도 근거 없이 단정하지 않는다.

### `_1/_2` 오버레이의 stage caller와 DAT 바이트 통계

`0x2A464`/`0x2A540` caller는 `(최대 sprite 수, 시작 selector, 끝 selector, cadence 값, color-table 인자)`를 역순 push한다. 시작·끝 selector의 포괄 구간 길이가 최대 sprite 수와 정확히 같다. 두 helper는 전역 처리 수가 이 한도에 이르면 새 맵 항목의 SPR 출력을 건너뛴다. cadence 값은 내부에서 1 을 뺀 mask로 적용된다. 이 표의 “attr”는 SPR BIOS가 기록하는 color-table 값의 원시값이고, 각 비트의 시각적 의미까지 해독했다는 뜻은 아니다.

| 구역 | caller → helper | 맵 포인터 | selector 범위/수량 | cadence | attr |
|---|---|---|---|---:|---:|
| 2 | `0x6124 → 0x2A464` | `EEE0` | `0x2E7–0x30A` / 36 | 64회 mask 주기 | `0x1A5` |
| 2 | `0x6198 → 0x2A464` | `EEE0` | `0x2E7–0x30A` / 36 | 64 | `0x1A5` |
| 2 | `0x61B0 → 0x2A540` | `EEDC` | `0x30B–0x316` / 12 | 64 | `0x1A7` |
| 3 | `0xB2A3 → 0x2A464` | `EEE0` | `0x2E7–0x2FB` / 21 | 8 | `0x1AB` |
| 3 | `0xB2CA → 0x2A540` | `EEDC` | `0x2FC–0x325` / 42 | 4 | `0x1AB` |
| 4 | `0x13F6D`, `0x13FD8`, `0x1406F → 0x2A464` | `EEE0` | `0x2E7–0x325` / 63 | 4 | `0x1B5` |
| 5 | `0x1CFBD`, `0x1D052`, `0x1D0F7 → 0x2A540` | `EEDC` | `0x2E7–0x325` / 63 | 4 | `0x1BF` |

caller가 읽는 `_1/_2` 비영 byte는 `0x280+ID`를 SPR AH=05h의 raw attribute 인자로 전달한다. `STn_BG.PAT`와 보스 전환 뒤의 `STn_BOS.PAT`가 각각 `SPR_DEFINE`의 시작 번호 `0x280`에 등록되는 사실을 확인했다. 타이틀 P에서 raw `0xA0`가 pattern entry `0xA0`와 실제로 대응하고 FreeTOWNSOS 테스트도 동일 번호 관례를 사용하므로, `0x280+ID`와 등록 범위 `0x280` 역시 같은 번호 체계를 따른다는 근거가 강하다. 다만 각 M ID가 가리키는 구체 도형과 애니메이션의 시각적 이름까지 모두 대조한 것은 아니다.

일본 원판 ZIP의 실제 M 자료를 16-byte 행으로 나눠 세었다. 비영 셀은 0 ID를 건너뛰는 경로에서 그려질 후보이고, 유일 ID 범위는 byte값 범위다. “active rows”는 16-byte 줄 중 적어도 하나의 비영 byte가 있는 줄 수다.

| 구역 | 파일 | 크기/16-byte 행 | 비영 셀/active rows | 비영 ID 범위 |
|---|---|---:|---:|---:|
| 1 | `M1_1_1.DAT` | `0x1000` / 256 | 203 / 89 | `0x30–0x57` |
| 1 | `M1_1_2.DAT` | `0x800` / 128 | 56 / 43 | `0x2C–0x5F` |
| 1 | `M1_1_3.DAT` | `0x400` / 64 | 503 / 47 | `0x04–0xE1` |
| 1 | `M1_2_3.DAT` | `0x100` / 16 | 69 / 16 | `0x0B–0x89` |
| 1 | `M1_3_1.DAT` | `0x800` / 128 | 148 / 78 | `0x01–0x28` |
| 1 | `M1_3_2.DAT` | `0x400` / 64 | 67 / 48 | `0x20–0x27` |
| 1 | `M1_3_3.DAT` | `0x200` / 32 | 130 / 32 | `0x02–0xE3` |
| 1 | `M1_4_3.DAT` | `0x100` / 16 | 101 / 16 | `0x08–0x67` |
| 2 | `M2_1_1.DAT` | `0x100` / 16 | 21 / 16 | `0x2A–0x2B` |
| 2 | `M2_1_2.DAT` | `0x200` / 32 | 42 / 15 | `0x01–0x0A` |
| 2 | `M2_1_3.DAT` | `0x400` / 64 | 341 / 64 | `0x01–0xFF` |
| 2 | `M2_2_1.DAT` | `0x1000` / 256 | 24 / 6 | `0x0B–0x16` |
| 2 | `M2_2_2.DAT` | `0x1000` / 256 | 148 / 62 | `0x01–0x0A` |
| 2 | `M2_2_3.DAT` | `0x800` / 128 | 665 / 128 | `0x01–0xEF` |
| 2 | `M2_3_3.DAT` | `0x80` / 8 | 73 / 8 | `0x0E–0xF9` |
| 3 | `M3_1_1.DAT` | `0x200` / 32 | 34 / 11 | `0x01–0x24` |
| 3 | `M3_1_2.DAT` | `0x100` / 16 | 21 / 11 | `0x25–0x32` |
| 3 | `M3_1_3.DAT` | `0x200` / 32 | 497 / 32 | `0x14–0xFE` |
| 3 | `M3_2_3.DAT` | `0x400` / 64 | 1,024 / 64 | `0x10–0xFF` |
| 3 | `M3_3_3.DAT` | `0x800` / 128 | 2,016 / 128 | `0x01–0xFE` |
| 3 | `M3_4_3.DAT` | `0x40` / 4 | 60 / 4 | `0x0C–0x4B` |
| 4 | `M4_1_1.DAT` | `0x800` / 128 | 60 / 57 | `0x3E–0x41` |
| 4 | `M4_1_2.DAT` | `0x400` / 64 | 96 / 36 | `0x01–0xFF` |
| 4 | `M4_1_3.DAT` | `0x400` / 64 | 988 / 64 | `0x01–0xFF` |
| 4 | `M4_2_3.DAT` | `0x400` / 64 | 1,011 / 64 | `0x01–0xFF` |
| 5 | `M5_1_1.DAT` | `0x800` / 128 | 39 / 11 | `0x01–0x15` |
| 5 | `M5_1_3.DAT` | `0x1000` / 256 | 671 / 72 | `0x01–0xF6` |
| 5 | `M5_2_3.DAT` | `0x200` / 32 | 271 / 18 | `0x01–0xFF` |
| 5 | `M5_3_3.DAT` | `0x200` / 32 | 136 / 16 | `0x58–0xE6` |

이 표에서 포인터 값은 “파일 버퍼 시작”과 “파일 내부에서 이동한 맵 커서”를 구별한다. 예를 들어 0x782EC는 M4_1_2 시작 주소가 아니라 같은 로드 버퍼 안의 +0xC0 위치이고, 0x8682C는 M3_3_3 시작 주소 +0x600 이다. 파일명과 포인터의 의미는 초기 대입·전환 코드·실제 호출자를 함께 따라가야 한다.

모든 구역에서 `32K_n.DAT`는 `05222C`에 `0x20000` 요청, `ENE_n.DAT`는 `07222C`에 `0x3E80` 요청으로 반복된다. 각 구역의 `STn_BG.PAT`와 `STn_BOS.PAT`는 `04222C`에 `0x8000`, `STn_BG2.PAT`는 같은 버퍼에 `0x4000`을 요청한다. 최종부는 `32K_5_2.DAT`와 `32K_5.DAT`를 각각 `05222C/0x20000`으로 다시 적재하고, `ENE_6.DAT`는 `07222C/0x3E80`, `ROLL_G.PAT`은 `04222C/0xC000`에 적재한다. 타이틀은 `TITLE.PAT` `04222C/0x8000`, `32K_TIT.DAT` `05222C/0x20000`, `MTITLE.DAT` `07A22C/0x200` 요청이다.

확인된 `SPR_DEFINE` 호출은 `STn_BG.PAT`의 256 개를 시작 번호 `0x280`에, `STn_BG2.PAT`의 128 개를 `0x380`에 등록한다. 모두 16 색 128-byte 패턴이며 원본 버퍼는 `0x4222C`다. FreeTOWNSOS `SPR_DEFINE` 구현은 `DS:ESI`에서 패턴 RAM으로 `폭×높이×128` bytes를 즉시 복사한다(`tgbios/SPR.C`, `_movedata`). 따라서 PAT를 공용 임시 버퍼에 읽는 일과 SPR 패턴 RAM에 등록하는 일은 서로 다른 단계다. `ST1_BG2.PAT`–`ST4_BG2.PAT`과 `ST5_BOS2.PAT`은 각각 32,768 bytes지만 해당 호출은 첫 16 KiB만 읽어 `0x380`–`0x3FF` 128 칸에 등록한다. 일본 원판 ZIP에서 다섯 파일의 두 번째 절반은 각각 16,384 개의 0 byte이며, 이는 요청 범위 밖의 파일 끝 padding이다. 각 파일명 리터럴은 게임 이미지에서 해당 로드 호출 한 곳씩만 참조된다.
각 `STn_BOS.PAT`(n=1–5)은 로드 직후 항상 등록되는 것이 아니라, 같은 `0x4222C` 버퍼에 보존됐다가 해당 구역의 별도 조건에서 `SPR_DEFINE`로 들어간다. 다섯 호출 모두 시작 번호 `0x280`, 폭 16, 높이 16 을 사용하므로 각 32 KiB 보스 파일의 256 개 패턴을 복사해 기존 `STn_BG.PAT`의 SPR 슬롯 `0x280–0x37F`를 교체한다. 실제 파일 내용은 스테이지 버퍼를 거쳐 지연 등록되므로 로드 직후만 확인해서 소비 여부를 판단할 수 없다.

| 파일 | 읽기 호출 | 등록 호출 | 코드에서 확인한 경로/조건 |
|---|---:|---:|---|
| `ST1_BOS.PAT` | `0x200` | `0xAE6` | 구역 1 selector `0x8EE8C=7` 경로. 특수 초기 화면 helper `0x48E8` 뒤 16×16/`0x280` 등록; 이후 플레이어 상태를 보고 boss EUP slot 2 시작 여부를 분기한다. |
| `ST2_BOS.PAT` | `0x5DD6` | `0x6341` | 구역 2의 `0x8EEBC==0xA0` 분기에서 16×16/`0x280` 등록; EUP slot 2 재생은 이어서 플레이어 상태 `+4<=4`인 경우에 시작한다. |
| `ST3_BOS.PAT` | `0xADD0` | `0xCA27` 직전 handler `0xCA17` | `ENE_3.DAT` 값 30 handler에서 등록하고 이어 복수 객체 상태를 초기화한다. 일본 원판 파일에서 값 30은 한 건이다. |
| `ST4_BOS.PAT` | `0x13B7B` | `0x14439` | 구역 4 update에서 scroll 위치 `0x8EEB0==0x1C0`, counter `0x8EEBC==0`일 때; player 상태 `+4<=4`이면 EUP slot 2를 시작한 뒤 16×16/`0x280` 등록한다. |
| `ST5_BOS.PAT` | `0x1CA07` | `0x1DE96` | `ENE_5.DAT` 값 3 handler `0x1DE30`의 객체 초기화 뒤 등록; player 상태 `+4<=4`인 경우 EUP slot 3을 시작한다. |

따라서 이 게임의 보스 화면은 공용 패턴 RAM의 새 전용 영역을 할당하는 게 아니라, 배경 PAT와 같은 `0x280–0x37F` 슬롯을 스테이지 중 교체하는 구성이다. `STn_BG2.PAT`에서 등록한 `0x380–0x3FF` 구간과는 다른 뱅크다. 각 등록의 helper 호출은 FreeTOWNSOS `SPR_DEFINE`가 원본 바이트를 즉시 패턴 RAM으로 복사한다는 구현과도 맞는다.

일본 원판 ZIP 바이트도 코드 사용과 함께 확인했다. `ST4_BOS.PAT`은 32 KiB 중 뒤 16 KiB가 모두 0 이고, `ST5_BOS.PAT`은 뒤 절반에 4,096 개의 비영 byte가 있다. 첫 16 KiB의 128-byte 패턴을 각각 대응 BG2 패턴과 비교하면 ST4 은 17/128, ST5 은 18/128 이 같다. 이런 유사/제로 패턴은 등록 범위를 줄이는 근거가 아니며, 실제 `SPR_DEFINE` 인자는 양쪽 모두 16×16 이다.

공용 로더 요청 길이와 ISO 파일의 실제 길이를 대조한 예외는 현재 여섯 건이다. ST1_BG2.PAT–ST4_BG2.PAT 및 ST5_BOS2.PAT은 각각 ISO 파일이 0x8000인데 해당 호출은 0x4000만 요청하고, MTITLE.DAT은 실제 0x100 bytes인데 호출은 0x200을 요청한다. MTITLE.DAT 렌더 루프는 16×16=256개 인덱스를 처리하므로 실제 파일의 256 bytes와 일치한다. 공용 read 경로는 남은 요청량이 없는 short read를 반환하며 상위 0x2AA10은 반환된 완전 항목 수를 검사하지 않는다. MTITLE.DAT의 256개 인덱스 접근은 제공된 256 bytes 안에 있다.

짧은 읽기 동작도 호출 체인에서 확인했다. `0x3573C`는 요청된 `size × count` 바이트를 하위 파일 읽기 함수 `0x35280`에 전달하고, 반환된 실제 바이트 수를 항목 크기로 나눠 완전히 읽힌 항목 수를 반환한다. `0x2AA10`은 이 반환값을 검사하지 않고 파일을 닫는다. 따라서 `MTITLE.DAT`의 512-byte 요청은 256-byte 실제 파일을 읽고 “완전한 512-byte 항목 0개”를 반환하더라도 호출 측이 계속 진행하는 형태다. 화면 렌더러가 그 맵에서 사용하는 인덱스 256개는 파일의 256 bytes에 들어 있다. 이 코드는 512-byte가 전부 유효하다고 가정하는 것이 아니라, 호출자가 short-read 결과를 무시하는 동작을 보여준다.


### 실행 이미지의 스테이지 리소스 표와 README가 확인하는 장면 흐름

압축 해제 이미지의 파일명/문구 상수표(런타임 이미지 0x3BD04–0x3C4xx)에 스테이지별 파일 묶음과 그 바로 뒤의 제목 문구가 
연속 저장돼 있다. 아래 그룹은 정적 문자열 표에서 확인한 묶음이며, 각 파일이 실제 어느 프레임에서 열리는지까지 모두 디버
거로 확인했다는 뜻은 아니다.

| 데이터표 위치 | 스테이지/장면 문자열 | 파일명 묶음 |
|---:|---|---|
| 0x3BD04 | `FIRST AREA`, `MAKE AN ASSAULT ON ENEMY`, `TARGET DESTROYED`, `FIRST AREA IS OVER` | `32K_1.DAT`, `M1_*`, `ENE_1.DAT`, `ST1_*.PAT`, `STAGE_1A/B.EUP`, `BOS_01_A.EUP` |
| 0x3BE20 | `SECOND AREA`, `ATTACK THE ZLDYZANT BASE`, `TARGET DESTROYED`, `SECOND AREA IS OVER` | `32K_2.DAT`, `M2_*`, `ENE_2.DAT`, `ST2_*.PAT`, `STAGE_2A/B.EUP`, `BOS_02_A.EUP` |
| 0x3BF30 | `THIRD AREA`, `THE BITING COLD WIND`, `TARGET DESTROYED`, `THIRD AREA IS OVER` | `32K_3.DAT`, `M3_*`, `ENE_3.DAT`, `ST3_*.PAT`, `STAGE_3A/B.EUP`, `BOS_03_A/B.EUP` |
| 0x3C040 | `FORTH AREA`, `LAST DEFENCE LINE`, `TARGET DESTROYED`, `FORTH AREA IS OVER` | `32K_4.DAT`, `M4_*`, `ENE_4.DAT`, `ST4_*.PAT`, `STAGE_4A/B.EUP`, `BOS_03_A/B.EUP` |
| 0x3C134 | 스테이지 5 리소스 목록 | `32K_5.DAT`, `M5_*`, `ENE_5.DAT`, `ST5_*.PAT`, `STAGE_5A/B.EUP`, `BOS_05_A/B/C.EUP` |
| 0x3C410 / 0x3C460 | `FINAL AREA`, `AGGRESSIVE ATTACK`, `TARGET DESTROYED`, `FINAL TARGET`, `ALLTYNEX` | 끝 장면 리소스 표: `32K_5_2.DAT`, `32K_5.DAT`, `ENE_6.DAT`, `ROLL_G.PAT`, `STAFF.EUP` 두 항목 |

일본어 원판 ZIP의 `README.DOC`를 CP932로 읽으면 실제 화면 전이가 “오프닝 데모 → 타이틀 → 일정 시간 입력이 없으면 플레이 데모”라고 설명한다. 타이틀에서 RUN을 누르면 1P, 2P, 1P+2P, OPTION 메뉴가 나오고, 옵션에는 난이도, 잔기, 스테레오/모노, 반격탄, 자동 슬로다운, 게임 종료, 대기 설정, 점수 초기화, 타이틀 복귀가 있다. README는 세로 스크롤 슈팅, 총 5스테이지, 동시 2인 플레이와 파이터/아머 변형 조작도 명시한다. EXP 상수표의 스테이지 제목·메뉴 문구·`PLAYDEMO.DAT`·`NAME.EUP`·`STAFF.EUP`가 이 문서의 장면 구분과 일치한다.

EXP의 전역 문자열 표는 `0x3DFDC` 부근부터 `AL_OVER.EUP`, `ALERT.EUP`, `NAME.EUP`, `ALLTYNEX.PAL`, `ALLTY_1.PAT`, `ALLTY_2.PAT`, `ALLTY_P.PAT`, `GAJE.PAT`, `PLAYDEMO.DAT`, `NOW LOADING`, `STAFF.EUP`, `CONTINUE=`, `CREDIT`, `GAME OVER`, `TITLE.PAT`, `32K_TIT.DAT`, `MTITLE.DAT`, `PROJECT@RAID@WIND@2`를 가리킨다. 이후 `1PLAYER`, `2PLAYER`, `OPTION`, 난이도/잔기/음향 옵션, `RANK`, `SCORE`, `NAME`, `1996:10@SATOSHI@YOSHIDA@@<`, `RANKING` 등의 UI 리터럴이 있다. 이는 EXP가 실행 코드와 화면 문구·파일명 표를 한 런타임 이미지 안에 함께 둔 구조임을 보여준다. 문자열 근처 주소만으로 모든 상태 전이 함수가 확정되는 것은 아니다.

초기화에서 ALLTY_1.PAT과 ALLTY_2.PAT는 각각 패턴 번호 0x80 과 0x180 부터 256 개씩 등록된다. FreeTOWNSOS SPR.C의 16 색 패턴은 하나당 128 bytes다. ALLTY_P.PAT은 같은 임시 버퍼 0x94CE4 에 뒤이어 읽히며, 이후 플레이어별 입력/애니메이션 처리 0x2F0CC–0x2F395 가 조회 표에서 패턴 오프셋을 얻어 0x33CF4 로 SPR 패턴 RAM에 4 개씩 재등록한다. _P 파일명의 문자 그대로 뜻까지는 확인되지 않았지만 플레이어 동작 경로의 그래픽 원본으로 소비되는 것은 코드상 연결된다. GAJE.PAT도 0x9CCE4 에서 런타임 SPR 재등록 경로가 읽는다.

## 리소스 적재 경로

런타임 이미지 000C:0002AA10에는 게임 파일을 여는 공용 함수가 있다. 확인된 호출 규약은 다음과 같다.

| 인자 | 함수 진입 시 위치 | 역할 |
|---|---|---|
| 파일명 | [EBP+08h] | 예: PAT/EUP/DAT 이름 |
| 목적 버퍼 | [EBP+0Ch] | 실행 이미지 안에 준비한 메모리 |
| 항목 크기 | [EBP+10h] | fread의 항목 크기 |
| 항목 수 | [EBP+14h] | fread의 항목 개수 |

함수 흐름은 fopen(name, "rb") → fread(buffer, size, count, fp) → fclose(fp)다. 기존 리소스 적재 호출도 이 함수를 사용하지만, 래퍼가 `fread` 반환값을 버리고 최종적으로 `fclose` 결과를 돌려주므로 short read를 호출자가 확인할 수 없다. 파일 길이·동적 할당에 쓰이는 하위 함수는 EUP 경로에서 `fseek` `0x3436C`, `ftell` `0x34450`, `malloc` `0x34590`, `fread` `0x3573C`로 확인했다. 최종 FNT 적재 동작과 제한은 [한글 빌드](Alltynex-Korean-Build.md)에 기록한다.

### CFGDAT.SAV 레이아웃

파일 크기는 9 + 128×26 = 3,337 bytes와 정확히 일치한다. record i의 파일 오프셋은 9 + 0x1A×i이다. 헤더 원시값은 02 04 00 00 00 00 00 00 01 이다. 헤더 byte 0/1/2/3/4/6/7/8 의 옵션 소비는 이어지는 옵션 절에 정리한다. byte 5 의 의미는 미확정이다.

| 레코드 오프셋 | 크기 | 정적으로 확인한 내용 |
|---|---:|---|
| +0x00..+0x0F | 16 bytes | 기본행은 NOPLAYER@@@@@@@@. 고득점 이름 처리도 선두 영역에 이름 바이트를 복사한다. |
| +0x10 | 1 byte | DATA RESET은 0. 고득점 행 갱신 코드 0x2D0F0은 CFGDAT 헤더 byte 6(AUTO SLOW DOWN)을 복사한다. |
| +0x11 | 1 byte | DATA RESET은 0. 0x2D103은 현재 EDI의 low byte를 기록하며, 같은 경로에서 EDI는 플레이어별 8-byte 이름 버퍼 선택에 쓰인다. |
| +0x12..+0x15 | 4 bytes | 점수 비교에서 DWORD로 읽는다. 기본행 값은 5,000부터 500까지다. |
| +0x16..+0x19 | 4 bytes | DATA RESET은 DWORD 1을 기록한다. 고득점 행 갱신 코드 0x2D106은 global DWORD [0x943B0]을 복사한다. 그 global의 게임 규칙상 의미는 미확정이다. |

런타임 레코드 배열은 0x9365C부터 시작해 0x9435C에서 끝난다(128×0x1A = 0xD00). EXP는 헤더를 0x93618 에, 레코드를 0x9365C에 별도 fread한다. 이 주소 간격은 파일 패딩이 아니다. 배열 직후의 [0x9435C]는 레코드 배열 끝 주소와 겹쳐 놓인 별도 DWORD pointer/cursor 변수다.

영문 패치 ISO의 첫 100 행은 10 행씩 반복되는 기본 점수표다. 행 100–109 와 113–127 은 0 이다. 행 110–112 는 KRETON@@로 시작하고 점수는 각각 40,025 / 25,718 / 1,666, 마지막 DWORD는 5 / 5 / 1 이다. 이 행의 출처나 게임상 용도는 아직 확인되지 않았다.

### CFGDAT.SAV의 EXP 읽기·쓰기

| 동작 | 주소 | 근거 |
|---|---|---|
| 읽기 호출자 | 0x2AA73 | 초기화 0x2AA54에서 reader 0x2ED88을 직접 호출한다. 직접 near-CALL은 한 곳이다. |
| reader | 0x2ED88 | 0x3F21C의 rb, 0x3F220의 cfgdat.sav로 open wrapper 0x34B30 호출(0x2ED93). fread wrapper 0x3573C에 header (0x93618, size 9, count 1)을 0x2EDA7에서, records (0x9365C, size 0x1A, count 0x80)을 0x2EDBE에서 전달한다. close wrapper 0x34268은 0x2EDC9에서 호출한다. |
| writer | 0x2D6E4 | 0x3E6EE의 wb, 0x3E6F4의 cfgdat.sav로 0x34B30 호출(0x2D6EE). fwrite wrapper 0x340DC가 header (0x93618, 9, 1)을 0x2D702에서, records (0x9365C, 0x1A, 0x80)을 0x2D719에서 기록한다. close wrapper 0x34268은 0x2D724에서 호출한다. |
| 저장 호출자 | 0x2B11D, 0x2C21D | 두 곳 모두 CALL 0x2D6E4. 앞은 점수/이름/랭킹 처리 뒤, 뒤는 옵션 EXIT 경로다. |

DATA RESET의 루프는 0x2C188 에서 배열 시작 0x9365C를 설정하고 10×10, 총 100 행을 0x1A 간격으로 초기화한다. 따라서 전체 128 행을 읽고 쓰는 기능과 reset 100 행 범위는 구분해야 한다.

레코드 배열의 직접 주소 참조는 reset/group 설정 0x2C188, 0x2C256; score/ranking 경로 0x2D0B8, 0x2D207; writer 0x2D715; reader 후 그룹 cursor 설정 0x2EDBA, 0x2EEEE, 0x2EF26 에서 확인됐다. rows 100–127 을 선택하는 별도 group이나 direct consumer는 발견되지 않았다. 다만 비정상/범위 밖 헤더의 모든 검증을 증명하지 않았으므로 어떤 입력에서도 해당 행에 접근할 수 없다고 일반화하지 않는다.

CFGDAT에서 확인한 범위:

- 시작 때 디스크의 128 행 전부를 읽고, 저장 때 128 행 전부를 기록한다. DATA RESET은 첫 100 행만 다시 만든다.
- 기본 세이브의 추가 28 행은 모두 빈 행이 아니다. 110–112 행에 KRETON 점수가 있으나 출처/용도는 미확정이다.
- 알려진 난이도·reflect 그룹 및 랭킹 루프는 첫 100 행을 사용한다. 나머지 28 행을 미사용 또는 삭제 가능한 여분이라고 부를 근거는 없다.

점수 그룹의 인덱스 계산은 비교 함수 `0x2D588`과 랭킹 화면 구성 함수 `0x2D194`에서 같은 산식으로 확인했다. `CFGDAT` header byte 0은 난이도(0–4), byte 3은 REFLECT ATTACK(0–1)이다. 둘로 고른 그룹은 `difficulty + 5×reflect`이며 각 그룹은 10개 연속 26-byte 레코드다. 랭킹 화면 함수가 받는 추가 인자 0 또는 5는 그룹 번호가 아니라 그룹 안의 레코드 시작 순번이다. 이 함수는 한 번에 5개를 그리므로 0은 1–5위, 5는 6–10위 범위를 고른다. 파일 레코드 시작 주소는 `0x9365C + 0x104×(difficulty + 5×reflect) + 0x1A×rankOffset`이며 `rankOffset∈{0,5}`다. 고득점 비교 함수는 선택된 동일 그룹의 10개 기록을 훑는다. 따라서 DATA RESET의 10그룹×10레코드 초기화는 다섯 난이도와 REFLECT ATTACK의 두 값에 대응하는 첫 100개 레코드를 정확히 덮는다. 남은 28개 레코드가 다른 버전/용도로 읽히는지는 전체 참조를 별도로 조사해야 한다.

CFGDAT 표본은 영문 ISO extent 1034, MD5 `21e852bd20b9563115138d847d7ccf39`다. 일본 ZIP에는 이 파일이 없다. 따라서 표본의 KRETON 행을 일본 원판 기본값으로 취급하지 않는다.

### 타이틀 선택과 옵션 메뉴

타이틀 선택 루틴 0x2BD0C는 입력 포트 번호를 받아 0x39008로 패드 바이트를 읽는다. 문자열 상수 0x3E0E8–0x3E104는 1PLAYER, 2PLAYER, 1P AND 2P, OPTION 네 항목이다. 옵션 항목을 고르면 0x2BF00이 설정 화면을 그리고 입력을 처리한다. 두 함수 모두 선택 문자를 0x26C9C의 게임 SPR 문자 루프에 전달한다.

설정 메뉴는 인덱스 0–8을 사용한다. 항목별 제목·표시값과 실행 이미지에서 확인한 값 표는 다음과 같다.

| 인덱스 | 제목 문자열 | 표시값 소스·확인된 동작 |
|---:|---|---|
| 0 | GAME LEVEL | 0x3E10C부터 VERY EASY, EASY, NOMAL, HARD, VERY HARD 다섯 값 |
| 1 | LEFT | 0x3E39C의 %d 형식으로 수치 표시. 기본 CFGDAT 헤더의 값은 4 |
| 2 | AUDIO | STEREO / MONO |
| 3 | REFLECT ATTACK | NO / YES |
| 4 | AUTO SLOW DOWN | OFF / ON |
| 5 | QUIT GAME | OFF / ON. ON은 정리 함수 `0x2B61C`를 부른 뒤 옵션 처리기의 공통 반환 경로로 이어진다. README.DOC의 종료 설명과 바이너리 흐름은 일치하지 않으며, DOS 종료 지점은 미확정이다. |
| 6 | WAIT | `CFGDAT.SAV` 헤더 byte 7을 사용한다. 문자열 표에는 `FULL`, `HARF`, `3`–`8`의 8개 레이블이 있지만, 메뉴 초기화가 이 항목의 선택 범위를 0–1로 설정하므로 정상 메뉴 조작에서 도달하는 것은 `FULL`과 `HARF`다. 나머지 여섯 레이블의 사용 경로는 미확정이다. |
| 7 | DATA RESET | NO / YES. YES 분기는 10개 그룹×10개 레코드의 점수표 기본값을 메모리에 다시 만든다. |
| 8 | EXIT | 옵션 화면에서 빠져나가며 CFGDAT 저장 함수 0x2D6E4를 호출한다. |

옵션 진입 때 `0x2ED88`은 저장된 9-byte 헤더 중 메뉴에 노출되는 값들을 3-byte `{현재값, 최소, 최대}` 레코드 8 개로 만든다. `0x2C267` 이후 렌더 경로가 선택값을 해당 헤더 byte에 다시 반영한다. 코드에서 복원한 매핑은 다음과 같다.

| 화면 항목 인덱스 | 항목 | `CFGDAT.SAV` 헤더 byte | 초기 허용 범위 |
|---:|---|---:|---:|
| 0 | GAME LEVEL | 0 | 0–4 |
| 1 | LEFT | 1 | 0–4 |
| 2 | AUDIO | 2 | 0–1 |
| 3 | REFLECT ATTACK | 3 | 0–1 |
| 4 | AUTO SLOW DOWN | 6 | 0–1 |
| 5 | QUIT GAME | 4 | 0–1 |
| 6 | WAIT | 7 | 0–1 |
| 7 | DATA RESET | 8 | 0–1 |
| 8 | EXIT | 해당 없음 | 선택값 레코드는 모두 0인 더미 |

헤더 byte 5 는 이 옵션 화면의 8 개 항목으로 복사되지 않는다. 또한 WAIT 레이블 배열은 8 개인데 메뉴 범위는 0–1 로 초기화된다. 현재 실행 흐름에서 2–7 이 선택되는 경로는 확인되지 않았으므로 레이블 잔존/다른 사용 여부를 미해결로 기록한다. 기본 `CFGDAT.SAV`의 byte 8 은 1 이므로 DATA RESET의 시작 표시는 `YES`에 해당할 수 있다. 이는 상수·선택 인덱스에 따른 해석이며, 실제 기본 화면 표시는 사용자가 확인한 런타임 결과와 구분한다.
옵션 인덱스 5(QUIT GAME)의 ON 분기는 처리기 `0x2BF00` 안의 `0x2C151`에서 정리 함수 `0x2B61C`를 부른다. 정리 함수는 `0x3A468`(EUP 내부 AH=03h 정지), `0x3392C`(5 개 EUP 슬롯의 동적 버퍼 정리), `0x3A444`(내부 서비스 AH=01h), `0x39198`(TBIOS 호출 묶음), `0x33CD4`(SPR AH=01h, AL=00h: 지정 스프라이트 정지), `0x34BF8(0)` 순서로 부르고 반환한다. 이어 옵션 처리기는 공통 후속 경로 `0x2C267`로 가서 행을 다시 그리고 현재 선택 결과를 반환한다. 함수 시작 때 EDI는 `0x100`이고 QUIT 행은 이를 덮어쓰지 않는다. 호출부 `0x2B66C:0x2BC5F–0x2BC97`는 반환값 8 일 때만 옵션을 닫고 로컬 상태 4 로 바꾸며, 값 8 은 행 8 EXIT의 경로가 설정한다. 따라서 정적으로 확인한 QUIT 행 경로는 정리 뒤 옵션 반환으로 이어진다. README.DOC의 “QUIT GAME=YES 후 A 버튼으로 프로그램 종료”와는 맞지 않는다. 행 5 경로에서 DOS INT 21h 종료 스텁 `0x34C26`으로 가는 명시 분기는 발견하지 못했으며, 프로세스 종료가 어디서 완성되는지는 미확정이다.


설정표는 `0x93628`부터 항목당 3-byte `{현재값, 최소, 최대}` 레코드로 접근한다. 메뉴 루프는 상하 입력으로 항목 0–8 을 순환시키고 좌우 입력으로 현재값을 경계 사이에서 순환시킨다. 로컬 패드 ABI 기준 UP/DOWN/LEFT/RIGHT 단독 입력은 active-low 값 `0xFD/0xFE/0xFB/0xF7`에 대응한다. 화면은 값에 맞는 수치/문자열을 선택해 `0x26C9C` SPR 경로로 출력한다. LEFT 선택값은 0–4 이며, 플레이어 초기화는 `CFGDAT.SAV` 헤더 byte 1 을 읽어 플레이어 레코드 `+0`에 `선택값+1`을 기록한다. 아래의 상태 처리·표시 경로에서 `+0`이 잔기 카운터로 쓰이는 것도 확인했다. 메뉴 항목별 확인/복귀 처리와 게임 중 이동·발사 상태로 이어지는 버튼 의미는 일부 미확정이다.

### CFGDAT 옵션값과 실행 경로의 연결

옵션표시 코드뿐 아니라 게임 런타임의 헤더 포인터 `0x93624` 참조를 따라 설정값이 소비되는 지점도 대조했다. 다음은 기계어의 직접 데이터 흐름으로 확인한 사항과 UI 이름을 바탕으로 한 해석을 구분한 기록이다.

| 헤더 byte | 옵션 | 확인된 소비 지점 | 정적 코드에서 확인되는 영향 |
|---:|---|---|---|
| 0 | GAME LEVEL | `0x24D1A`, `0x25815`, `0x2599E`, `0x26130`, `0x26FED`, `0x2F90C`, `0x2D084` 등 | 난이도 값으로 `0x3F6E8` 계열 표를 조회해 객체 디스크립터의 이동/경계 계열 필드와 스테이지 객체 파라미터를 결정한다. 같은 값은 점수표 레코드 묶음 인덱스에도 들어간다. 각 배열 항목이 실제 난이도에서 보이는 효과는 일부 미확정이다. |
| 1 | LEFT | `0x27858`, 계속 초기화 `0x277F4` | 선택값에 1을 더해 플레이어 레코드 +0에 기록한다. |
| 2 | AUDIO | 음향 공통 함수 `0x337B0` | 값이 1이면 세 번째 인자(좌우 위치/팬으로 쓰이는 값)를 `0x40`으로 강제해 중앙에 둔다. 이후 `0x392C8`, `0x392EC`, `0x392D8`, `0x392B0` 경로로 음향 명령을 전달한다. 이 실행 코드에서 MONO는 음향 위치를 중앙값으로 고정한다. |
| 3 | REFLECT ATTACK | 객체 생성 `0x27070`, 처리기 `0x32167`, `0x32412` | 새 44-byte 객체의 +8 필드에 `0x100 + 52×설정값`을 쓰며, 값 1이면 두 처리기에서 추가 방향 계산 `0x2753C` 분기로 들어간다. UI 이름과 이 분기는 부합하지만, 해당 객체가 화면에서 어떤 공격/반사 효과를 나타내는지는 ENE·PAT 도형 대조를 더 해야 한다. |
| 4 | QUIT GAME | 메뉴 인덱스 5 | 값 1에서 정리 루틴 `0x2B61C`를 부른 뒤 옵션 처리기의 공통 반환 경로로 진행한다. 옵션 호출부가 닫힘을 판정하는 반환값 8은 행 8 EXIT 경로가 설정한다. README.DOC에는 YES+A가 프로그램을 종료한다고 적혀 있지만, 현재까지 바이너리에서 행 5와 DOS 종료 스텁을 잇는 분기는 찾지 못했다. |
| 5 | 메뉴 미노출 | 확인된 헤더 포인터 참조에서 직접 접근 없음 | 읽기·쓰기·게임 동작의 의미를 아직 찾지 못했다. |
| 6 | AUTO SLOW DOWN | `0x270FC` | 값 1이고 객체 카운터 `0x3F710`이 8 이상이면 `0x33CD4`를 호출한다. 이 래퍼는 `AH=01h`로 `ES:[0x60]` SPR BIOS를 호출하고 `AL=02h`를 준다. FreeTOWNSOS의 [`SPR_JUMPTABLE`](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tgbios/HEADER.ASM#L470-L499)에서 AH=01h는 `SPR_DISPLAY`이며, AL=2는 CRTC 상태와 스프라이트 버스 BUSY 해제를 기다리는 분기([`SPR.C`](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tgbios/SPR.C#L66-L104))다. 따라서 부하 임계에서 스프라이트 하드웨어 준비를 기다리는 자동 감속 경로가 정적으로 연결된다. |
| 7 | WAIT | 메인 반복 경로 `0x2AF2E`, 보조 반복 경로 `0x2ECCB` | 저장값에 1을 더해 반복 지연 카운터에 넣는다. 메인 경로는 반복 끝에서 카운터를 감소시키며, 메뉴에서 선택할 수 있는 값은 0/1이다. 레이블 3–8은 현재 메뉴 범위에서 도달할 수 없다. |
| 8 | DATA RESET | 옵션 분기 `0x2C174` | 값 1이면 10개 그룹×10개 랭킹 레코드의 이름·점수를 메모리에서 다시 초기화한다. |

TBIOS 호출 벡터도 구별해야 한다. `ES:[0x20]`은 FreeTOWNSOS `HEADER.ASM`에서 EGB로 연결되고 `ES:[0x60]`은 SPR로 연결된다. 게임 래퍼 이름만 보고 이 둘을 혼동하지 않도록 실제 far-call 주소와 `AH` 점프표를 기준으로 분석했다.

DATA RESET의 실제 record writes와 저장 호출은 앞의 CFGDAT 읽기·쓰기 절에서 정리한다.

### 고득점 판정과 이름 입력


고득점 관련 함수 0x2D588은 현재 모드/플레이어에 대응하는 레코드 묶음의 기존 10개 점수와 새 점수를 비교하고 순위를 반환한다. 상위 10위 밖의 반환값 11이면 0x2C710은 이름 입력 화면을 열지 않는다. 1–10위이면 게임의 SPR 표시 경로로 이름 입력 화면을 만든다. 상위 호출은 0x2B002이며 두 플레이어를 각각 처리한다.

이름 입력 문자는 0x3E448 의 ASCII 표에서 온다. 표에는 숫자, 일부 구두점, 대문자, 공백 표식이 있고 런타임은 45 개 항목을 표시한다. 항목별 SPR AH=05h raw 속성값은 선택 문자에 0x50 을 더해 만들며, 0x33D48/0x33D7C로 위치·속성을 지정한다. 이 화면은 EGB 시스템 폰트 문자열 경로가 아니라 게임 SPR 속성 호출을 쓰는 문자표다.

입력된 이름은 플레이어별 8-byte 버퍼에 쌓인다. 완성 경로는 해당 점수 레코드의 이름 필드에 최대 8 bytes를 복사하고 점수·플레이어 관련 필드를 갱신한다. 이름 편집 중 입력 코드 0x3F는 완료 분기를 설정하고, 0x3E는 커서/길이 조정 분기로 간다. 두 문자의 화면상 의미와 패드 버튼 대응은 아직 사용자 상호작용 표로 확정하지 않았다. 순위 레코드 갱신은 메모리에서 이루어지고, 바깥 점수 처리 흐름의 저장 호출 0x2B11D에서 CFGDAT.SAV를 기록한다.

### 플레이어 상태·계속·GAME OVER

두 플레이어 관리 레코드는 각각 32-byte 간격의 `0x94368`와 `0x94388`에서 시작하고, 각 레코드 +4(주소 `0x9436C`, `0x9438C`)를 상태 코드로 읽는다. 공용 처리기 `0x2B127`는 플레이어 0과 1을 차례로 처리하고 상태 0–7을 점프표 `0x2B1A5`에서 각각 `0x2B1C5`, `0x2B1CF`, `0x2B1EB`, `0x2B1F5`, `0x2B203`, `0x2B4D1`, `0x2B60D`, `0x2B5B2`로 보낸다. 상태 번호 자체를 게임 개념으로 해석하지 않고, 문구 및 필드 변경과 연결된 경로만 아래에 이름 붙인다.

상태 4 처리기 `0x2B203`는 조이스틱을 읽고 `CONTINUE=`(`0x3E06C`), `CREDIT@@`(`0x3E078`), `%1d`(`0x3E084`)를 SPR 문자열 루프로 표시한다. 공용 크레딧 word는 `0x94372`다. 입력 함수 `0x39008`이 반환한 byte가 `0xBF`이고 크레딧이 양수일 때, cdecl 인자 `(playerIndex, 1)`로 `0x277F4`를 호출한다. 양쪽 상태가 모두 4인데 크레딧이 0 이하라면 플레이어 0 상태를 5로 바꾸고 EUP 슬롯 7을 시작한다.

상태 5 처리기 `0x2B4D1`는 스테이지 객체 풀 중 `0x91AB8`에서 시작하는 32 개 44-byte 레코드의 활성값을 내리고, `0x3E088`의 `GAME@OVER`를 SPR 문자열 루프로 표시한다. 일반 크레딧 소진 경로는 상태 4 처리기 `0x2B203`에서 두 관리 상태가 모두 4 인지 확인한 뒤 `0x2B217: SUB EDI,EDI`로 카운터를 0 으로 초기화하고 상태 5 를 설정한다. 공용 caller `0x2AEF1`은 EBX를 `0x2B127`에 넘기며, 처리기는 EDI를 증가시켜 EAX로 반환하고 caller는 값을 다음 pass에 다시 전달한다. 따라서 이 전이에서 상태 5 첫 처리 결과는 1 이고 1–180 이면 GAME OVER 처리를 계속한다. 181 에 도달하면 같은 객체 구간을 정리하고 양쪽 상태 주소에 6 을 기록한다. `0x2B127`의 별도 demo caller `0x2EC93`는 ESI=0x258 에서 시작해 반환값을 ESI에 보관하므로, 이 공용 처리기를 부르는 모든 경로에 0–181 범위를 일반화하지 않는다. 상태 12 경로의 `0x2AEDE`에도 EBX=`-1` 초기화가 있으나, 그 값이 state5 에 전달되는지는 별도 호출 경로를 따라야 한다. 이 값은 `0x2B127` 호출에 따라 증가하는 루프 카운터이며 화면 프레임/초로 환산된 값은 아니다. 상태 6 점프표 항목은 `0x2B60D: INC ESI; JMP 0x2B135`로 이어져 `CMP ESI,2` 이후 다음 플레이어/루프 종료 검사로 간다. 이는 `0x2B134` 명령 중간으로 진입하는 경로가 아니다. 메인 루프 `0x2AF50`–`0x2AF5B`는 `[0x9436C]`와 6 을 비교하고, P0 가 상태 6 일 때만 `0x2AF5D` 이후 사후 처리로 진입한다.

그 사후 처리 경로는 STAFF.EUP를 슬롯 0 으로 적재하고, 플레이어 상태별로 이름 입력 함수 `0x2C710` 및 계속/음악 조회 경로를 처리한 뒤 점수 파일 저장 `0x2D6E4`에 도달한다. 끝의 `0x2B122`는 호출이 아니라 같은 초기화 함수의 `0x2AADC`로 직접 점프한다. 그 지점부터 descriptor pool과 그래픽을 다시 초기화하고 PAL/PAT 로드 및 타이틀·메인 메뉴 준비 코드를 실행한 뒤 `0x2ABAF` 선택 루프로 이어진다. 즉 확인된 GAME OVER 흐름은 문구 표시 → 양 플레이어 상태 6 → STAFF.EUP/점수·이름 처리 → CFGDAT.SAV 기록 → 장면 초기화/선택 루프 복귀다. P3 런타임 종료 스텁으로 이어지는 호출은 이 경로에서 발견되지 않았다. 이 정적 제어 흐름만으로 복귀 직후 실제 화면에 어떤 문구가 보이는지는 단정하지 않는다.

상태 0·1·2·3 의 주요 갱신은 다음과 같다. 상태 0 은 `0x31AF8`에서 플레이어 관리 레코드 `+6` 호출 카운터를 증가시키고 `0x40`에서 상태 `+4`를 1 로 바꾸며 `+6`을 0 으로 초기화한다. 상태 1 처리기 `0x31CB8`도 `+6`을 증가시켜 `0x78`에서 상태 2 로 전환한다. 이 카운터를 화면 프레임/초로 환산할 증거는 없다. 상태 2 는 `0x2F0CC`의 반복 입력·이동 처리다. 상태 3 처리기 `0x28314`는 사망 후 단계를 처리한다. 정확한 장면 동작 이름은 화면 자산과 완전히 대조하지 않았다.

관리 레코드의 확인된 필드는 다음과 같다. `R[p]=0x94368+0x20*p`이며 `p`는 플레이어 0/1 이다.

| 오프셋 | 확인된 용도 | 근거와 경계 |
|---:|---|---|
| `+0` | 잔기 카운터 | `0x277F4`가 CFGDAT 헤더 byte 1+1을 기록하고, 사망 처리 `0x2864B–0x28650`에서 최초 사망 단계에 1회 감소한다. `0x27ADC`는 `R+0−1`을 `%d` 문자열로 그린다. |
| `+2` | 충돌/상태 자원 카운터 | 일반 충돌 분기에서 0이면 상태 3으로, 0이 아니면 상태 1로 보내고 카운터들을 초기화한다. class-4 객체 접촉 경로에서는 7까지 증가한다. UI/게임 규칙에서의 정확한 명칭은 미확정이다. |
| `+4` | 플레이어 상태 | `0x2B127`의 0–7 점프표 대상이다. 상태 3은 사망 처리, 4는 CONTINUE, 5는 GAME OVER, 6은 사후 정리 경로와 연결된다. |
| `+6` | 상태 0/1 호출 카운터 | 0→1은 `0x40`, 1→2는 `0x78`에서 전환 후 0으로 초기화한다. 상태 3에서도 증가하지만 60 카운트 전환은 장면 descriptor `+0x12`가 구동한다. 상태 4의 카운터라고 보지 않는다. |
| `+0x10` | 점수 | HUD에서 `0x3E5A0` 포맷으로 표시하고, `0x2D67D–0x2D695`에서 고득점 후보와 비교한다. class-4 객체의 조건부 접촉에서는 100점이 더해진다. |
| `+0x14`, `+0x18` | 점수 갱신 제어값과 타이머 | `0x2F143–0x2F161`에서 `+0x18`을 감소시키고 0이 되면 `+0x14`를 지운다. 점수 경로 `0x28800–0x28841`은 `+0x14`를 갱신하며, `0x2895B–0x28972`에서 특정 값일 때 되감고 `+0x18=0x24`를 설정한다. 충돌 함수는 이 필드들을 검사하지 않으므로 무적 타이머로 부를 근거가 없다. |
| `+0x1C` | 미확정 | 컨티뉴 초기화 때 `0x2FFF`를 기록하는 것만 확인했다. |

잔기 0/1 전환은 사망 단계에서 `0x286A8–0x28710`을 거쳐 `0x279B4`로 간다. `R+0==0`이면 상태 4(CONTINUE), 아니면 상태 0 으로 되돌린다. 공용 크레딧 word `0x94372`는 신규 게임에서 5 로 초기화하며, 상태 4 처리기 `0x2B203`는 입력 byte가 `0xBF`이고 크레딧이 양수일 때 `0x277F4(player,1)`을 불러 크레딧을 1 감소시킨다. 두 플레이어가 모두 상태 4 이고 크레딧이 0 이하이면 상태 5(GAME OVER)로 간다.

충돌 함수 `0x27F04`는 객체 사각형과 플레이어 sprite descriptors `0x91A08`/`0x91958`를 겹침 검사한다. 일반 객체 경로는 `0x27E74`에서 상태 2 인 플레이어만 고른다. 겹쳤을 때 해당 플레이어 `R+2==0`이면 장면 descriptor `+0x12=0`, 관리 상태 `R+4=3`, 카운터 `R+6=0`으로 바꿔 사망 처리를 시작한다. `R+2!=0`이면 `R+2`, `R+6`을 지우고 상태 1 로 되돌리며 효과음 `0x42/0x43`을 부른다. 객체 상태 `+0x10==4` 경로는 상태 1/2 플레이어와 별도 접촉 판정을 한다. 접촉할 때 `R+2<7`이면 `0x281D8` 뒤 값을 증가시키고, 7 이면 유지하며 `0x281D8`이 `R+0x10` 점수를 100 올린다. 이어 효과음 `0x44`와 객체 비활성화를 수행한다. 확인한 충돌 코드에서 별도 무적 플래그는 발견하지 못했다.

`0x277F4(playerIndex, 1)`은 `R[p]`의 `+0`에 잔기 초기값을 쓰고 `+2/+4/+6/+8`, `+0x10/+0x14`, `+0x0E`를 초기화한다. `+0x1C=0x2FFF`를 기록하고 크레딧 `0x94372`를 감소시킨다. 대응 장면 레코드의 초기 좌표·패턴·크기를 다시 쓰고 잔기 표시 함수 `0x27ADC(playerIndex)`를 호출한다. 따라서 컨티뉴는 선택 플레이어와 장면 상태를 재초기화하는 경로다.

## 문자·비트맵 출력 규약과 호출 레코드

### EGB 시스템 폰트 문자열과 BIOS 규약

게임 래퍼 `0x33C94`는 `EGB_SJISSTRING`(AH=60h)을 호출한다. [`HEADER.ASM`](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tgbios/HEADER.ASM), [`EGB.H`](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tgbios/EGB.H), [`EGBFONT.C`](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tgbios/EGBFONT.C)를 대조했다. 입력은 DS:ESI의 `{int16 x,y; uint16 len; uint8 str[]}`이고, len은 바이트 수다. Shift-JIS lead는 다음 바이트와 함께 SJIS→JIS→ROM 인덱스로 변환하고 그 외 바이트는 ANK ROM을 사용한다. 원래 ROM 글리프는 Kanji 16×16/32 bytes, ANK 8×16/16 bytes다.

게임은 AH=18h로 ANK와 Kanji의 화면상 셀을 모두 24×24 로 설정한다. 설정 주소는 `0x1D624/0x1D637`, `0x2665E/0x2666E`, `0x2D860/0x2D870`이다. EXP에서 EGB AH=17h 간격 setter는 발견되지 않았으므로 원본 parsed unit 전진은 24px다. `0x3AAFD`의 AH=17h는 FS:[0x80]의 SND Timer A restart이며 EGB spacing이 아니다.

확인한 ES:[0x20] EGB wrapper의 AH 값은 `00,01,02,04,05,06,07,0A,18,21,24,25,41,60`이다. `0x2AB1B → 0x33D20`의 AH=03h는 ES:[0x60] SPR 팔레트 설정이다. EGB viewport setter로 해석하지 않는다. EGB_RESOLUTION은 각 page viewport를 mode 크기로 초기화한다. 타일 초기화 mode 8 뒤 공용 helper `0x2A864`는 `(page0,page1)=(3,5)`를 설정한다. AH=05 WRITEPAGE wrapper `0x33B18`의 직접 CALL은 79 개이고 helper는 page 1 사용 후 page 0 을 복원한다(`0x2A891→0x2A8E5`). 엔딩 `0x1D681`, 스탭롤 `0x26793`, 오프닝 경로는 page 0 출력으로 연결된다.

mode 3 page 0 은 4bpp, VRAM size 1024×512, viewport `(0,0)..(1023,511)`이다. nominal visible size 640×480 과 실제 CRTC display-start는 viewport와 별개다. 스탭롤 row 0 의 y=512 는 viewport 아래 경계 밖에서 시작한다. 알려진 AH=60 상단 clip 계산 오류는 이 viewport의 minY=0 에서는 발동하지 않는다. EXP에서 AH=19 style setter도 발견되지 않았다.

원본 날짜 레코드는 raw P3 `0x3E910`→runtime `0x3E700`, x=80,y=200,len=40 이다. 사용자 디버거의 `0x2DBED → 0x33C94`가 이 레코드를 전달한다. 일본판 `西暦２１９２年`, 영문판 `２１９２ Ａ．Ｄ．`은 함수의 `0xAC0`-byte 스택 복사 버퍼를 거쳐 출력된다.

AH=60 width prepass는 SJIS trail을 추가 셀로 세어 `page->textX`를 과대 증가시킬 수 있다. 그러나 게임 wrapper는 BIOS 복귀 후 AH를 EAX에 부호 확장하며, EAX는 픽셀 너비로 사용되지 않는다. 로컬 FreeTOWNSOS에서 `page->textX` reader는 찾지 못했다. gateway 복원과 AH=02 디버거 캡처를 근거로 AH=60 의 정적 예상 EAX는 `0x60`이며 이를 오류값이라고 단정하지 않는다.

AH=23 비트맵은 확대율이 적용되지 않는 1bpp 소스다. 24×24 입력은 행당 3 bytes/총 72 bytes지만 대상 화면의 색상 모드는 별개다. descriptor의 data far pointer는 +0/+4, 시작 x/y는 +6/+8, 끝 x/y는 +0xA/+0xC다. y는 문자열 글리프 하단 기준이므로 배치 계산에 이 차이를 반영해야 한다. AH=60 의 24×24 확대 루틴은 drawingMode를 무시하고 전경색 set-bit를 써 PSET처럼 동작한다. EXP의 AH=0Ah 직접 setter 14 개 중 초기 MATTE(6) 1 개 외 13 개는 PSET(0)이고 `0x2A795/0x2A875` 초기화도 PSET으로 설정한다. 해당 정적 스크립트 경로의 AH=23 은 기존 전경색/PSET 동작을 사용한다. 원본 TownsOS 호환 호출에는 매번 DS:EDI에 게임 작업 버퍼를 전달해야 한다.

외부 FNT는 원본 EGB가 자동으로 적재하지 않는다. 구현한 조합 토큰 파싱·FNT 적재·AH=23 호출·ABI 보존·양 OS 검증은 [한글 빌드](Alltynex-Korean-Build.md)에 통합한다.

### EGB 레코드 저장과 호출 매핑

물리 레코드 stride는 `0x56`(86 bytes): x/y/len 머리글 6 bytes와 str 저장 80 bytes다. 비교 입력의 len은 모두 40 이므로 앞 40 bytes만 소비하고 나머지 40 bytes는 tail이다. FreeTOWNSOS는 len 안의 NUL에서도 종료하지 않고 ANK code0 으로 처리한다. 로컬 CompROM `FMT_FNT.ROM`의 ANK16 code0 offset `0x3D800` 16 bytes는 모두 0 이다. BIOS는 selector0138h를 사용하지만 그 ROM 파일의 실제 selector 매핑은 런타임에서 직접 확인하지 않았다. `81 40`의 JIS2121h/ROM offset0x420 32 bytes도 로컬 파일에서 0 이지만 실제 매핑 검증과 구별한다.

118 개 물리 슬롯(엔딩 6+스탭롤 80+오프닝 32), 비공백 문구 합집합 74 행, 래퍼 직접 CALL 58 개는 서로 다른 수량이다. 일본 원본 ZIP의 EXP를 압축 해제하여 오프닝 표의 45 개 주소 모두 E8 rel32 와 목적지 0x33C94 를 확인했다. 코드 0..0x3B000 의 전체 대조도 엔딩 12 개·스탭롤 1 개·오프닝 45 개, 합계 58 개였다. 기존 57 개 집계는 이 대조 결과에 따라 정정한다.

그룹별로 원본 테이블을 스택에 복사하므로 AH=60 입력 포인터를 고정 원본 주소와 비교하면 현재 행을 식별하지 못한다. 공용 wrapper의 첫 인자는 작업 버퍼, 둘째는 레코드이며 호출자가 인자 스택을 정리한다. 첫 6 bytes `56 57 8B 7C 24 0C`의 명령 경계를 패치 진입점으로 사용했다. 레코드 내용 식별 구현은 빌드 문서에서 다룬다.


### 호출 그룹 및 초기 후보 집계

| 그룹 | `MOV ESI` immediate / `REP MOVSD` | 런타임 원본 | raw EXP 대응 | 레코드 수·간격 | 초기 호출 후보 수 |
|---|---:|---:|---:|---:|---:|
| 엔딩（초기 기록명: 인트로/스테이지 안내） | `0x1CB7E` / `0x1CB8E` | `0x3C20C` | `0x3C41C` | 6개 × `0x56` (86 bytes) | 12 |
| 크레딧 | `0x26714` / `0x26720` | `0x3C4A8` | `0x3C6B8` | 80개 × `0x56` | 1개 반복 callsite |
| 스토리/날짜 | `0x2D740` / `0x2D750` | `0x3E700` | `0x3E910` | 32개 × `0x56` | 45 |

스탭롤은80개 슬롯 중 현재 행 인덱스로 레코드를 선택하는 반복 호출이다. 엔딩 표의12개는 조건 분기별 대안이므로 한 번의 실행에서 전부 호출된다는 뜻이 아니다. 오프닝 표는 조건·반복을 포함한 초기 호출 후보 수다.

### 엔딩: 6개 레코드, 12개 직접 CALL

엔딩 그룹의 `MOV ESI,0x3C20C` 명령은 `0x1CB7D`에서 시작하며 immediate 주소는 `0x1CB7E`; 대응 `REP MOVSD`는 `0x1CB8E`이다. 이 복사로 `6 × 0x56 = 0x204` bytes가 함수 로컬 `[EBP-0x5640]`으로 이동한다. `0x1CB80`은 명령 경계가 아니므로 복사 지점으로 쓰지 않는다. raw EXP의 테이블 시작은 `0x3C41C`이다. 각 callsite는 로컬 시작 주소에 레코드 인덱스의 `0x56`배를 더해 넘긴다.

| 인덱스 | raw EXP 레코드 | runtime callsite |
|---:|---:|---|
| 0 | `0x3C41C` | `0x1D6E8`, `0x1D712` |
| 1 | `0x3C472` | `0x1D734`, `0x1D780` |
| 2 | `0x3C4C8` | `0x1D745`, `0x1D791` |
| 3 | `0x3C51E` | `0x1D756`, `0x1D7A2` |
| 4 | `0x3C574` | `0x1D7C4`, `0x1D7FC` |
| 5 | `0x3C5CA` | `0x1D7D5`, `0x1D80D` |

따라서 문자열 번역 코드와 글리프 표는 현재 레코드 포인터에서 읽을 수 있다. 선택되지 않은 분기 레코드도 EXP 안에 있으므로 번역본에는 전체 관련 텍스트를 기록해야 한다.

### 크레딧: 80개 레코드, 동적 행 포인터

크레딧 그룹의 `MOV ESI,0x3C4A8` immediate는 `0x26714`, 대응 `REP MOVSD`는 `0x26720`이다. 이 복사로 `80 × 0x56 = 0x1AE0` bytes가 `[EBP-0x5600]`으로 이동한다. raw EXP 테이블 시작은 `0x3C6B8`이다. 단일 AH=60 callsite `0x267C8`에서 counter `[0x3F3DC]`를 `0x56`과 곱해 로컬 시작 주소에 더한 뒤 그 행을 전달한다.

```text
runtime local record = [EBP-0x5600] + [0x3F3DC] * 0x56
raw EXP record      = 0x3C6B8 + [0x3F3DC] * 0x56
```

이 그룹은 호출 주소별 분류가 아니라 실제 전달되는 레코드의 코드쌍을 기준으로 번역·글리프 매핑해야 한다.

### 오프닝/날짜: 32개 레코드, 45개 호출 지점

오프닝 그룹의 `MOV ESI,0x3E700` immediate는 `0x2D740`, 대응 `REP MOVSD`는 `0x2D750`이다. 이 복사로 `32 × 0x56 = 0xAC0` bytes가 `[EBP-0x5604]`로 이동한다. raw EXP 테이블 시작은 `0x3E910`이다. callsite가 넘기는 포인터는 로컬 시작 주소와 정적 레코드 인덱스의 합이다.

| 인덱스 | raw EXP 레코드 | runtime callsite |
|---:|---:|---|
| 0 | `0x3E910` | `0x2DBED` |
| 1 | `0x3E966` | `0x2DD69`, `0x2DDA2` |
| 2 | `0x3E9BC` | `0x2DD76`, `0x2DDAF` |
| 3 | `0x3EA12` | `0x2DDBC` |
| 4 | `0x3EA68` | `0x2DDD6`, `0x2DDFD` |
| 5 | `0x3EABE` | `0x2DFFF`, `0x2E038` |
| 6 | `0x3EB14` | `0x2E00C`, `0x2E045` |
| 7 | `0x3EB6A` | `0x2E052` |
| 8 | `0x3EBC0` | `0x2E06C`, `0x2E0AA` |
| 9 | `0x3EC16` | `0x2E079`, `0x2E0B7` |
| 10 | `0x3EC6C` | `0x2E0C4` |
| 11 | `0x3ECC2` | `0x2E268` |
| 12 | `0x3ED18` | `0x2E275` |
| 13 | `0x3ED6E` | `0x2E282` |
| 14 | `0x3EDC4` | `0x2E23C` |
| 15 | `0x3EE1A` | `0x2E2B1`, `0x2E2EA` |
| 16 | `0x3EE70` | `0x2E2BE`, `0x2E2F7` |
| 17 | `0x3EEC6` | `0x2E311`, `0x2E37E` |
| 18 | `0x3EF1C` | `0x2E3EA` |
| 19 | `0x3EF72` | `0x2E3F7` |
| 20 | `0x3EFC8` | `0x2E404` |
| 21 | `0x3F01E` | `0x2E411` |
| 22 | `0x3F074` | `0x2E4AB`, `0x2E527` |
| 23 | `0x3F0CA` | `0x2E4BF`, `0x2E534` |
| 24 | `0x3F120` | `0x2E4D0`, `0x2E541` |
| 25 | `0x3F176` | `0x2E55B`, `0x2E717` |
| 26 | `0x3F1CC` | `0x2E568`, `0x2E724` |
| 27 | `0x3F222` | `0x2E578`, `0x2E731` |
| 28 | `0x3F278` | `0x2E787` |

현재 근거로 스토리 표의 32개 슬롯 가운데 29개만 이 초기45개 호출 후보에서 참조 대상으로 분류됐다. 나머지 세 슬롯의 사용 여부는 이 매핑만으로 주장하지 않는다.

### 공용 SPR 문자 루프: 타이틀·스테이지 안내·메뉴

`0x26C9C`는 문자열 포인터 EDI를 받아 바이트를 하나씩 읽는다. NUL에서 끝내고 `0x40` (`@`)은 별도 공백 처리 경로로 보낸다. 일반 ASCII 문자는 코드값에 `0x50`을 더해 SPR AH=05h에 넘길 raw 속성값을 만든 다음, AH=04h 위치 설정 래퍼 `0x33D48`과 AH=05h 속성 설정 래퍼 `0x33D7C`를 호출한다. 이 루프는 타이틀 전용이 아니다. 실행 이미지 전체에서 66개의 직접 CALL 지점이 확인됐다.

| 장면 | 호출 주소 → 문자열 위치 | 문자열 바이트(공백 표시는 `@`) |
|---|---|---|
| 타이틀 | `0x2DB94` → `0x3F1FC` | `PROJECT@RAID@WIND@2` |
| 1구역 | `0x5E9`, `0x619`, `0x6F0`, `0x715` | `FIRST@AREA`, `MAKE@AN@ASSAULT@ON@ENEMY`, `TARGET@DESTROYED`, `FIRST@AREA@IS@OVER` |
| 2구역 | `0x5F60`, `0x5F90`, `0x6067`, `0x608C` | `SECOND@AREA`, `ATTACK@THE@ZLDYZANT@BASE`, `TARGET@DESTROYED`, `SECOND@AREA@IS@OVER` |
| 3구역 | `0xAFAD`, `0xAFDD`, `0xB0B4`, `0xB0D9` | `THIRD@AREA`, `THE@BITING@COLD@WIND`, `TARGET@DESTROYED`, `THIRD@AREA@IS@OVER` |
| 4구역 | `0x13CB5`, `0x13CE5`, `0x13DBC`, `0x13DE1` | `FORTH@AREA`, `LAST@DEFENCE@LINE`, `TARGET@DESTROYED`, `FORTH@AREA@IS@OVER` |
| 최종 구역 | `0x1CC17`, `0x1CC47`, `0x1CD11`, `0x1CDBB`, `0x1CDE0` | `FINAL@AREA`, `AGGRESSIVE@ATTACK`, `TARGET@DESTROYED`, `FINAL@TARGET`, `ALLTYNEX` |
| 전환 UI | `0x2AE3D` | `NOW@LOADING` |

기존 P의 ASCII 0x50 에 게임이 0x50 을 더해 SPR AH=05h 직전 ESI=0xA0 으로 전달되는 것이 Tsugaru 로그에서 확인됐다. `PRINT SPRPTN4 0xA0`의 패턴 RAM 내용 128 bytes는 `ALLTY_1.PAT` 파일 오프셋 0x1000(등록 시작 0x80 + 0x20 patterns)과 일치하고, 사용자가 올린 화면에는 `PROJECT`의 P가 실제로 보인다. 따라서 이 실행에서 타이틀 P의 raw value 0xA0 와 pattern entry 0xA0 은 일치한다. FreeTOWNSOS 자체 테스트 [`sprite01.c`](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tests/tgbios/sprite01.c)도 `SPR_define(..., ptnNum=128, ...)`와 `SPR_setAttribute(..., attrib=128, ...)`를 짝지어 사용해 같은 번호 관례를 보여 준다. 다만 [`SPR.C`](https://github.com/captainys/FreeTOWNSOS/blob/b72f4066b20b08d78fbfaf876e4f629c77cbb56f/tgbios/SPR.C)의 AH=05h 구현은 ESI를 attribute RAM에 그대로 기록하므로, 임의의 16-bit attribute의 비트 분해/하드웨어 fetch 규칙까지 소스에서 복원한 것은 아니다. 이 근거로 게임의 `0x280+ID`와 PAT 시작 번호 `0x280`은 같은 번호 관례를 따르는 것으로 강하게 지지되며, 객체별 ID와 도형 이름·상위 attribute 비트 의미는 미확정이다.

### 화면 출력 경로의 구별

`M*_3`는 32K DAT 512-byte 타일→EGB AH=25h이고 `M*_1/_2`는 raw `0x280+ID`→SPR 위치/속성 호출이다. 앞의 파일 적재·M 소비 절에서 함수·인자·파일별 후보 범위를 정리한다. 같은 화면에 표시되어도 일반 문자열, UI 문자, 배경 타일과 객체 스프라이트는 서로 다른 입력 자료와 API를 사용한다. `32K_*.DAT`의 16-bit 원시값이 RGB555/RGB565 중 어느 형식인지 아직 확정하지 않았다.

## 프레임/상태 흐름과 스테이지 이벤트 자료

### 타이틀 진입 후 메인 상태 디스패처

초기화 `0x2AA54`는 Free386의 P3 진입 스텁에서 호출된다. 초기 장면 선택 루프 `0x2ABAF`가 오프닝·타이틀·데모·입력 대기 경로를 거친 뒤 `0x2ADBA`의 상태 디스패처로 들어간다. 디스패처는 전역 `[0x8EEF4]`에서 1을 빼고, 값이 0–12이면 0x2ADCE의 13-entry 점프 테이블을 사용한다. 유효 범위를 벗어나면 공통 루프 꼬리 `0x2AEEB`로 간다.

초기 장면 선택 루프의 데모 분기(`0x2AC1B`)는 `PLAYDEMO.DAT`을 `rb`로 열어 `0xA4EB4` 버퍼에 원소 크기 4 × 원소 수 `0x1000`의 읽기 요청을 보내고, 재생 커서 `0xA8EB4`를 0 으로 초기화한 뒤 모드 word `0x94374`를 1 로 설정한다. 이어 `0x2EC0C`를 호출한다. 이 루틴은 플레이어 0 의 시작 처리(`0x277F4(0,0)`), 플레이어/화면 초기화, 구역 처리기 `0x550` 1 회 호출 후 `0x27D18` 렌더와 `0x2B127` 플레이어 처리를 반복한다. 루프에서 입력 함수 `0x39008`로 포트 0 과 1 을 읽고, 반복 계수는 3,600 까지 센다. 둘 중 하나가 `0xFF`가 아니거나 플레이어 0 상태가 3 이상이면 반환값 0, 그 조건 없이 3,600 에 도달하면 반환값 2 를 둔다. 호출자는 반환값을 선택 루프 변수 `ESI`에 옮기고 다음 반복에서 메뉴/전환 분기를 다시 고른다. 데모 DWORD 소비는 플레이어 처리기 `0x2F0CC`에서 이뤄지며 뒤의 재생 cursor 절에서 다룬다. 실제 패드 wrapper `0x39008` 자체가 데모 배열을 읽는 것은 아니다.

메인 상태기 진입은 별도 경계다. 선택 루프에서 `EDI >= 0`이 되면 `0x2ACF7` 초기화로 가서 표시 상태를 정리하고 공통 카운터 `0x2B648`을 호출한 뒤 `0x8EEF4=1`로 설정한다. 그 다음부터 `0x2AD88` 반복 루프에서 매 반복마다 입력/표시 보조 처리 뒤 `0x2ADBA` 디스패처를 실행한다. 따라서 `0x2EC0C`의 데모 준비·대기는 상태 1–13 스테이지 진행 루프와 분리되어 있다.

| 전역 상태 `[0x8EEF4]` | 테이블 분기 주소 | 확인된 작업 |
|---:|---:|---|
| 1 | `0x2AE4A` | 스테이지 1 처리기 `0x550` 호출 |
| 2 | `0x2AE02` | 전환 처리, 상태 증가, `NOW@LOADING`을 공용 SPR 문자 루프로 표시 |
| 3 | `0x2AE5E` | 스테이지 2 처리기 `0x5ED0` 호출 |
| 4 | `0x2AE02` | 공용 전환 처리 |
| 5 | `0x2AE68` | 스테이지 3 처리기 `0xAF18` 호출 |
| 6 | `0x2AE02` | 공용 전환 처리 |
| 7 | `0x2AE72` | 스테이지 4 처리기 `0x13C20` 호출 |
| 8 | `0x2AE02` | 공용 전환 처리 |
| 9 | `0x2AE79` | 스테이지 5 처리기 `0x1CB38` 호출 |
| 10 | `0x2AE02` | 공용 전환 처리 |
| 11 | `0x2AE80` | 전역 난이도/모드 필드 2곳을 7로 설정하고 최종 처리기 `0x26704` 호출 |
| 12 | `0x2AE97` | 표시/SPR 상태 정리, 관련 초기화 호출, 상태 증가 |
| 13 | 0x2AEEB | 공통 루프 꼬리로 직행 |

점프 테이블은 정확히 13개 엔트리다. 디스패처는 상태값에서 1을 뺀 뒤 0–12 범위를 검사하므로 전역 상태 1–13이 각각 테이블 항목에 대응한다. 상태 13은 범위 밖이 아니다. 상태 0 또는 14 이상이면 테이블을 건너뛰고 공통 루프 꼬리로 간다.

공용 전환 처리 `0x2AE02`는 `0x28E4C`, `0x2B648`을 부르고 `[0x8EEF4]`를 증가시킨다. 이어 점수/상태 전역값을 갱신하고 `0x3E054`의 `NOW@LOADING`을 `0x26C9C`로 그린다. 공통 꼬리 `0x2AEEB`는 게임 루프/입력·표시 보조 함수들을 이어 호출한다. 이는 관찰된 분기 일부를 복원한 것이며 옵션 메뉴의 모든 선택 경로와 각 스테이지 내부 종료 조건까지 완성한 호출 그래프는 아니다.

전역 상태 12의 정리 handler `0x2AE97`는 두 플레이어의 관리 레코드 `+4`를 6으로 설정하고 `[0x8EEF4]`를 13으로 증가시킨 뒤 공통 꼬리로 fall-through한다. 이 때문에 다음 루프의 P0 player-state 6 검사가 GAME OVER 후처리로 진입한다. 후처리는 점수/이름 및 저장 처리를 마친 뒤 `0x2AADC`로 직접 점프하여 pool·그래픽·타이틀/메뉴 준비를 다시 하고 선택 루프로 간다. 전역 상태 13은 자체 장면 handler나 프로세스 종료가 아니며 점프 테이블에서 공통 꼬리 `0x2AEEB`로 보낸다. 이 전역 장면 상태값과 플레이어 관리 레코드의 state 6은 서로 다른 값/역할이다. 스테이지 처리기들이 전역 상태를 증가시키는 명령 주소는 정리했지만, 각 분기에서 왜 종료하는지에 대한 전체 조건과 이를 게임 규칙상 ‘클리어’라고 부를 수 있는지는 아직 닫히지 않았다.

상태 선택자 0x8EEF4와 별도로, 스테이지 처리기들은 전역 0x8EE94를 읽고 변경한다. 이 값은 스테이지 1–5 진입 때 0이면 각 구역 전용 초기화 함수(각각 0x0000, 0x5C30, 0xAC44, 0x13A1C, 0x1C8AC)를 호출하고, 149 미만 구간에서 공통으로 안내 문구와 32개 객체 항목을 다룬다. 이후에도 값은 스테이지별 조건에 따라 증가하며, 200–320 구간에 추가 안내/전환 처리가 있고, 스테이지 5에는 400–520 구간도 있다. 증가가 각 처리기 안의 특정 분기에 배치되어 있으므로 이를 단순한 ‘프레임 수’로 부르지 않고 스테이지 내부 진행 카운터로 기록한다.

장면 상태 0x8EEF4의 실제 증가 지점도 코드에서 찾았다. 홀수 상태의 각 게임 구역 처리기가 상태를 다음 전환 상태로 넘기고, 공통 NOW LOADING 처리기가 그 사이 상태를 다음 홀수 상태로 넘긴다. 아래 주소는 증가 명령 위치다. 이 분기 조건들이 모두 ‘스테이지 클리어’인지 ‘게임오버’인지까지는 아직 각각 확정하지 않았다.

| 상태 진행 | 증가 명령 주소 | 증가를 실행하는 처리기 |
|---|---:|---|
| 1 → 2 | 0x000D8E | 구역 1 처리기 0x550 |
| 2 → 3 | 0x2AE0C | 공통 전환 처리기 0x2AE02 |
| 3 → 4 | 0x06573 | 구역 2 처리기 0x5ED0 |
| 4 → 5 | 0x2AE0C | 공통 전환 처리기 0x2AE02 |
| 5 → 6 | 0x0B829 | 구역 3 처리기 0xAF18 |
| 6 → 7 | 0x2AE0C | 공통 전환 처리기 0x2AE02 |
| 7 → 8 | 0x14B04 | 구역 4 처리기 0x13C20 |
| 8 → 9 | 0x2AE0C | 공통 전환 처리기 0x2AE02 |
| 9 → 10 | 0x1D829 | 구역 5 처리기 0x1CB38 |
| 10 → 11 | 0x2AE0C | 공통 전환 처리기 0x2AE02 |
| 11 → 12 | 0x268CF | 최종 구역 처리기 0x26704 |
| 12 → 13 | 0x2AEE2 | 정리 처리기 0x2AE97 뒤 공통 루프 꼬리 |

장면 전환 주소는 확인했지만, 전환 원인이 전부 스테이지 함수 안의 한 비교문에 있는 것은 아니다. 추가 교차참조 결과 `0x8EE8C`는 구역별 내부 점프표 선택자이며, 구역 처리기뿐 아니라 객체 상태/소멸 처리 코드도 이 값을 바꾸는 것을 확인했다. 그러므로 아래 주소표를 사용자 화면의 “클리어” 명칭과 바로 등치하지 않는다.

### 최종 구역 처리기와 크레딧 문자열 테이블

메인 상태 11은 `0x2AE80`에서 최종 처리기 `0x26704`를 부른다. 이 처리기의 첫 진입 초기화 `0x2650C`는 `ENE_6.DAT` 16,000 bytes를 `0x7222C`에, `ROLL_G.PAT` 49,152 bytes를 `0x4222C`에 적재한다. 후자는 SPR 시작 번호 `0x280`, AL=0(16색), DH=16, DL=24, 원본 `0x4222C`로 등록된다. FreeTOWNSOS `SPR_DEFINE`는 16색 패턴당 128 bytes를 복사하고 DH×DL개를 처리하므로 총 384개, 49,152 bytes가 된다. 이는 `ROLL_G.PAT` 파일 크기와 정확히 일치한다. 초기화는 `STAFF.EUP`을 EUP 슬롯 0으로 `0x33514`에 넘기고, 같은 이름을 `0x33348`에도 전달한다. 후자는 EUP 헤더에 저장된 보조 파일 stem을 읽어 해당 FMB/PMB 자료를 여는 코드다. 앞의 EUP 보조 리소스 절에서 일본 원판 파일과의 대응 및 파서 입력 구조를 확인했다. 이어 `0x33730(0)`이 슬롯의 제어 배열을 내부 EUP 서비스에 전달한다.

최종 처리기 `0x26704`는 초기화 때 런타임 이미지 주소 `0x3C4A8`의 6,880 bytes를 로컬 버퍼로 복사한다. 이에 대응하는 압축 P3 EXP raw 파일 범위 시작은 `0x3C6B8`이다. 길이는 정확히 80 개의 86-byte 레코드다. 각 레코드는 `{int16 x, int16 y, uint16 len, uint8 str[80]}`로 읽히며 로컬 FreeTOWNSOS `EGB.H`의 `EGB_String`과 같은 앞부분 레이아웃이다. 모든 항목의 len은 40 bytes이고, 문자열은 영문판에서 Shift-JIS 전각 ASCII로 저장돼 있다. 레코드 주소 준비는 기존 기록의 `0x267C2` 부근이며 실제 래퍼 직접 CALL은 `0x267C8`이다. 래퍼는 EGB AH=60h(`EGB_SJISSTRING`)로 그대로 넘긴다. 로컬 FreeTOWNSOS의 EGB AH=60h 경로는 해당 문자열을 이 OS 구현의 시스템 폰트 ROM 조회에 전달한다.

비어 있지 않은 레코드의 인덱스·위치·텍스트는 다음과 같다. 빈 레코드도 좌표 간격과 스크롤 순서를 유지하므로 단순 삭제하면 안 된다.

| 레코드 | (x, y) | 영문 텍스트 |
|---:|---:|---|
| 0 | (92, 512) | PROJECT RAID WIND 2 |
| 1 | (92, 32) | ALLTYNEX |
| 3 | (80, 96) | STAFF |
| 8 | (80, 256) | ORIGINAL CONCEPT |
| 10, 16 | (80, 320), (80, 512) | Satoshi Yoshida |
| 13 | (80, 416) | GRAPHICS, VIDEO, AND |
| 14 | (80, 448) | PROGRAMMING |
| 19 | (80, 96) | VOICE EFFECTS |
| 21 | (80, 160) | Y. Uemura (YASUWARE) |
| 24 | (80, 256) | SOUND EFFECTS |
| 26 | (80, 320) | Mitsuru Takaya |
| 29 | (80, 416) | SUPERVISION |
| 31 | (80, 480) | Takayuki Iida |
| 34 | (80, 64) | COLLABORATORS |
| 36–44 | y=128–384, 32 간격 | Takayuki Iida; Naoya Irie; Yuji Suzuki; Mitsuru Takaya; Ryuji Nishikawa; Daisuke Hashimoto; Hirofumi Hirose; Nobuji Mukai; Toru Muneyuki |
| 49 | (80, 32) | ENGLISH TRANSLATION |
| 51 | (80, 96) | Derek Pascarella |
| 52 | (80, 128) | (a.k.a. “ateam”) |
| 54 | (80, 192) | Walnut |
| 68 | (80, 128) | PRODUCED AND CREATED |
| 70 | (80, 192) | BY SATOSHI YOSHIDA |

이 크레딧 표에도 `PROJECT RAID WIND 2`가 있지만, 주 타이틀 화면의 같은 문구는 별도 문자열 `0x3F1FC`를 `0x26C9C` SPR 문자 루프로 그린다. 따라서 크레딧 레코드가 EGB 경로라는 사실을 주 타이틀의 렌더 경로에 일반화하지 않는다.

최종 처리기 내부 선택자 [`0x8EE8C`]의 0–3 분기는 다음과 같이 이어진다. 0은 위 80행 표와 배경/스크롤 갱신을 진행한다. 1은 0x3A4C4(내부 EUP AH=06h) 조회를 반복하고 반환값이 0일 때 2로 넘어간다. 조회값은 곡의 자체 종료 코드가 아니라 스트림 활성 표시 [`0xCFD9A`]다. STAFF.EUP의 FE 이벤트가 [`0xCFD9B`]를 세우고, 지연 큐 [`0xCFDA4`]가 비워진 뒤 주기 처리기가 스트림을 중지해 활성 표시를 지우는 경로를 확인했다. 따라서 이 폴링과 자연 종료의 연결은 EUP 파서/스케줄러를 통해 정적으로 닫힌다. 2는 별도 카운터를 120까지 올린다. 3은 [`0x3FC20`]=0x119를 기록하고 메인 상태값 [`0x8EEF4`]를 증가시켜 다음 메인 상태로 보낸다. 이 뒤 상태 12의 정리 루틴은 EUP 슬롯·객체/표시 상태를 정리하고 상태 13으로 진행한다.

최종 처리기는 크레딧 출력 이외에도 `0x90148`부터 44-byte 간격의 객체 레코드 96 개를 훑는다. `[0x8EEE8]`은 `0x2650C`에서 `ENE_6.DAT` 버퍼 `0x7222C`로 설정되고, 이 루프는 호출 1 회마다 바이트 16 개를 순서대로 읽어 포인터를 16 칸 전진시킨다. 실제 `ENE_6.DAT` 16,000 bytes는 0 으로 채워져 있고 `0x2F6`에만 `01`이 있다. 따라서 ENE 입력 배치 48 번째의 내부 인덱스 6 에서 opcode1 이 들어온다. 하위 4 비트 gate가 입력 배치 실행을 제한하므로 이 수치를 최종 처리기 호출 48 회로 해석하지 않는다. 이벤트 분기는 현재 첫 미사용 객체 블록의 디스크립터를 설정한다: 좌표 필드 x=0, y=0x1800(위치 API가 6 비트 고정소수점을 적용해 y=96), 격자 8×6, `+0x0A=0x280`, `+0x08=0x01D6`, 상태 10, 활성값 1. `SPR_SETPOSITION`은 `806 + 현재 할당 오프셋`을 시작 슬롯으로 삼아 8×6 위치를 배치한다. `SPR_SETATTRIBUTE`는 같은 스프라이트 레지스터 범위에 raw attribute 시작값 `0x280`, color-table 값 `0x81D6`을 쓴다. `ROLL_G.PAT`가 시작 번호 `0x280`으로 384 개를 등록하므로 수치 체계가 정렬되고, 타이틀 P의 raw `0xA0` 사례도 같은 번호가 대응하는 실제 패턴을 확인해 준다. 다만 이 최종 객체의 `0x280` 블록이 화면에서 실제 `ROLL_G.PAT`의 어느 도형을 읽는지까지는 아직 대조하지 않았다. 스캔 로직은 객체 격자 크기 8×6 만큼 44-byte 레코드 블록을 건너뛴다. 이는 ENE_6 → 미사용 객체 블록 선택 → SPR 위치/속성 쓰기의 연결을 확정한다.

96개 레코드 중 `+0x14==1`인 항목만 상태 갱신 대상으로 처리하며 `+0x10` 값 0–10은 전용 점프표 `0x26AB6`로 분기한다. 최종 상태 10의 목적지는 `0x26B28`이다. 이 함수는 활성 갱신마다 디스크립터 `+0x12` 카운터를 증가시킨다. 카운터가 580/1,180/1,780/2,380/2,980/3,580일 때 `+0x08`을 `0x2000`으로 바꾸고, 600/1,200/1,800/2,400/3,000일 때 `+0x08=0x01D6`로 복귀시키며 `+0x0A`를 48 증가시킨다. 각 갱신에서 현재 객체 인덱스에 해당하는 8×6 SPR 위치(AH=04h)와 속성(AH=05h)을 다시 쓴다. AH=05h 인자는 `+0x0A`의 raw attribute 시작값과 `+0x08 | 0x8000`의 color-table 필드다. FreeTOWNSOS `SPR_SETATTRIBUTE`에서 color-table bit15는 격자 셀마다 기록되는 attribute 값을 1씩 증가시키는 모드다. raw attribute 시작값은 `0x280, 0x2B0, 0x2E0, 0x310, 0x340, 0x370`으로 바뀌고 각 블록은 8×6=48셀을 채운다. 여섯 48셀 블록은 총 288개 패턴으로, `ROLL_G.PAT`의 등록 범위 384개 중 앞쪽 288개를 사용한다. 타이틀 P에서는 같은 번호의 단일 패턴 대응을 확인했지만, 이 최종 객체의 각 raw value가 실제로 해당 `ROLL_G.PAT` 도형을 fetch하는지와 그 화면상 모양은 아직 직접 대조하지 않았다. 다른 상태 처리기와 공통 꼬리 `0x27F04`의 상태별 역할은 일부 미확정이다.

위 여섯 descriptor의 범위는 각각 8×6 셀, 합계 288개 패턴(`0x280–0x39F`)이다. 등록된 PAT 전체는 384개(`0x280–0x3FF`)이며, 마지막 96개(`0x3A0–0x3FF`)는 이 여섯 범위에 포함되지 않는다. 이는 정적 번호·크기 대응이며 화면상 도형 이름이나 실제 표시 결과를 확정한 것은 아니다.

### 구역 내부 스크립트 선택자 `0x8EE8C`

구역 함수는 `0x8EE8C`를 인덱스로 점프표를 호출한다. 런타임 이미지의 표 범위와 실제 목적지는 다음과 같다. 반복 목적지는 표에 적힌 그대로 보존했다.

| 처리기 | 유효 인덱스 | 점프표 | 인덱스 → 목적지 |
|---|---:|---:|---|
| 구역 1 `0x550` | 0–11 | `0x76D` | `0:79D, 1:80E, 2:87C, 3:8FE, 4:959, 5:9F0, 6:A82, 7:B22, 8:BF8, 9:C86, 10:D5B, 11:D8E` |
| 구역 2 `0x5ED0` | 0–9 | `0x60E4` | `0:610C, 1:6180, 2:6255, 3:62FA, 4:63CD, 5:6421, 6:64AD, 7:64DB, 8:652C, 9:6564` |
| 구역 3 `0xAF18` | 0–10 | `0xB131` | `0:B15D, 1:B1B1, 2:B1FB, 3:B27F, 4:B34B, 5:B5BB, 6:B6D2, 7:B71B, 8:B766, 9:B7F6, 10:B829` |
| 구역 4 `0x13C20` | 0–20 | `0x13E39` | `0:13E8D, 1:13ECA, 2:13F07, 3:13F55, 4:13FC0, 5:14057, 6:140A2, 7:14B28, 8:140FC, 9:14130, 10:1422F, 11:14266, 12:142A3, 13:1436D, 14:143B2, 15:14498, 16:145AD, 17:145EE, 18:148D5, 19:148D5, 20:14AFA` |
| 구역 5 `0x1CB38` | 0–16 | `0x1CE58` | `0:1CE9C, 1:1CFA5, 2:1D031, 3:1D0D6, 4:1D0D6, 5:1D1C1, 6:1D220, 7:1D298, 8:1D2CD, 9:1D3DC, 10:1D445, 11:1D4C2, 12:1D4FA, 13:1D58E, 14:1D5B8, 15:1D67A, 16:1D829` |
| 최종 구역 `0x26704` | 0–3 | `0x26760` | `0:26770, 1:26892, 2:268AE, 3:268C5` |

`0x8EE8C`는 시간이나 프레임 카운터가 아니다. 구역 함수는 scroll/cursor/타이머 경계에 따라 직접 값을 설정하거나 증가시키며, 객체 처리 쪽도 값 증가를 수행한다. 이미 조건까지 교차 확인된 전환 예시는 아래와 같다.

| 구역 / 지점 | 확인된 분기 조건 | 코드가 바꾸는 값 또는 다음 동작 |
|---|---|---|
| 1, `0x7A2–0x7D1` | 배경 커서 `0x8EEB0 >= 0x3FF` | 내부 선택자를 1로 설정하고 커서를 0으로 초기화. 미도달이면 기존 선택자를 유지 |
| 1, `0x856` | 선택자 1의 초기화 처리 | `0x8EE90=0`, 표시·특수 배경 초기화, 속도 설정 후 선택자를 2로 설정하고 `_1`/`_2` 맵 포인터를 설정 |
| 1, `0x8DC` | 선택자 2에서 스크롤 값이 `0x7D0`을 넘는 경로 | 속도를 바꾸고 선택자를 3으로 설정 |
| 1, `0x910` | 선택자 3이며 스크롤 값 `<0x32` | 선택자를 4로 설정. 스크롤이 `0x600`일 때 별도 사운드 경로도 있음 |
| 1, `0x9D5` | 선택자 4의 맵/화면 재설정 처리 | 선택자를 5로 설정하고 M1 맵 포인터 및 커서를 초기화 |
| 1, `0xA01` | 선택자 5 처리 중 `0x8EEB0 >= 0x1FF` | 선택자를 1 증가시키고 `0x8EEB0=0` |
| 1, `0xACE` | 선택자 6의 특수 화면/객체 초기화 처리 | 선택자를 7로 설정 |
| 1, `0xB7C` | 선택자 7에서 스크롤 값 `>0x7D0` | 선택자를 8로 설정하고 맵/표시 상태 재초기화 |
| 1, `0xD1F` | 선택자 9 처리의 `0x3F380` 워드가 `0x78`보다 커짐 | 선택자를 1 증가시키고 다음 객체 풀 주소를 설정 |
| 1, index 10 target `0xD5B` → `0xD8E` | `0xD8C`의 조건부 분기에서 스크롤 좌표 하위 6비트가 0일 때만 `0xD8E`까지 fall-through; 아니면 `0xD94`로 분기 | `0xD8E`에서 장면 상태 `[0x8EEF4]` 증가. 별도 index 11은 table target `0xD8E`로 직접 와서 이 증가를 무조건 실행 |
| 2, `0x613C` | 배경 커서 `0x8EEB0 >= 0x200` | 선택자를 1 증가시키고 커서·보조 카운터를 초기화 |
| 2, handler index 1 (`0x6180`), increment `0x61F3` | 비교는 `0x61B8`: `0x8EEB0 >= 0x6D6` | 맵 포인터/스크롤 값을 재설정하고 선택자를 1 증가 |
| 2, `0x62C3` | 보조 카운터 `0x8EEBC >= 2` | 선택자를 1 증가시키고 보조 카운터를 0으로 초기화 |
| 2, `0x6398` | `0x8EF3A`가 주기적으로 감소해 0이 됨 | 선택자를 1 증가시키고 보조 카운터를 초기화 |
| 2, `0x655C` | 보조 카운터 `0x8EEBC == 0x3F` | 선택자를 1 증가 |
| 2, `0x6573` | 선택자 9 목적지 처리 | 장면 상태 `0x8EEF4`를 증가시킴 |
| 3, `0xB251` | 비교는 `0xB226`: 선택자 2에서 맵 커서 `0x8EEB0 >= 0x200` | `EEE4=0x8022C` 대입은 `0xB236`, 선택자 증가와 스크롤·커서 갱신은 `0xB251` 부근 |
| 3, `0xB707` | 비교는 `0xB6F7`: 선택자 6 경로에서 `0x8EEB0 >= 0x800` | 선택자 증가 및 스크롤·커서 초기화는 `0xB707`; 다음 맵 `EEE4=0x8C22C` 설정은 `0xB757` |
| 3, `0xB7CE` | `0x8EEBC`가 `0xB4` 또는 `0x12C` | 선택자를 증가. `0xD2`/`0xF0`에서는 별도로 스크롤 속도를 설정 |
| 3, index 9 target `0xB7F6` → `0xB829` | index 9 경로의 `0xB81F`/`0xB827` 조건들을 통과할 때만 `0xB829`에 도달; 스크롤 정렬 하위 6비트 검사 포함 | `0xB829`에서 장면 상태 `[0x8EEF4]` 증가. 별도 index 10은 table target `0xB829`로 직접 와서 이 증가를 무조건 실행 |
| 4, `0x13E9F` | 선택자 0에서 커서 `0x8EEB0 >= 0x40` | 선택자를 증가시키고 보조 카운터·M4 맵 포인터를 초기화 |
| 4, `0x13F81` | 선택자 3에서 `0x8EEB0 >= 0x280` | 선택자를 증가시키고 보조 카운터를 초기화 |
| 4, `0x14035` | 선택자 4에서 `0x8EEBC == 0x3F` | 선택자를 증가시키고 스크롤 속도 변경 |
| 4, `0x140F0` | 선택자 6 처리의 두 경계 조건 통과 | 선택자를 한 번에 2 증가시키고 다음 맵/커서 상태를 준비 |
| 4, `0x14186`, `0x144EE`, `0x1464E` | 각 선택자의 행 처리에서 `0x8EEB4 < 0x10` | 선택자를 증가시키고 해당 행 루프 종료 후 스크롤/표시 상태 변경 |
| 4, `0x142F2` | 화면 분할 계산 결과가 `0x100` | 선택자를 증가시키고 출력 분할/속도/배경 상태 변경 |
| 4, indices 18/19 target `0x148D5` | `[0x8EEB8] < 2`이면 `0x14B28` 쪽으로 건너뜀; 그 외에는 selector 1 증가 후 `[0x8EEBC]`와 `[0x8EEB8]` 초기화 | 다음 index 20 target `0x14AFA`가 `[0x8EEF4]`를 증가. `[0x8EEB8]`의 2 도달 원인은 아직 미확정 |
| 4, `0x14B04` | 선택자 20 목적지 처리 | 장면 상태 `0x8EEF4`를 증가시킴 |
| 5, handler index 0 (`0x1CE9C`), increment `0x1CF90` | 비교는 `0x1CF6A`: `0x8EEB0 >= 0x240` | 선택자를 증가시키고 M 맵·속도 상태를 재설정 |
| 5, handler index 1 (`0x1CFA5`), increment `0x1CFF5` | 비교는 `0x1CFE5`: `0x8EEB0 >= 0x280` | 선택자를 증가시키고 화면/효과 상태 초기화 |
| 5, `0x1D0C1` | `0x8EEB8 >= 4` | 선택자를 증가시키고 `0x8EEB8=0` |
| 5, `0x1D1EC` | 선택자 5 경로에서 커서 `0x8EEB0 >= 0x480` | 선택자를 증가시키고 출력/객체 상태를 변경 |
| 5, `0x1D2B6` | 선택자 7에서 커서 `0x8EEB0 >= 0x100` | 선택자를 증가시키고 속도·보조 카운터를 초기화 |
| 5, index 15 target `0x1D67A` → `0x1D817` | `[0x8EEBC]`의 이전값을 `0x1D69C`에서 읽고 memory 값을 증가시킨 다음 snapshot이 `0x30C`인지 비교 | 일치하면 `0x1D817`에서 selector를 증가시키고 `[0x8EEB8]=0`으로 초기화. 다음 index 16 target `0x1D829`가 `[0x8EEF4]`를 증가 |
| 5, `0x1D829` | 선택자 16 목적지 처리 | 장면 상태 `0x8EEF4`를 증가시킴 |
| 최종, `0x26875` | 객체/목록 카운터 `0x3F3DC >= 0x4F` | 선택자를 증가 |
| 최종, `0x2689C` | `0x3A4C4`의 반환값이 0 | 선택자를 증가시키고 `0x8EEBC=0` |
| 최종, `0x268BD` | `0x8EEBC >= 0x78` | 선택자를 증가 |
| 최종, `0x268CF` | 선택자 3 목적지 처리 | 장면 상태 `0x8EEF4`를 증가시킴 |

이 표의 조건은 디스어셈블리에서 확인한 값 비교와 분기만 옮겼다. `0x8EEB0`, `0x8EEBC`, `0x8EEB8`는 구역마다 서로 다른 루프의 커서/보조값으로 재사용되므로 이름을 공통 “타이머”로 일반화하지 않는다. `0x8EE90`은 부호·경계 비교와 고정 증가량 `0x800`으로 갱신되는 스크롤 좌표다. `0x8EE98`은 같은 경로에서 스크롤 이동량으로 사용된다.

점프표 밖의 쓰기도 조사했다. `0x45FE`는 일반적인 객체 소멸 카운터가 아니라 구역 1 객체 상태 `0x33` 처리기의 종료 분기다. 완료 경로에서 디스크립터 `+0x14`를 0 으로 만들고 `0x8EE8C`를 1 올린 뒤 효과음 호출을 한다. 다른 selector 증가도 스테이지별 객체 상태 점프표에 귀속했다. 구역 2 의 `0x99B4`는 상태 `0x24`; 구역 3 의 `0xE743`, `0xF4E4`, `0x113A7`, `0x11981`은 각각 상태 `0x0E`, `0x16`, `0x35`, `0x39`; 구역 4 의 `0x1813C`, `0x1859F`, `0x18724`, `0x1B28E`는 상태 `0x17`, `0x19`, `0x1C`, `0x40`; 구역 5 의 `0x1FF7B`, `0x23885`, `0x23B1F`, `0x247DD`는 상태 `0x0E`, `0x44`, `0x45`, `0xCB`의 처리 경로다. 이 주소들은 각 구역 전용 객체 상태표의 목적지와 디스크립터 변경을 대조해 귀속했다. 확인된 쓰기 주소만으로 객체의 화면상 이름을 정하지 않는다.

아직 귀속되지 않은 selector 쓰기의 호출 조건과 PAT/descriptor의 화면상 대응은 미확정이다.

게임 초기 장면 선택 루프는 `0x2ABAF` 부근에 있다. 상태값 0에서 표시 초기화 뒤 오프닝/플레이 데모 루틴 `0x2D730`을 호출
하고, 상태값 1에서 타이틀 초기화 `0x2B66C`를 호출한다. 이후 사용자 입력/설정값을 확인하고 선택이 완료되면 게임 상태를 1
로 초기화해 상태 디스패처로 들어간다. 일본 원판 README의 “오프닝 데모 → 타이틀 → 대기 시 플레이 데모” 설명과 이 호출이 
대응된다.

### PLAYDEMO.DAT와 재생 cursor

파일은 4-byte little-endian DWORD 4,096 개다. 실제 데이터는 각 DWORD의 상위 24 비트가 0 이고 하위 byte만 사용한다. 값 3,536 개는 nonzero, 끝의 560 개는 zero다. 빈도가 높은 값은 DF(739 개), D7(660 개), DB(585 개), FF(558 개), 00(560 개)이다. 값이 pad byte처럼 보인다는 점만으로 저장 포맷을 추정하지 않고 소비 코드를 함께 본다.

| 경로 | 주소 | 확인된 동작 |
|---|---|---|
| 파일 열기 | 0x2AC1B–0x2AC25 | 0x3E03E의 rb, 0x3E044의 playdemo.dat로 open wrapper 0x34B30 호출 |
| 전체 로드 | 0x2AC2B–0x2AC3C | read wrapper 0x3573C에 (buffer 0xA4EB4, size 4, count 0x1000) 전달; 0x34268로 close(0x2AC47) |
| 재생 준비 | 0x2AC4E, 0x2AC59 | cursor [0xA8EB4]=0, mode word [0x94374]=1; 재생 함수 0x2EC0C 호출(0x2AC5F) |
| 입력 처리 caller | 0x2B1DE, 0x2B1EE | state 1/2 경로에서 0x2F0CC(player)를 직접 호출 |
| 모드 선택 | 0x2F16D–0x2F18A | mode 0은 실제 입력 wrapper 0x39008(player), mode 1은 demo array 경로 |
| indexed read | 0x2F18F–0x2F19A | [0xA8EB4] index로 0xA4EB4 + 4×cursor의 DWORD를 읽는다 |
| cursor 증가 | 0x2F19F | [0xA8EB4]를 1 증가시킨다. 다음 0x2F0CC 호출은 다음 DWORD를 읽는다. |

읽은 값은 0x2F1AB에서 &0x0F를 적용해 이동 lookup에 사용한다. 후속 코드는 상위 nibble을 검사하고, 0x2F3A8 이후 A-only/B-only 분기와 플레이어 descriptor +0x1A/+0x12 상태 변경으로 연결된다. 따라서 demo 값이 플레이어 입력 경로에 들어가는 것은 확인됐다. 녹화 생성 규칙과 모든 비트의 개별 의미는 아직 미확정이다.

0x2EC0C는 플레이어/화면을 초기화하고 0x2B127 을 반복 호출한다. 메인 구조 문서에서 확인한 종료 조건은 키 입력, 플레이어 0 상태, 반복 상한 3,600 이다. cursor는 0x2F0CC가 호출될 때만 증가하며 0x2B127 은 두 플레이어를 순회한다. 그러므로 outer loop 반복 횟수와 demo DWORD 소비 수가 1:1 이라고 단정할 수 없다. 0x2F18F의 indexed read 앞에서 cursor와 4,096 을 비교하는 별도 검사는 확인되지 않았다. 0 값도 입력값으로 소비될 수 있으므로 파일 꼬리의 560 개 zero를 EOS sentinel로 단정하지 않는다.

0xA4EB4 직접 사용은 로드 목적지 0x2AC38 과 indexed read 0x2F196 뿐이고, cursor [0xA8EB4]는 초기화 0x2AC4E, 읽기 0x2F18F, 증가 0x2F19F에서 확인됐다. 확인한 EXP 재생 경로에서 PLAYDEMO.DAT을 기록하는 writer는 찾지 못했다. 이는 게임의 모든 녹화 기능 부재를 증명하는 것은 아니다.

PLAYDEMO.DAT은 영문 ISO extent1258 과 일본 ZIP에서 모두 16,384 bytes, MD5 `5d81e059d43c1dc6aa596eb9cdb05bf8`로 바이트가 같다. 녹화 생성 규칙·전체 bit 의미·cursor 상한 검증·끝 560 zero의 제작 의도는 미확정이다.

### 장면 대기·게임패드 입력 경로

장면 선택 루프 0x2ABAF–0x2ACED는 초기 모드 값 ESI로 오프닝/타이틀/데모 경로를 나눈다. ESI=0은 화면을 초기화하고 0x2D730 오프닝/플레이 데모 루틴을 호출한다. ESI=1은 타이틀 화면 0x2B66C를 만들고 선택 처리 0x5BA4로 간다. 뒤의 대기 루프는 0x39008을 패드 포트 0과 1에 각각 호출하고 반환 바이트가 0xFF인지 검사한다. 어느 포트든 0xFF가 아니면 ESI=1로 설정해 타이틀 입력 분기를 다시 탄다.

0x39008(port, out)는 DH=port, AH=41h를 설정하고 0x39334를 거쳐 FS:[0x80]의 SND TBIOS 엔트리로 far-call한다. 결과 DL을 출력 포인터에 쓴다. FreeTOWNSOS HEADER.ASM의 SND 표에서 AH=41h는 SND_JOY_IN_2이고 SND.C는 EDX[15:8] 포트 번호에 따라 게임 포트 0x4D0 또는 0x4D2를 읽는다. 기본 패드 입력은 active-low라 유휴 바이트가 0xFF다. 6버튼 설정에서는 BIOS가 PAD6_in(port)를 사용한다. 게임 장면 대기와 FreeTOWNSOS의 패드 ABI가 양쪽 코드에서 맞물린다.

로컬 FreeTOWNSOS `SND.C`의 pad 정의와 구현에서 리턴 byte bit를 확인했다. `DOWN=0x01`, `UP=0x02`, `LEFT=0x04`, `RIGHT=0x08`, `A=0x10`, `B=0x20`, `RUN=0x40`, `SELECT=0x80`이며 active-low여서 눌린 키의 bit가 0 이다. 따라서 idle은 `0xFF`, 단독 UP/DOWN/A/RUN은 각각 `0xFD/0xFE/0xEF/0xBF`가 된다. 6 버튼 패드에서는 Y를 RUN, Z를 SELECT로 합성한다. 이는 FreeTOWNSOS 입력 ABI의 bit 의미이며, 게임이 그 버튼에 붙인 동작은 호출자별 비교에서 따로 확인한다.

타이틀 선택 처리기 `0x2BD0C`는 `0x2BD4F`에서 pad byte를 읽고 `0xFD`(UP only)를 현재 선택 인덱스 감소, `0xFE`(DOWN only)를 증가, `0xEF`(A only) 또는 `0xBF`(RUN only)를 선택 확정 분기로 사용한다. 이와 별도로 플레이어 상태 4(CONTINUE) 처리기 `0x2B203`는 `0x2B241`에서 플레이어 pad byte를 읽고 `0xBF`를 요구한다. 이어 공용 credit `[0x94372] > 0`이면 `0x277F4(player,1)`로 해당 플레이어와 장면을 재초기화하며 크레딧을 사용한다. 양쪽 플레이어가 상태 4 이고 credit이 남지 않으면 플레이어 0 상태를 5 로 바꾸어 GAME OVER 경로로 보낸다. 이 비교는 active-low API와 수치가 일치하며 RUN 입력으로 이어지는 코드 경로를 확인한 것이다.

게임 중 플레이어 처리 0x2F0CC도 플레이어 인덱스 0/1을 0x39008에 넘겨 입력을 읽는다. 전역 입력 모드가 0이면 실제 패드를 폴링하고, 1이면 기록 입력 배열 0xA4EB4에서 값을 가져와 인덱스 0xA8EB4를 증가시킨다. 인접 처리 0x2F366–0x2F392는 플레이어 상태값 0..11을 표 0xA90E4의 패턴 오프셋으로 바꾸고 0x94CE4 + offset×128에서 패턴을 가져와 SPR 슬롯 0xF0 + 4×player부터 4개 등록한다. 이로써 ALLTY_P.PAT은 초기 적재 뒤 플레이어별 동작 그래픽의 원본으로 동적 사용됨이 확인된다. 이동·발사 버튼을 게임 규칙상 어떤 동작으로 매핑하는지까지는 전부 복원하지 않았다.

플레이어 입력 후속 경로에서 descriptor `+0x1A`는 동작 처리 분기값, `+0x12`는 그래픽 시퀀스 표 조회에 쓰이는 값으로 구분된다. 디스패처 `0x2F270–0x2F285`는 상태 3 을 `0x2F3E1`, 상태 4 를 `0x2F479`로 보낸다. action 상위 nibble이 `0xE0`인 A-only 분기는 `0x2F3A8–0x2F3CB`에서 `0x337B0` 효과음 호출을 한 뒤 `+0x1A=3,+0x12=0`을 쓴다(방향 입력이 없을 때 전체 byte는 `0xEF`). 상위 nibble `0xD0`인 B-only 분기는 `+0x1A=4,+0x12=6`을 쓴다(방향 입력이 없을 때 `0xDF`). 상태 4 경로는 `+0x12`를 증가시키고 값 6 에서 `+0x1A=2,+0x12=0`으로 돌아간다. 별도 애니메이션 경로 `0x2F5AB–0x2F651`은 `+0x12`를 감소시키고 0 에 이르면 상태 1, `+0x12=0x0B`로 전환한다.

그래픽 조회에서는 `0x2F47E–0x2F4AA` 및 `0x2F5AB–0x2F5DB`가 표 `0xA9134`를 사용한다. 이 표에서 확인한 word 값은 `[0x10,0x40,0x44,0x48,0x4C,0x50,0x54,0]`이며, 선택된 값에 128 을 곱해 `0x94CE4` 내 패턴 주소를 만든 뒤 `0x33CF4`로 SPR에 등록한다. 따라서 A/B 입력이 동작 상태와 그래픽 시퀀스 선택에 영향을 주는 연결은 확인됐지만, 사용자 관점에서 이를 “발사/폭탄” 등으로 명명할 근거는 부족하다. `0x337B0` 호출 인자의 게임상 음향 의미와 PAT 원본 그림의 슬롯 대응도 미확정이다.

EXP 바이트에서 직접 INT 90h (CD 90) 명령은 발견되지 않았다. 이것만으로 간접 입력 경로의 부재까지 증명하지는 않으며, 여
기서는 코드와 FreeTOWNSOS 구현을 대조해 확인한 패드 경로만 기록한다.

### 스테이지별 ENE 디스패처와 객체 상태 갱신기

코드를 각 스테이지 처리기에서 개별적으로 따라가니 ENE가 한 개 공용 디스패처를 공유하지 않는다는 점이 확인됐다. 여섯 구역은 모두 ENE 버퍼 시작 주소 `0x7222C`를 전역 포인터 `0x8EEE8`에 넣고, 활성 디스크립터를 44-byte 간격의 동일한 기본 배열 `0x90148`에서 순회한다. 하지만 입력 코드 범위와 handler 점프표, 객체 상태 점프표는 구역별로 다르다. 같은 숫자 이벤트 또는 상태를 다른 구역에서도 같은 동작으로 해석하면 안 된다.

모든 확인 구역은 `0x8EEEC`의 하위 4 비트가 0 인 호출에서 ENE 입력 배치를 처리하고, 나머지 호출에서는 이벤트 디스패치를 건너뛰고 객체 상태 갱신으로 간다. 활성 디스크립터 슬롯을 폭×높이만큼 건너뛰는 96-slot 논리 순회와 공통 충돌 보조 함수 `0x27F04` 호출은 반복되는 구조다. 여기서 96 은 배열이 96 개뿐이라는 뜻이 아니다. 전체 초기화 배열은 324 개이며, 각 구역 처리기는 이 하위 범위에서 슬롯을 순회한다.

| 구역 | 입력 루프 / gate | 이벤트 표와 허용 값 | 그 구역 데이터에서 관찰된 예외 | 96-slot 상태 갱신기 |
|---|---|---|---|---|
| 1 | `0x1097`; gate `0x101A` | 1–25, 표 `0x10C4`; >25는 공통 경로 `0x1DAA` | `ENE_1.DAT`의 비영 값은 1–25 범위 | 루프 `0x1E44`; 상태 0–`0x68` 표 `0x1EAA`(105 entries), 특수 `0xC9/0xCA/0x12D`, 공통 꼬리 `0x486F` |
| 2 | `0x6843`; gate `0x67D0` | 1–25, 표 `0x6870`; table 내부 일부가 `0x736D` 공통 경로로 합류, >25도 `0x736D` | 파일에 값 25가 offset `0x1B79`에 1회 있음 | 루프 `0x7407`; 0–`0x15` 표 `0x7457`, `0x16` 별도, `0x1E`–`0x30` 표 `0x74D1`, `0x31` 별도, 공통 꼬리 `0xA3E9` |
| 3 | `0xBA42`; gate `0xB9BC` | 1–30, 표 `0xBA6F`; 25–29는 `0xCDD8` 공통 경로, >30도 `0xCDD8` | `ENE_3.DAT`의 값 30은 offset `0x1987`에 1회 있고 handler `0xCA17`로 간다 | 루프 `0xCE75`; 0–`0xFD` 표 `0xCED2`, `0x12D/0x12E` 별도, 공통 꼬리 `0x12BC8` |
| 4 | `0x14F8A`; gate `0x14F03` | 1–25, 표 `0x14FB7`; 20–24는 `0x1685F` 공통 경로, >25도 `0x1685F` | 파일에 값 25가 1회 있음; 값 20–24는 표에 있으나 공통 경로 | 루프 `0x168FC`; 0–`0xCD` 표 `0x16959`, `0x12D/0x12E` 별도, 공통 꼬리 `0x1C03D` |
| 5 | `0x1D997`; gate `0x1D910` | 1–6, 표 `0x1D9C4`; >6은 `0x1E992` 공통 경로 | `ENE_5.DAT`은 값 1–6만 사용 | 루프 `0x1EA35`; 0–`0xCC` 표 `0x1EA92`, `0x12D/0x12E` 별도, 공통 꼬리 `0x24B28` |
| 최종 | `0x26952`; gate `0x268D5` | 1만 초기화 handler `0x26976`; 그 밖의 비영 값은 기존 슬롯 처리로 합류 | `ENE_6.DAT`에는 값 1이 1회 있음 | 루프 `0x26A74`; 0–`0x0A` 표 `0x26AB6`, 그 밖은 `0x26C1A` 공통 꼬리 |

구역 1 의 상태 0–`0x68` 표와 ENE 값 1–25 의 상세 매핑은 아래 절에서 펼쳐 쓴다. 나머지 구역의 이벤트 표 주소와 범위는 서로 다른 처리기를 사용한다는 구조 증거다. 값이 표의 공통 꼬리로 향한다고 해서 이벤트가 게임 데이터에서 실제로 나타났다는 뜻은 아니므로, 코드의 허용 범위와 ENE 파일에서 센 분포를 구별해 기록했다.

`0x8EEEC`의 하위 4 비트는 ENE 입력 배치 여부를 고르지만, 이 값은 단순 증가 카운터가 아니다. 각 구역의 객체 루프 끝에서 1 증가하고, 이벤트/상태 처리기 안에서는 `INC`, `DEC`, `ADD 2`가 추가 실행된다. 아래는 실행 이미지 전체에서 확인한 쓰기를 스테이지 코드와 디스패치 표에 귀속한 결과다. 초기화 주소와 gate 읽기는 위 표를 참조한다.

| 구역 | 각 96-slot pass 끝의 증가 | 그 밖에 확인한 직접 조정 |
|---|---:|---|
| 1 | `0x48DD: +1` | 확인된 추가 증감 없음 |
| 2 | `0xA457: +1` | ENE 값 21 handler `0x70BE: +1`; 상태 `0x1E` handler `0x8A3D: −1`; 상태 `0x23` handler 내부 `0x9271: −1` |
| 3 | `0x12C36: +1` | 구역 selector 1/2 처리기 `0xB1B6`, `0xB200: −1`; ENE 값 4 `0xBC91: +2`; ENE 값 30 `0xCA31`, `0xCA4F: 각각 +2`; 객체 상태 `0x0E`, `0x15`, `0x16`, `0x32`, `0x35`, `0x39`의 handler `0xD974`, `0xF0D6`, `0xF294`, `0x10786`, `0x110BF`, `0x116BF: 각각 −1` |
| 4 | `0x1C0AB: +1` | ENE 값 12 handler `0x158CD: +1`; 값 25 handler `0x162A1: +1`; 객체 상태 `0x17`, `0x18`, `0x19`, `0x1A`, `0x1B`, `0x33`의 handler `0x17D94`, `0x1818E`, `0x181FA`, `0x185AA`, `0x185E1`, `0x18C89: 각각 −1` |
| 5 | `0x24B9C: +1` | ENE 값 2/3 handler `0x1DCDF`, `0x1DE30: 각각 +1`; 객체 상태 `0x0A`, `0x0D`, `0x0E`, `0x33`, `0x44`, `0xC9`, `0xCB`, `0xCC`의 handler `0x1EE1E`, `0x1FB8B`, `0x1FC3B`, `0x20BF8`, `0x23874`, `0x240D2`, `0x247BD`, `0x248F0: 각각 −1` |
| 최종 | `0x26C8E: +1` | 이 범위 안에서 pass 증가 외 직접 조정은 확인하지 않음 |

특히 상태 handler가 gate 값을 되돌리거나 여러 칸 더하므로, `0x8EEEC`에서 16 을 나눠 ENE 소비 시점을 읽더라도 실제 경과 프레임이나 일정한 시간 간격으로 환산할 수 없다. 여기서는 명령어가 실행되는 주소와 handler 경로만 확정하고, 조정의 게임상 연출 의도는 적의 실제 도형·이동·이벤트 배치와 연결한 뒤에 붙인다.

구역별 이벤트 점프표에 들어 있는 handler 목적지는 다음과 같다. 여기의 1 부터 시작하는 열은 ENE byte 값이며, 값−1 이 내부 table index다. `→` 오른쪽 주소는 실행 이미지의 handler 목적지다. 반복 주소는 공통 처리 경로로 모이는 table entry다.

| 구역 | ENE 값 → handler 목적지 |
|---|---|
| 2 | `1–25: 68D4, 6965, 69EA, 6A74, 6AF1, 6B6D, 6BF3, 6C7D, 6D07, 6D95, 6E12, 736D, 6E97, 6F21, 6FA5, 702D, 736D, 736D, 736D, 736D, 70BE, 714F, 71D8, 7268, 72DE` |
| 3 | `1–30: BAE7, BB86, BBE9, BC6B, BF4E, BFC3, C182, C1C9, C210, C25F, C2AF, C304, C359, C3A9, C41E, C4E0, C532, C649, C6EF, C77A, C7FE, C879, C8FF, C98C, CDD8, CDD8, CDD8, CDD8, CDD8, CA17` |
| 4 | `1–25: 1501B, 1509B, 1513E, 152AE, 152B7, 152C0, 152C9, 1561F, 15702, 1578D, 1582A, 158CD, 15ED0, 15F3C, 15F9E, 1602C, 160B2, 1615C, 1620D, 1685F, 1685F, 1685F, 1685F, 1685F, 162A1` |
| 5 | `1–6: 1D9DC, 1DCDF, 1DE30, 1E7DF, 1E877, 1E916` |

구역별 객체 상태 점프표는 범위부터 다르다. 구역 1 의 105-entry 표 `0x1EAA`는 전 게임 공용이 아니다. 구역 2 는 `0x7457` 및 `0x74D1`의 두 구간, 구역 3 은 254-entry `0xCED2`, 구역 4 는 206-entry `0x16959`, 구역 5 는 205-entry `0x1EA92`, 최종부는 11-entry `0x26AB6`를 사용한다. 44-byte 디스크립터 레이아웃이 같아도 `+0x10` 상태값의 뜻은 현재 구역의 표 문맥 안에서만 해석한다.

### 구역 2–6 ENE 이벤트에서 객체 상태 처리기까지

앞 절의 이벤트 jump table만으로는 ENE byte가 어떤 객체를 만드는지 알 수 없으므로, 각 handler가 실제로 쓰는 디스크립터 `+0x10` 상태값을 추적해 그 구역의 상태 jump table에 대입했다. 아래에서 상태 코드는 16-bit 값의 16 진수이며, `상태→처리 주소`는 해당 구역 갱신 루프의 목적지다. 여러 상태가 적힌 이벤트는 handler가 그 순서로 여러 디스크립터를 초기화하는 경우다. 코드가 현재 descriptor를 공통 경로로 넘기거나 상태 저장을 직접 하지 않는 경우도 별도 표시했다. 이 값들에 적·탄·보스 이름은 붙이지 않는다.

| 구역 | ENE 값 | 디스크립터 상태 초기화 → 상태 처리 주소 |
|---|---:|---|
| 2 | 1 | `0x0A→0x75F3` |
| 2 | 2 | `0x0B→0x77EF` |
| 2 | 3 | `0x0D→0x7A49` |
| 2 | 4–5 | `0x0E→0x7CAA` |
| 2 | 6, 9 | `0x0F→0x7D20` |
| 2 | 7 | `0x10→0x7F80` |
| 2 | 8 | `0x11→0x81EA` |
| 2 | 10–11 | `0x12→0x82C6` |
| 2 | 12, 17–20 | event table의 현재 descriptor 공통 경로 `0x736D`; 별도 상태 초기화 코드는 여기서 특정하지 않음 |
| 2 | 13–15 | 상태값 `0xC9/0xCA/0xCB`는 상태 0–`0x31` jump-table 구간 밖이므로 공통 꼬리 `0xA3E9`에 도달; 구역 2에서는 이 값의 상태 전용 갱신기가 확인되지 않음 |
| 2 | 16 | `0x16→0x896E` (상태 루프의 직접 분기) |
| 2 | 21 | `0x1E→0x8A3D` |
| 2 | 22 | `0x1F→0x8E5A` |
| 2 | 23 | `0x20→0x8EF1` |
| 2 | 24–25 | `0x14→0x851C` |
| 3 | 1, 18 | `0x0A→0xD322` |
| 3 | 2 | `0x0C→0xD5EE` |
| 3 | 3 | `0x0D→0xD76E` |
| 3 | 4 | `0x0E→0xD974`, `0x0F→0xE74E`, `0x10→0xE949`, `0x11→0xEBB0`, `0x12→0xED05` |
| 3 | 5 | 선행 `0x19→0xF8A1` 한 개와 공용 꼬리의 `0x1A→0xF934` 두 개 |
| 3 | 6 | 선행 `0x1D→0xFD23` 한 개와 공용 꼬리의 `0x1A→0xF934` 두 개 |
| 3 | 7–8 | 각각 `0x1E→0xFF06` |
| 3 | 9 | `0xCA→0x1202B` |
| 3 | 10–14 | 각각 `0xCD→0x121BA`, `0xCE→0x121D6`, `0xCF→0x12200`, `0xD0→0x12247`, `0xD0→0x12247` |
| 3 | 15–16 | `0xD1→0x122D0`, `0xD2→0x12309` |
| 3 | 17 | `0xD2→0x12309`와 `0xC9→0x11E2B` |
| 3 | 19–24 | 값 19=`0x1F→0x1019B`; 20=`0x20→0x1052E`; 21–23=`0x1E→0xFF06`; 24=`0x20→0x1052E` |
| 3 | 25–29 | 공통 현재 descriptor 경로 `0xCDD8` |
| 3 | 30 | 복합 생성: `0xFA→0x12770`, `0xFB→0x12A03`, `0xFC→0x12A1B`, `0x35→0x110BF`, 두 descriptor 모두 `+0x10=0xF8→0x12489` (상태값 저장 지점 `0xCCFC`, `0xCD91`). 상태표 `0xCED2`의 F8 엔트리(`0xD2B2`)는 `0x12489`, F9 엔트리(`0xD2B6`)는 `0x1274D`다. `0xCD38`에서 즉치값 `0xF9`를 읽고 `0xCD3C`에서 descriptor `+0x22`에 저장한다. 이는 `+0x10` 상태값이 아니다. |
| 4 | 1–3 | 1=`0xC9→0x1B579`; 2=`0xCA→0x1B6EC`; 3=`0x0A→0x16CE9`, `0x0B→0x16F51` |
| 4 | 4–6 | 공용 생성 블록으로 합류해 각각 `0x0E→0x170F8` |
| 4 | 7 | `0x0F→0x173DC`, `0x10→0x174FB`, `0x11→0x17778`; 같은 block에 레지스터 경유 값도 있어 생성 전체는 추가 대조 대상 |
| 4 | 8–11 | 8=`0xCC→0x1BAF6`; 9=`0x14→0x178D8`; 10=`0xCA→0x1B6EC`; 11=`0x0E→0x170F8` |
| 4 | 12 | 복합 생성 상태 순서: `0x17→0x17D94`, `0x16→0x17AD7`, `0x11→0x17778`, `0x16→0x17AD7`, `0x11→0x17778`, `0x16→0x17AD7`, `0x11→0x17778`, `0x16→0x17AD7`, `0x11→0x17778` |
| 4 | 13–15 | 각각 `0x0E→0x170F8` |
| 4 | 16–19 | 16=`0x1D→0x1878E`; 17–18=`0x1F→0x188CB`; 19=`0x21→0x18AAA` |
| 4 | 20–24 | 공통 경로 `0x1685F` |
| 4 | 25 | 9개 디스크립터 순서: `0x34→0x1A7A2`, `0x33→0x18C89`, `0x3A→0x1A9C4`, `0x35→0x1A80B`, `0x37→0x1A8D4`, `0x36→0x1A866`, `0x37→0x1A8D4`, `0x38→0x1A935`, `0x39→0x1A966` |
| 5 | 1 | 다섯 디스크립터: `0x0A→0x1EE1E`, 이어 `0x0B→0x1F84A` 네 개. 초기 폭·높이는 첫 항목 2×6이고 후속 항목은 별도 좌표/크기를 설정함 |
| 5 | 2 | `0xC9→0x240D2`, `0xCA→0x246CA` |
| 5 | 3 | 복합 생성 상태 순서: `0x33→0x20BF8`, `0x34→0x222B7`, `0x34→0x222B7`, `0x35→0x2244E`, `0x36→0x225BE`, `0x37→0x2262B`, `0x38→0x2273D`, `0x39→0x227B0`, `0x3A→0x229FD`, `0x3B→0x22ACE`, `0x36→0x225BE`, `0x3C→0x22CD6`, `0x38→0x2273D`, `0x3D→0x22E9F`, `0x3A→0x229FD`, `0x34→0x222B7` |
| 5 | 4–5 | 각각 `0x19→0x2082F` |
| 5 | 6 | `0x1A→0x209B3` |
| 최종 | 1 | 단일 descriptor: `0x0A→0x26B28`; 초기 폭×높이 8×6, attribute/패턴 시퀀스 시작값 `+0x0A=0x280`, color-table `+0x08=0x01D6`, x=`0`, y=`0x1800`, 활성값 1. 공통 표시 호출은 생성 직후 해당 descriptor의 크기만큼 갱신한다. |

이 표에서 구역 2–6 의 각 상태 처리 주소는 런타임 jump table을 little-endian dword로 읽은 결과와 상태 loop의 직접 분기 코드를 대조했다. 구역 2 상태 `0x16`은 table 바깥 직접 분기 `0x896E`, `0x31`은 `0x9DA3`이며, `0x1E–0x30`은 별도 표의 인덱스 `state−0x1E`로 간다. 구역 3·4·5 의 표는 각각 254·206·205 entries이고, 구역 최종부는 11 entries다. 따라서 동일한 상태 코드라도 각 구역 행 안에서만 해석해야 한다.

복합 생성 handler는 한 ENE byte만으로 여러 44-byte descriptor를 직접 초기화한다. 특히 구역 5 ENE 값 3 은 단일 객체가 아니라 16 개의 상태 슬롯을 설정하며, 구역 4 값 12 와 25, 구역 3 값 4·6·30 도 복수 디스크립터를 만든다. 여기까지는 초기 상태와 update handler 연결만 확정했다. 패턴 인덱스·크기·좌표/속도·수명 변경의 전체 상태별 연결과 PAT 이미지 도형의 대응은 미확정이다.

### ENE 초기화 시 raw attribute 저장 주소

형식: `ENE ID: dispatcher 목적지 → descriptor +0x0A store 주소(기록 값)`. 반복되는 여러 store는 서로 다른 객체/상태를 만들 수 있다. 동적 레지스터 store는 별도로 표시했다.

#### 스테이지 2

이 조사에서 직접 immediate store가 확인된 이벤트는 다음과 같다. E12 및 E17–20은 공통 처리기 `0x736D`로 연결되며 개별 초기화 store는 확인되지 않았다.

| ENE | dispatcher 목적지 | raw attribute store |
|---:|---:|---|
| 1 | `0x68D4` | `0x6942: 0x0330` |
| 2 | `0x6965` | `0x69AE: 0x0320` |
| 3 | `0x69EA` | `0x6A36: 0x0340` |
| 4 | `0x6A74` | `0x6ABC: 0x02F0` |
| 5 | `0x6AF1` | `0x6B39: 0x02F0` |
| 6 | `0x6B6D` | `0x6BB8: 0x02F0` |
| 7 | `0x6BF3` | `0x6C3F: 0x0350` |
| 8 | `0x6C7D` | `0x6CC9: 0x0380` |
| 9 | `0x6D07` | `0x6D53: 0x02F0` |
| 10 | `0x6D95` | `0x6DE1: 0x03E4` |
| 11 | `0x6E12` | `0x6E5E: 0x03A0` |
| 13 | `0x6E97` | `0x6EE3: 0x03A0` |
| 14 | `0x6F21` | `0x6F6D: 0x03EC` |
| 15 | `0x6FA5` | `0x6FF1: 0x02C0` |
| 16 | `0x702D` | `0x708A: 0x03F4` |
| 21 | `0x70BE` | `0x7111: 0x02F0` |
| 22 | `0x714F` | `0x71A1: 0x0304` |
| 23 | `0x71D8` | `0x722A: 0x030E` |
| 24 | `0x7268` | `0x72B4: 0x02B0` |
| 25 | `0x72DE` | `0x732A: 0x02B0` |

#### 스테이지 3

직접 확인한 immediate stores는 아래와 같다. 표는 아직 전 이벤트를 닫지 않았다. E7–13 및 E16 등은 계산값/공통 helper 경로가 남아 있다.

| ENE | dispatcher 목적지 | raw attribute store |
|---:|---:|---|
| 1 | `0xBAE7` | `0xBB34: 0x02B8` |
| 2 | `0xBB86` | `0xBBCF: 0x02F0` |
| 3 | `0xBBE9` | `0xBC32: 0x02E4` |
| 4 | `0xBC6B` | `0xBCD5: 0x02F8`; `0xBD6C: 0x0304`; `0xBDFD: 0x030C`; `0xBE87: 0x0314`; `0xBF19: 0x031A` |
| 5 | `0xBF4E` | `0xBFAD: 0x0350`; shared-tail children at `0xC0C1/0xC148: 0x03AC` |
| 6 | `0xBFC3` | `0xC022: 0x0350`; shared-tail children at `0xC0C1/0xC148: 0x03AC` |
| 14 | `0xC3A9` | `0xC3F4: 0x02F0` |
| 15 | `0xC41E` | `0xC469: 0x02F0` |
| 17 | `0xC532` | `0xC582: 0x02F0`; `0xC611: 0x03AC` |
| 18 | `0xC649` | `0xC696: 0x02B8` |
| 19 | `0xC6EF` | `0xC73C: 0x02D0` |
| 20 | `0xC77A` | `0xC7C7: 0x02CC` |
| 21 | `0xC7FE` | `0xC847: 0x02F0` |
| 22 | `0xC879` | `0xC8C2: 0x02F0` |
| 23 | `0xC8FF` | `0xC948: 0x02F0` |
| 24 | `0xC98C` | `0xC9D9: 0x02CC` |
| 30 | `0xCA17` | `0xCA91: 0x02B8`; `0xCB2C: 0x02CA`; `0xCC63: 0x02DA`; `0xCD9D: 0x03AC` |

ENE 17–24 의 표 값은 ENE dispatch에서 처음 만드는 descriptor의 초기값이다. ENE 17 target `0xC532`는 state `0xD2` / raw `0x02F0` descriptor를 만든 뒤 shared tail을 통해 두 번째 state `0xC9` / raw `0x03AC` descriptor도 만든다. ENE 18/19/20 은 각각 state `0x0A/0x1F/0x20`, ENE 21–23 은 각각 state `0x1E`, ENE 24 는 state `0x20`으로 초기화된다. state `0x0A`/`0x1E`/`0x1F`/`0x20`는 별도 update handler로 분기하며 이후 raw 값이 바뀔 수 있다. ENE 30 에는 descriptor 생성값과 별도로 상태 `0xF8` store가 `0xCCFC`와 `0xCD91`에 있다. `0xCD3C`의 `0xF9`는 descriptor `+0x22` 기록이므로 `+0x0A` attribute 표와 합치지 않는다.

ENE 5/6 의 dispatch는 공용 생성 꼬리 `0xC036`에 합류한다. ENE 5 는 먼저 상태 `0x19` / raw `0x0350`을 현재 descriptor에 기록한다. ENE 6 은 상태 `0x1D` / raw `0x0350`을 기록한 뒤 같은 꼬리에 들어간다. 이 꼬리는 현재 블록 이후 상태 `0x1A` / raw `0x03AC` descriptor 두 개를 더 만든다(`0xC0B3/0xC0C1`, `0xC13C/0xC148`). 두 후속 descriptor는 모두 base `0x90148 + 44×index`로 계산되고, 코드상 `index += 0x30` 후 추가 `index += 4`로 배치된다. 따라서 ENE 5 와 ENE 6 이벤트는 각각 선행 state 0x19 또는 0x1D 블록과 공용 꼬리의 두 state 0x1A 블록을 초기화한다. 이 연결만으로 화면상 객체 이름/도형은 부여하지 않는다.

추가 대조에서 ENE 7–13 및 16 의 생성 블록도 확인했다. 목적지와 폭·높이, 초기 상태/하위 상태는 다음과 같다. 이 생성 블록에는 `+0x0A` immediate store가 없어 전역 descriptor 초기값과 이후 상태 처리기 값을 분리해야 한다.

| ENE | 목적지 | `+0x16/+0x18` | 상태 초기값 `+0x10` | `+0x12` 초기값 |
|---:|---:|---:|---:|---:|
| 7 | `0xC182` | `2/2` | `0x1E` | 별도 값 없음 |
| 8 | `0xC1C9` | `2/2` | `0x1E` | 별도 값 없음 |
| 9 | `0xC210` | `2/2` | `0xCA` | 별도 값 없음 |
| 10 | `0xC25F` | `2/2` | `0xCD` | `0x34` |
| 11 | `0xC2AF` | `2/2` | `0xCE` | `0x18` |
| 12 | `0xC304` | `2/2` | `0xCF` | `0x28` |
| 13 | `0xC359` | `2/2` | `0xD0` | `0x30` |
| 16 | `0xC4E0` | `2/2` | `0xD2` | `0x30` |

위 8개 생성 블록은 모두 descriptor `+0x10`에 상태 초기값을 저장한다. `+0x1A`는 이 표의 상태 저장 필드가 아니다.

이벤트가 생성한 뒤의 상태 처리기에서 다음 raw attribute 공급식을 확인했다.

| 상태 | 처리기 | `+0x0A` 기록 |
|---:|---:|---|
| `0x1E` | `0xFF06` 경로, store `0x100C4` | `+0x12`로 index를 정규화한 뒤 `T16_3F480[index] × 4 + 0x318` |
| `0xC9` | `0x11E2B` 경로, store `0x11FED` | `T16_3F480[index] × 4 + 0x3C0` |
| `0xCC` | `0x120DC` 경로, store `0x120E1` | 고정값 `0x034C` |
| `0xD2` | `0x12309` 경로, store `0x12358` | `0x0380 + 4 × T16_3F480[index]` |

상태 `0xCA/0xCD/0xCE/0xCF/0xD0`의 확인된 handler 몸체는 phase/substate 전이를 수행하지만 직접 `+0x0A`를 쓰지 않았다. 상태 `0xCB`는 `0xCC` descriptor 준비 경로로 이어져 `0x034C` store에 도달한다. 따라서 ENE 10–13 의 초기 `+0x12`는 이 상태 전이 흐름의 입력이며, PAT 도형 ID로 곧바로 해석하지 않는다.

#### 스테이지 4

직접 확인된 값은 다음과 같다. ENE 7에는 register에서 가져오는 추가 값이 있다. `0x147D0` 및 `0x14D25`의 더 이른 pattern 관련 stores는 아래 ENE 목적지에 귀속하지 않았다.

| ENE | dispatcher 목적지 | raw attribute store |
|---:|---:|---|
| 1 | `0x1501B` | `0x15093: 0x02C0` |
| 2 | `0x1509B` | `0x15111: 0x02C8` |
| 3 | `0x1513E` | `0x151A4: 0x02D0`; `0x1527E: 0x02E0` |
| 7 | `0x152C9` | `0x1533D: 0x0330`; `0x153E5: 0x0350`; `0x15496: 0x0360`; `0x1553E: 0x0350`; `0x155EE: 0x0360` |
| 8 | `0x1561F` | `0x15689: 0x02E8` |
| 9 | `0x15702` | `0x15759: 0x02E8` |
| 10 | `0x1578D` | `0x15803: 0x02C0` |
| 12 | `0x158CD` | `0x159E8: 0x0350`; `0x15A97: 0x0360`; `0x15B3F: 0x0350`; `0x15BEF: 0x0360`; `0x15C97: 0x0350`; `0x15D47: 0x0360`; `0x15DEF: 0x0350`; `0x15E9F: 0x0360` |
| 16 | `0x1602C` | `0x160A7: 0x03B0` |
| 17 | `0x160B2` | `0x1612F: 0x03A8` |
| 18 | `0x1615C` | `0x161D9: 0x03A8` |
| 19 | `0x1620D` | `0x1626D: 0x03C0` |
| 25 | `0x162A1` | `0x162FE: 0x02A0`; `0x16391: 0x02A9`; `0x16423: 0x02CE`; `0x164C6/0x1657B/0x16623/0x166D3: 0x02B5`; `0x16783: 0x02B6`; `0x1682E: 0x02C2` |

#### 스테이지 5

| ENE | dispatcher 목적지 | raw attribute store |
|---:|---:|---|
| 1 | `0x1D9DC` | `0x1DA45: 0x02A0`; `0x1DADA: 0x02AC`; `0x1DB72: 0x02B6`; `0x1DC01: 0x02C0`; `0x1DC9F: 0x02C4` |
| 2 | `0x1DCDF` | `0x1DD3C: 0x0320`; `0x1DE01: 0x0370` |
| 3 | `0x1DE30` | `0x1DEF5: 0x0280`; `0x1DF91: 0x02C4`; `0x1E0C0: 0x02DC`; `0x1E169: 0x0286`; `0x1E1F5/0x1E289/0x1E315/0x1E3A9/0x1E435/0x1E4D3/0x1E55F/0x1E5F3/0x1E67F/0x1E713: 0x02DC`; `0x1E79F: 0x03B8` |
| 4 | `0x1E7DF` | `0x1E84A: 0x0350` |
| 5 | `0x1E877` | `0x1E8E2: 0x0350` |
| 6 | `0x1E916` | `0x1E963: 0x0330` |

ENE 3 은 초기 처리기 `0x1DE30`에서 현재 descriptor base `[0x926EC]`를 16 회 전진해 16 개 객체 블록을 만든다. 직접 저장값을 block 순서대로 연결하면 다음과 같다. `+0x24` 값도 숫자 그대로 기록했으며 timer/lifetime 등 게임 의미는 아직 부여하지 않았다.

| 블록 | 상태 `+0x10` | 격자 `+0x16×+0x18` | raw attr `+0x0A` | `+0x24` dword |
|---:|---:|---:|---:|---:|
| 1 | `0x33` | `3×4` | `0x0280` (`0x1DEF5`) | `0x1388` |
| 2 | `0x34` | `2×4` | `0x02C4` (`0x1DF91`) | `0x64` |
| 3 | `0x34` | `2×4` | `0x02DC` (DX source, `0x1E02D`) | `0x64` |
| 4 | `0x35` | `1×1` | `0x02DC` (`0x1E0C0`) | `0x50` |
| 5 | `0x36` | `1×1` | `0x0286` (`0x1E169`) | `0` |
| 6 | `0x37` | `1×1` | `0x02DC` (`0x1E1F5`) | `0` |
| 7 | `0x38` | `1×1` | `0x02DC` (`0x1E289`) | `0` |
| 8 | `0x39` | `1×1` | `0x02DC` (`0x1E315`) | `0` |
| 9 | `0x3A` | `1×1` | `0x02DC` (`0x1E3A9`) | `0` |
| 10 | `0x3B` | `1×1` | `0x02DC` (`0x1E435`) | `0x50` |
| 11 | `0x36` | `1×1` | `0x02DC` (`0x1E4D3`) | `0` |
| 12 | `0x3C` | `1×1` | `0x02DC` (`0x1E55F`) | `0` |
| 13 | `0x38` | `1×1` | `0x02DC` (`0x1E5F3`) | `0` |
| 14 | `0x3D` | `1×1` | `0x02DC` (`0x1E67F`) | `0` |
| 15 | `0x3A` | `1×1` | `0x02DC` (`0x1E713`) | `0` |
| 16 | `0x34` | `3×3` | `0x03B8` (`0x1E79F`) | `0x60` |

블록 1 은 폭 3 과 높이 4, block 16 은 폭·높이 3 을 각기 register/즉시값 조합으로 공급한다. 나머지 격자 크기는 `+0x16/+0x18`에 직접 기록된다. `+0x24` 값 `0x1388/0x64/0x50/0x60`을 수명·점수·타이머 등으로 해석할 근거는 아직 없다. ENE3 의 초기 attribute base-pointer 연결은 이 16 개 블록 범위에서 닫혔지만, 상태 전이별 상호작용과 실제 PAT 그림은 여전히 미확정이다.

스테이지 5 상태 `0x33` handler는 `0x20BF8`에서 descriptor `+0x12`를 분기값으로 읽고, `0x20C18` 표를 통해 0–13 범위의 처리기를 고른다. 확인된 목적지는 `0→0x20C50`, `1→0x20D76`, `2→0x20DB2`, `3→0x21313`, `4→0x2132C`, `5/6→0x213A3`, `7→0x21725`, `8→0x21742`, `9/10→0x217A8`, `11→0x21A0E`, `12→0x21A27`, `13→0x21A6F`; 13 초과는 `0x2221C`로 간다. 마지막 분기군 내부의 직접 raw attribute writes는 다음과 같다.

| descriptor `+0x1A` 값 | 처리 분기 | raw attribute store → 대상 |
|---:|---:|---|
| `0` | `0x21AFA` → `0x21CB4` | `0x21CC6=0x03A0` → current+`0x210`+`0x0A`; `0x21CD8=0x03A8` → current+`0x370`+`0x0A` |
| `0x0276` | `0x21C25` → `0x21EBF` | `0x21EC4=0x028C` → current+`0x0A` |
| `0x0280` | `0x21C31` → `0x21EEC` | `0x21EF1=0x0298` → current+`0x0A` |
| `0x02D0` | `0x21C62` → `0x21FA9` | `0x21FB5=0x02D4` → current+`0x210`+`0x0A`; `0x21FC7=0x02EC` → current+`0x370`+`0x0A` |
| `0x03D4` | `0x21C7F` → `0x21FEF` | `0x21FFB=0x02CC` → current+`0x210`+`0x0A`; `0x2200D=0x02E4` → current+`0x370`+`0x0A` |
| `0x03E8` | `0x21C8B` → `0x22015` | `0x2201A=0x028C` → current+`0x0A` |
| `0x03F2` | `0x21C97` → `0x22022` | `0x22027=0x0280` → current+`0x0A` |

기계어에서 `[0x926EC]`는 현재 descriptor base로 읽힌다. `EBX`에 `0x210` 또는 `0x370`을 더한 뒤 store하는 분기는 각각 현재 base+12×0x2C, base+20×0x2C의 descriptor를 대상으로 한다. 나머지 분기는 `[0x926EC]+0x0A`에 직접 쓴다. 각 phase 값에 대응하는 분기와 store 목적지는 바이트 흐름으로 연결됐으며, 이 값들은 동시에 모두 기록되지 않는다. 이 하위 descriptor의 생성 시점, 좌표·수명 및 PAT 그림은 추가 분석 대상이다.

#### 최종 구역

| ENE | dispatcher 목적지 | raw attribute store |
|---:|---:|---|
| 1 | `0x26976` | `0x269B7: 0x0280` |

최종 상태표는 상태 `0x0A`가 `0x26B28`로 가는 것을 확인했다. 이 handler에서 descriptor `+0x0A` 값은 `0x26BB6`에서 `+0x30`씩 변한다. 8×6 격자의 여섯 시작값은 `0x0280, 0x02B0, 0x02E0, 0x0310, 0x0340, 0x0370`이다. 여섯 블록의 합계는 288개(`0x280–0x39F`)로, 등록된 384개 중 나머지 96개(`0x3A0–0x3FF`)는 이 범위에 포함되지 않는다. 실제 패턴 RAM fetch 연결은 위 해석 한계대로 미확정이다.

### 상태 갱신 중 raw attribute·슬롯·전이 기록

초기 ENE descriptor의 `+0x0A` 기록 외에도 일부 상태 처리기가 raw attribute를 고정값으로 바꾸거나 현재 값에 더한다. 이 예시들은 모든 상태의 전수표가 아니다.

- 스테이지 2 상태 `0x0A` 목적지 `0x75F3`: descriptor `+0x0A`에 `0x0334`, `0x0338`, `0x033C`를 기록한다. 상태 `0x0C` 목적지 `0x790B`는 `+0x0A` 값을 증가시킨다.
- 스테이지 2 상태 `0x12` 목적지 `0x82C6`: `0x03E8`, `0x03E4`, `0x03E8`, `0x03E0` 순서를 기록한다. 상태 `0x16` 분기는 현재 `+0x0A` 값에 4 를 더한다.
- 스테이지 2 상태 `0x0F` 목적지 `0x7D20`은 `T16_3F480[+0x12]×4+0x02E0`를 `0x7E9E`에서, 상태 `0x14` 목적지 `0x851C`는 `T16_3F480[+0x12]×4+0x02B0`를 `0x865C`에서 쓴다. 두 번째 상태표의 상태 `0x30` 목적지 `0x9D92`는 같은 표를 조회해 `T16_3F480[+0x12]×4+0x03A0`를 `0x9FFD`에서 쓴다.
- 스테이지 2 의 두 번째 상태표에서 상태 `0x25` 목적지 `0x9AA3`는 `0x0318`, `0x0328`, `0x0338`, `0x0348`, `0x0358`을 기록한다.
- 스테이지 3 상태 `0x0A`, `0x0C`, `0x0D`는 각각 `0xD3A5–0xD420`, `0xD624–0xD6BE`, `0xD7A4–0xD83E`에서 반복 attribute 시퀀스를 쓴다. 개별 객체 행까지의 연결은 일부 더 필요하다. 상태 `0x69`는 descriptor `+0x12`가 `0x0C/0x18/0x24`일 때 `+0x0A`를 1 씩 증가시키고, `0x30` 분기는 다른 draw 경로로 간다. 상태 `0x6A`는 raw를 `0x0324/0x0326` 사이에서, `0x6B`는 `0x0325/0x0327` 사이에서 고른다. 이는 생성값이 아니라 상태 처리 중의 갱신이다.
- 스테이지 3 상태 `0xF8` 처리기 `0x12489`는 `0x12681`에서 `0x03C0 + 4*T16_3F480[desc+0x12]`를 쓴다. 상태 `0x1E/0xC9/0xCC/0xD2`의 식과 store 주소는 앞의 공급식 표에 기록했다. 이 값만으로 실제 PAT 도형을 특정하지 않는다.
- Update/spawn split confirmed for Stage3: `0xC182/0xC1C9` are state-`0x1E` descriptor creation targets, while state `0x1E` itself dispatches to update handler `0xFF06`; the latter recalculates `+0x0A`, updates `+0x04/+0x06`, and draws. State `0x69` (`0x11C23`), `0x6A` (`0x11D1C`), `0x6B` (`0x11D6F`), `0xCC` (`0x120DC`), and `0xD2` (`0x12309`) likewise mutate and redraw existing descriptors rather than create new ones. State `0xD2` also changes `+0x1C`, advances `+0x1A`, and indexes `T16_3F500/T16_3F604` for position/animation fields.
- State `0x0A` handler `0xD322` updates raw values by phase: default `0x02C4`; when descriptor `+0x04>0x10`, `0x02C8`; when `+0x04>0xF0`, `0x02C0`; a later phase returns to `0x02C4`. State `0x0C` handler `0xD5EE` chooses `0x02F4/0x02F0/0x02EC/0x02F0` for `+0x1A=0x50/0x60/0x70/0x80`; state `0x0D` handler `0xD76E` chooses `0x02E8/0x02E4/0x02E0/0x02E4` for the same phase sequence. These are update/animation stores, not ENE initialization values.
- State `0x1A` update handler `0xF934` has computed raw store at `0xFAE2`: `0x03C0 + 4*T16_3F480[desc+0x12]`. State `0x15` table target `0xF0D6` first transitions the current descriptor to state `0x16` at `0xF124`, then sets allocator pointer `[0x926F0]=0x90358` and initializes a separate state-`0x17` descriptor at `0x90358` (`0xF1D4`), followed by a state-`0x18` descriptor at `0x904B8` (`0xF22C`). The child descriptors have distinct `+0x04` values (`0xFFE0` and `0x0020`), `+0x06=0x0040`, texture fields `+0x0C/+0x0E=0xFC18`, `+0x28=0xFFFFD8F0`, and zeroed phase fields. No state-`0x15` setter was found in the scanned Stage3 region, so its upstream reachability is unresolved. Further audited state transitions: state `0xCB` writes intermediate `1` at `0x120A1`, then state `0xCC` at `0x120D1` on the same descriptor, state `0xF9→1` at `0x12765`, and state `0xFA→0xFD` at `0x129D3` when descriptor `+0x1C >= 0x0960`.
- Later Stage3 transition and spawn findings: state `0x32` handler entry `0x10786` updates the current descriptor to state `0x38` at `0x11091` when `+0x1A>=0x2710`, then advances/masks `+0x1C`, `+0x12`, and `+0x1A`; this is an update, not allocation. State `0x35` handler entry `0x110BF` has a branch at `0x113B7` (`ESI>=0x3F`) that resets allocation pointer `[0x926F0]=0x90148` and creates descriptors at states `0x32`, `0x36`, `0x37` (`0x113E8/0x1141C/0x11449`), with pointer increments `0x318` and `0x2C0`: state 32 is at `0x90148`, state 36 at `0x90460`, and state 37 at `0x90720`. State32 also writes `+0x28=0x2AF8`, zeroes `+0x12/+0x1A/+0x1C/+0x1E`, and sets `+0x20=0x1388`; later 36/37 handlers use aux coordinates as recorded below. No visual identities are assigned. State `0x38` handler `0x115C7` prepares two aux slots at current+`0x318` and +`0x344` by writing `+0x28=0xFFFFD8F0` and `+0x0C/+0x0E=0xFC18` (no aux state `+0x10` is set there), then zeros current phase fields `+0x1A/+0x1C/+0x1E/+0x20/+0x12` and `+0x04/+0x06`, and writes current state `0x39` at `0x11644`. Its loop scans `ESI=0x14..0x5F`, derives `[0x926F0]=0x90148+44*ESI`, tests slot `+0x10==4`, and calls helper/draw paths for matching slots. This establishes partial aux-record preparation and descriptor-array iteration, not proven spawn semantics. State `0x39` handler `0x116BF` changes current state to `0x3B` or `0x3A` at `0x11781/0x117A3`, while separately priming `[0x926F0]` to current base `+0x344` or `+0x318`; the consumer of that allocation pointer is unresolved.
- Further Stage3 closure for state `0x39`: signed `+0x1A==0x78` takes the 39→3B branch at `0x11781` and sets current `+0x04=0xFF80`; `+0x1A==0xA0` takes 39→3A at `0x117A3` and sets `+0x04=0x0080`. The branch sites do not initialize a child descriptor; the nearby `[0x926F0]` base adjustments are allocation-pointer preparation of unresolved purpose. State 3A (`0x119D9`) and 3B (`0x11AD0`) are parallel motion/update handlers: each moves descriptor `+0/+2`, updates signed `+0x04/+0x06`, increments `+0x1A`, and increments/masks `+0x12`; neither writes `+0x0A` or `+0x10` in the traced body. State 36 (`0x1147E`) reads auxiliary descriptor `[0x926F0]=0x90148`, writes current x=`aux.x−0x0200`, y=`aux.y+0x1000`, `+0x28=0xFFFFB1E0`, and geometry `+0x16/+0x18=1/1`; state 37 (`0x1150C`) uses the same auxiliary source and geometry but writes current x=`aux.x+0x1600`, y=`aux.y+0x1000`. Neither handler body writes `+0x0A/+0x10`; auxiliary data and visible identity remain unresolved. State 38’s loop work remains only partly resolved. State stubs 2F/30/31 (`0x1075F/0x1076D/0x1077B`) and 65–68 (`0x11BF1/0x11BFC/0x11C07/0x11C18`) call helpers and tail-jump; their helper semantics are not yet assigned.
- Additional Stage3 state/descriptor links: state `0x14` (`0xEF52`) advances `+0x1C` modulo `0x10` and increments `+0x1E`; once `+0x1E>0x3C`, it resets `[0x926F0]` to `0x90148`, updates an allocation-base word, and sets the current descriptor state to `1` (`0xF0B2–0xF0CB`). State `0x1B` (`0xFB28`) initializes current `+0x1A/+0x1C/+0x1E/+0x20/+0x12=0`, `+0x0C/+0x0E=0xFC18`, `+0x28=0xFFFFD8F0`, then changes the current state to `0x1C` (`0xFB5E`) and sets allocator pointer relative to current base `+0x840`; any allocated child fields are separate. State `0x1C` (`0xFBC0`) increments/masks `+0x1C` to 3 bits and increments `+0x1A`; once `+0x1A>0x3C`, it changes current state to `3` (`0xFCDE`). State `0x20` (`0x1052E`) changes current state to `1` at `0x106AF` when `+0x1C>=0x1E`, while updating phase and position. These are descriptor-level transitions only; no visual names are inferred.
- Additional Stage3 controller/update paths: states `0x33` and `0xFB` share entry `0x12A03`, while `0x34` and `0xFC` share `0x12A1B`; these handlers read auxiliary coordinates through `[0x926F0]=0x90148` and recalculate current `[0x926EC]+0/+2` using opposite x offsets (`−0x0800` vs `+0x1000`) and y `+0x0A00`. Shared tail `0x12A6B` dispatches current `+0x12` through five subcases (`0x12A81/0x12A95/0x12AC9/0x12AEC/0x12B08`) that update phase/timer/position fields; the scanned `0x12A03–0x12BC8` body has no direct `+0x0A/+0x10` writes. A subpath sets `[0x926F0]=0x909E0`, but no child descriptor initialization is proven. State `0x0E` (`0xD974`) has a branch only when current `+0x1C==2` (`0xDC8A`): it zeros current `+0x04/+0x06`, points `[0x926F0]` successively at `0x90358` and `0x904B8` and increments each auxiliary `+0x1C`, then writes phase DX to current `+0x1A`, increments current `+0x1C`, and stores `+0x28=0x07D0`. It manipulates two existing auxiliary records; no child `+0x10/+0x0A` initialization proves a spawn.
- Stage3 state `0x0F` (`0xE74E`) updates current position from aux `[0x926F0]=0x90148`: current y copies aux y, x becomes aux x−`0x0600`+current `+0x04`; it increments current `+0x12`. State `0x10` (`0xE949`) uses the same aux base, copies y, and sets x=aux x+`0x0A00`+current `+0x04`, also incrementing `+0x12`. State `0x11` (`0xEBB0`) points aux to `0x90358`, while state `0x12` (`0xED05`) points it to `0x904B8`; both use common tail `0xEE55` to set current x=aux x and y=aux y+`0x0C00`. These are current-object motion updates, with no new state `+0x10` or raw `+0x0A` stores in the shared paths; the fixed aux coordinate records' producers are unresolved.
- Stage3 state-table coverage was checked against the 254-entry dword table at `0xCED2`: explicit non-fallback ranges are `00–20`, `2F–3B`, `65–6C`, `C9–D2`, `F8–FD`; `21–2E`, `3C–64`, `6D–C8`, and `D3–F7` point to common fallback `0x12BC8`. A bounded byte scan of active code `0xD322–0x12BC8` found direct descriptor `+0x0A` operations at `D3A5/D3B2/D3C4/D420`, `D624/D64C/D674/D6BE`, `D7A4/D7CC/D7F4/D83E`, `FAE2`, `100C4`, `11C70/7F/8E` (word increments), `11D21/3B`, `11D74/8E`, `11FED`, `120E1`, `12358`, and `12681`. This bounds direct encoded writes found in that range; helper-mediated/indirect updates are not excluded.
- 스테이지 4 상태 `0x0E` handler `0x170F8`는 `+0x12`로 `T16_3F480`을 조회하고 `4×value+0x02F0`를 `0x1739F`에서 descriptor `+0x0A`에 쓴다. 상태 `0x11`은 `T16_3F500[+0x12]+0x0360`을 `0x177A9`에서 쓰고, 상태 `0x16`은 같은 표에 `0x0350`을 더해 `0x17D66`에서 쓴다. 해당 표 값의 의미와 PAT fetch 대응은 미확정이다.
- Stage4 state `0x12` table target `0x177F5` initializes eight sequential child descriptors at current base+`0x580` (32×`0x2C`): zero `+0x12` at `0x17813`, zero state `+0x10` at `0x17817`, increment slot pointer by `0x2C` at `0x1781B`; current descriptor is then initialized with `+0x28=0xFFFFD8F0`, `+0x0C/+0x0E=0xFC00`, zeroed phase fields, `+0x06=0x0080`, and transitions 12→13 at `0x1784B`. State `0x18` table target `0x1818E` similarly initializes 16 slots at current base+`0x6E0` (40×`0x2C`) to state/substate zero (`0x181B2/0x181B6`, step `0x2C` at `0x181BA`), then sets current `+0x28=0x07D0`, `+0x24=0x0190`, `+0x22=0x001A`, zeroes phase fields, and transitions 18→19 at `0x181DE`. These are confirmed slot initializations; which slots become active and their visuals is separate.
- Stage4 state chain: table state `0x1A→0x185AA` initializes current descriptor `+0x28=0xFFFFD8F0`, `+0x0C/+0x0E=0xFC00`, zeroes `+0x1A/+0x1C/+0x1E`, then writes state `0x1B` at `0x185D6`. State `0x1B` (`0x185E1`) increments current `+0x12`; exactly `0x3C` triggers state `0x1C` and resets `+0x12` (`0x185F5–0x185FE`). State `0x1C` (`0x186FB`) runs an ESI 0..7 helper loop (`0x18731/0x1877A`), then on completion writes current state `0x02` at `0x18783`; no allocator-pointer change is observed in this loop.
- 스테이지 5 상태표의 상태 `0x3A/0x3B/0x3C/0x3D/0x43` 구간에는 각각 `0x22A78`, `0x22C98`, `0x22E72`, `0x2309A`, `0x2386B`의 register 기반 `+0x0A` store가 있다. source register/lookup base는 미확정이다.

### ENE 공통 형식과 구역 1 이벤트 스트림

각 ENE 파일은 16,000 bytes다. 아래는 구역 1 처리기에서 확인한 ENE 공통 형식과 그 구역의 구체적 처리다. 전체 게임에서 이벤트 값의 뜻과 점프표가 같지는 않다. 구역별 처리기는 자체 디스패치 표를 가진다. 그 차이는 앞의 스테이지별 ENE 디스패처 비교표에 기록한다.

구역 1 처리 코드의 0x1097 루프는 EDI=0..15 를 돌며 0x8EEE8 이 가리키는 byte를 하나씩 소비한다. 값 0 은 객체 초기화/표시 분기를 건너뛰고 스트림 포인터를 한 칸 진행한다. 1–25 는 값−1 을 0x10C4 의 25-entry 점프표에 넣는다. 점프표의 20 번째 항목(ENE 값 20)은 현재 디스크립터의 공통 표시 경로 0x1DAA이며, 21–25 는 고정 객체 슬롯을 초기화하는 별도 처리기다. 25 보다 큰 값은 공통 표시 경로 0x1DAA로 간다. 한 번의 입력 배치에서 최대 16 bytes를 처리하지만, 처리 시점은 `0x8EEEC`의 하위 4 비트 게이트로 제한되므로 이를 매 프레임의 단일 이벤트라고 단정하지 않는다.

가변 객체 핸들러는 EDI 열 번호로 x=(EDI×0x400)−0x400 을 만든다. 공통 처리부 0x1DAA는 x/y를 6 비트 우측 이동해 SPR 위치 함수에 넘긴다. 0x400 단위는 화면 좌표로 16 픽셀 간격이며, 따라서 16 입력 위치가 가로 16 칸 좌표와 대응한다. 객체의 패턴 폭/높이는 16×16 SPR 패턴 칸 수로 설정된다. 개별 opcode의 고정 좌표·속도·보조 필드는 코드 상수로 기록하고, 적/탄/효과 이름은 그래픽 대조 전까지 붙이지 않는다.

opcode별 핸들러가 디스크립터 `+0x0A`에 기록하는 raw attribute `+0x0A`, 패턴 격자 크기, 생성 한도와 고정 슬롯은 다음과 같다. “EBX 한도”는 그 값보다 EBX가 클 때 새 초기화 경로를 건너뛰는 코드의 비교 상수다. 이름처럼 보이는 의미값이 아니라 아래 객체 풀 커서 문맥에서 읽어야 한다.

| ENE 값 | 처리 주소 | raw SPR attribute (`+0x0A`) | 패턴 격자 | EBX 비교 상한 | 객체 풀 슬롯 선택 |
|---:|---:|---:|---:|---:|---|
| 1 | `0x1128` | `0x2FC` | 2×2 | `0x5C` | 가변 |
| 2 | `0x11B6` | `0x324` | 2×2 | `0x5C` | 가변 |
| 3 | `0x1232` | `0x32C` | 4×4 | `0x50` | 가변 |
| 4 | `0x12AD` | `0x300` | 2×2 | `0x5C` | 가변 |
| 5 | `0x1331` | `0x300` | 2×2 | `0x5C` | 가변 |
| 6 | `0x13C7` | `0x358` | 2×2 | `0x5C` | 가변 |
| 7 | `0x1455` | `0x35C` | 2×2 | `0x5C` | 가변 |
| 8 | `0x14F6` | `0x2FC` | 2×2 | `0x5C` | 가변 |
| 9 | `0x1592` | `0x360` | 6×3 | `0x4E` | 가변 |
| 10 | `0x1617` | `0x344` | 2×2 | `0x5C` | 가변 |
| 11 | `0x1693` | `0x2D2` | 1×1 | `0x4B` | 가변 |
| 12 | `0x1702` | `0x380` | 2×2 | `0x5C` | 가변 |
| 13 | `0x177C` | `0x38C` | 2×2 | `0x5C` | 가변 |
| 14 | `0x17F3` | `0x384` | 2×2 | `0x5C` | 가변 |
| 15 | `0x189E` | `0x2B0` | 2×7 | `0x56` | 가변 |
| 16 | `0x191C` | `0x390` | 1×6 | `0x5A` | 가변 |
| 17 | `0x1995` | `0x390` | 1×6 | `0x5A` | 가변 |
| 18 | `0x1A25` | `0x3C0` | 8×4 | `0x40` | 가변 |
| 19 | `0x1AA7` | `0x3A2` | 4×4 | `0x5C` | 가변 |
| 20 | `0x1DAA` | 현재 디스크립터 | 기존 크기 | — | 초기화 없이 공통 처리 |
| 21 | `0x1B2C` | `0x2E0` | 3×5 | — | 고정 슬롯 0 |
| 22 | `0x1BB3` | `0x2F0` | 2×4 | — | 고정 슬롯 23 |
| 23 | `0x1C2D` | `0x2F8` | 2×4 | — | 고정 슬롯 39 |
| 24 | `0x1CB1` | `0x300` | 2×4 | — | 고정 슬롯 15 |
| 25 | `0x1D2B` | `0x308` | 2×4 | — | 고정 슬롯 31 |

ENE 표의 descriptor `+0x0A` 값은 `SPR_SETATTRIBUTE`에 전달되는 16-bit raw attribute다. FreeTOWNSOS는 이 값을 스프라이트 attribute RAM에 그대로 쓴다. attribute의 하위 10 비트가 패턴 RAM 슬롯 번호라는 해석은 이 로컬 BIOS 저장 코드만으로 입증되지 않았으므로, 아래 PAT 대조는 통상적인 슬롯 해석을 전제로 한 조건부 후보로 취급한다. 실제 스프라이트 레지스터 인덱스는 공용 draw 경로가 `0x326 + drawIndex`로 별도 계산한다. color-table은 descriptor `+0x08`에 있으며 호출 때 `0x8000` flag를 더해 격자 셀마다 raw attribute를 1 씩 증가시킨다. ENE 값 1/8 은 이미지의 `0x3F480` 테이블 인덱스 `0x1E`에서 값 7 을 얻어 raw attribute `0x2E0+7×4=0x2FC`를 만든다. 값 4/5 는 인덱스 `0x20`에서 값 8 을 얻어 raw attribute `0x300`을 만든다. 구역 1 ENE 값 1 handler `0x1128`에서 폭·높이 2×2, 상태 `+0x10=0x0A`, raw attribute `+0x0A=0x2FC`, color-table `+0x08=0x114`, active `+0x14=1`을 직접 대조했다.

### 구역 1 ENE 초기 raw attribute와 원판 PAT의 조건부 대응

아래 표는 FreeTOWNSOS `SPR_DEFINE`의 단위(16 색 패턴당 128 bytes), EXP의 스테이지 등록 시작값, ENE 처리기의 `+0x0A`·격자 크기를 숫자로 대조한 것이다. `+0x0A`가 AH=05h에 전달되는 raw attribute이고 격자 설정에 따라 1 씩 증가하는 사실은 코드로 확인됐다. 이 값의 하위 10 비트가 pattern RAM 슬롯을 고른다는 전제 아래 PAT 시작 번호 `0x280`/`0x380`에 대응시킨 결과이며, 해당 하드웨어 해석은 현재 로컬 BIOS 소스에서 독립적으로 확인되지 않았다. 따라서 표의 파일 내 번호는 조건부 PAT 후보이고 화면에서 쓰인 패턴이 정적으로 확정됐다는 뜻은 아니다.

아래 파일 내 번호 범위와 비영 픽셀 수는 일본 원판 ZIP의 원시 PAT 바이트에서 계산했다. 비영 픽셀 수는 각 128-byte 패턴의 4bpp 니블 가운데 값이 0 이 아닌 니블 수다. 이를 투명 픽셀 수라고 단정하지 않으며, 표는 화면에서 어떤 적인지 식별하는 의미 부여가 아니다.

| 구역 1 ENE 값 | `+0x0A` raw 시작값 | 격자 | 조건부 PAT 후보 | 가정상 파일 내 번호 | 비영 니블 수 / 전체 |
|---:|---:|---:|---|---:|---:|
| 1, 8 | `0x2FC` | 2×2 | `ST1_BG.PAT` | `0x07C–0x07F` | 328 / 1,024 |
| 2 | `0x324` | 2×2 | `ST1_BG.PAT` | `0x0A4–0x0A7` | 496 / 1,024 |
| 3 | `0x32C` | 4×4 | `ST1_BG.PAT` | `0x0AC–0x0BB` | 1,658 / 4,096 |
| 4, 5 | `0x300` | 2×2 | `ST1_BG.PAT` | `0x080–0x083` | 312 / 1,024 |
| 6 | `0x358` | 2×2 | `ST1_BG.PAT` | `0x0D8–0x0DB` | 728 / 1,024 |
| 7 | `0x35C` | 2×2 | `ST1_BG.PAT` | `0x0DC–0x0DF` | 757 / 1,024 |
| 9 | `0x360` | 6×3 | `ST1_BG.PAT` | `0x0E0–0x0F1` | 2,540 / 4,608 |
| 10 | `0x344` | 2×2 | `ST1_BG.PAT` | `0x0C4–0x0C7` | 294 / 1,024 |
| 11 | `0x2D2` | 1×1 | `ST1_BG.PAT` | `0x052` | 172 / 256 |
| 12 | `0x380` | 2×2 | `ST1_BG2.PAT` | `0x000–0x003` | 448 / 1,024 |
| 13 | `0x38C` | 2×2 | `ST1_BG2.PAT` | `0x00C–0x00F` | 269 / 1,024 |
| 14 | `0x384` | 2×2 | `ST1_BG2.PAT` | `0x004–0x007` | 269 / 1,024 |
| 15 | `0x2B0` | 2×7 | `ST1_BG.PAT` | `0x030–0x03D` | 2,442 / 3,584 |
| 16, 17 | `0x390` | 1×6 | `ST1_BG2.PAT` | `0x010–0x015` | 212 / 1,536 |
| 18 | `0x3C0` | 8×4 | `ST1_BG2.PAT` | `0x040–0x05F` | 3,524 / 8,192 |
| 19 | `0x3A2` | 4×4 | `ST1_BG2.PAT` | `0x022–0x031` | 2,874 / 4,096 |
| 21 | `0x2E0` | 3×5 | `ST1_BG.PAT` | `0x060–0x06E` | 1,208 / 3,840 |
| 22 | `0x2F0` | 2×4 | `ST1_BG.PAT` | `0x070–0x077` | 640 / 2,048 |
| 23 | `0x2F8` | 2×4 | `ST1_BG.PAT` | `0x078–0x07F` | 629 / 2,048 |
| 24 | `0x300` | 2×4 | `ST1_BG.PAT` | `0x080–0x087` | 640 / 2,048 |
| 25 | `0x308` | 2×4 | `ST1_BG.PAT` | `0x088–0x08F` | 629 / 2,048 |

원시 데이터 안에서 ENE 값 1 과 8 은 같은 네 패턴을 참조하고, 4 와 5 도 같은 네 패턴을 참조한다. 값 16 과 17 은 같은 여섯 패턴을 참조한다. 값 4/5 와 고정 객체 값 24 는 시작값이 모두 `0x300`이지만 격자 크기가 다르므로 앞의 2×2 와 뒤의 2×4 는 서로 다른 PAT 범위를 사용한다. 패턴 블록이 PAT에 존재하고 처리기의 시작 번호·크기에 정확히 대응하는 점은 정적으로 확인했다. 색상표 적용 후의 외관과 각 상태의 시간별 애니메이션, 그 도형이 게임상 어떤 객체인지는 별도 대응이 필요하다.

객체 슬롯 커서 문맥도 확인했다. 한 16 칸 처리 전 코드는 `0x90148`부터 활성 플래그 `+0x14`를 살피며 기존 객체가 차지한 `폭×높이` 슬롯을 건너뛴다. 가변 처리기는 현재 EBX 커서와 opcode별 비교 상한을 검사한 뒤 현재 커서의 디스크립터를 초기화한다. 공통 처리부 뒤에는 현재 `+0x16 × +0x18` 크기를 EBX에 더하고, 객체 포인터를 같은 수의 44-byte 레코드만큼 전진시킨다. 이 때문에 다칸 스프라이트는 패턴 칸 수만큼 연속 디스크립터 슬롯을 예약하며, `0x5C` 같은 비교값은 시간/프레임 값이 아니라 이 배치에서 사용하는 객체 풀 커서의 한도다. 고정 opcode 21–25 는 이 가변 커서 검사 대신 지정 인덱스를 고른다.

파일 바이트 분석에서 ENE 값 1–25 의 실제 빈도는 다음과 같다. 값 0 은 각 파일의 나머지 바이트이며, 표의 수치는 파일 안에서의 횟수이지 플레이 중 실제 생성 횟수의 별도 계측값은 아니다.

| 파일 | 1–25 중 0이 아닌 값 분포 (`값:횟수`) |
|---|---|
| `ENE_1.DAT` | `1:12, 2:20, 3:7, 4:1, 5:16, 6:43, 7:37, 8:3, 9:4, 10:6, 11:47, 12:7, 13:15, 14:18, 15:2, 16:10, 17:9, 18:1, 19:2, 21:1, 22:1, 23:1, 24:1, 25:1` (합계 265) |
| `ENE_2.DAT` | `1:14, 2:2, 3:11, 4:24, 5:24, 6:56, 7:1, 8:3, 9:2, 10:49, 11:3, 13:7, 14:3, 15:4, 16:22, 21:1, 22:1, 23:1, 24:1, 25:1` (합계 230) |
| `ENE_3.DAT` | `1:21, 2:17, 3:18, 4:1, 5:1, 6:1, 7:28, 8:26, 9:4, 10:1, 11:2, 12:1, 13:1, 14:1, 15:1, 16:8, 17:8, 18:1, 19:10, 20:42, 21:30, 22:30, 23:2, 24:2` (합계 257); 별도로 값 `30` 1회 |
| `ENE_4.DAT` | `1:23, 2:20, 3:8, 4:62, 5:18, 6:17, 7:2, 8:1, 9:26, 10:1, 11:2, 12:1, 13:24, 14:13, 15:13, 16:18, 17:21, 18:1, 19:24, 25:1` (합계 296) |
| `ENE_5.DAT` | `1:1, 2:1, 3:1, 4:22, 5:12, 6:1` (합계 38) |
| `ENE_6.DAT` | `1:1` (합계 1) |

이 입력 소비에는 별도의 16 단계 게이트가 있다. 코드 0x101A는 전역 0x8EEEC의 하위 4 비트가 0 이 아니면 바로 0x1E44 객체 갱신 경로로 가며, ENE byte-dispatch 0x1097 을 건너뛴다. 하위 4 비트가 0 이면 16-byte 입력 루프를 실행한 뒤 객체 갱신을 한다. 스테이지 초기화에서는 0x8EEEC를 0 으로 설정하는 코드가 공통 시작 0x74, 다음 구역 진입 0x5C96/0xACA9/0x13A80/0x1C90C, 최종 구역 0x2656C에서 확인된다. 따라서 “파일에서 16 바이트를 한 번에 읽는다”는 건 맞지만, 그 호출 간격을 곧바로 한 화면 프레임이나 고정 시간으로 환산할 수 없다. 0x8EEEC를 증가시키는 코드가 0x48DD 외에도 여러 실행 경로에 있으므로 모든 증가 호출과 메인 대기 루프를 연결해야 실제 소비 주기를 알 수 있다.

`ENE_3.DAT`에는 offset `0x1987`에 값 `30`이 한 번 있다. 구역 3 의 유효 ENE 점프표는 1–30 이므로 이 값은 handler `0xCA17`로 간다. handler는 descriptor 두 개에 상태 `+0x10=0xF8`을 쓰며, 상태표에서 F8 은 `0x12489`로 간다. `0xCD38`에서 즉치값 F9 를 읽어 `0xCD3C`에서 descriptor `+0x22`에 저장한다. 이 이벤트의 화면상 객체 이름은 아직 특정하지 않았다.

공통 표시 경로 0x1DAA는 현재 디스크립터의 +0x14 가 1 일 때만 현재 객체를 위치/속성 BIOS 호출로 갱신한다. 디스크립터 +0/+2 는 x/y, +0x08 은 color-table 값, +0x0A는 SPR attribute/패턴 시퀀스 시작값, +0x14 는 활성값, +0x16/+0x18 은 패턴 격자 폭/높이다. ENE 처리 뒤 별도 상태 갱신 루프 0x1E44 는 `0x90148 + 인덱스×0x2C`를 기준으로 인덱스 0–95 를 순회한다. 활성값이 1 인 디스크립터는 +0x10 상태 필드를 본다. `0x12D`, `0xCA`, `0xC9`는 각각 0x4866, 0x4637, 0x46FE의 특수 분기로 가고, 나머지 값 0–0x68 은 0x1EAA 점프표(105 개 엔트리, 43 개 고유 코드 주소), 그 밖의 값은 0x486F 공통 꼬리로 간다. 각 처리 뒤 인덱스는 `폭×높이`만큼 건너뛰며, 루프 말미 0x48DD가 별도 전역 0x8EEEC를 1 증가시킨다. 이 전역은 메인 장면 상태 0x8EEF4 나 구역 진행값 0x8EE94 와 구분해 기록한다.

따라서 파일에서 읽은 ENE 바이트, 고정 디스크립터 번호, 상태 디스패치 코드값은 서로 다른 단계의 번호다. 객체의 움직임/수명 코드는 여러 보조 함수를 호출하므로 상태마다 의미 이름을 붙이려면 각 상태 처리기가 갱신하는 좌표·속도·패턴·활성 필드와 실제 PAT 도형을 추가로 맞춰야 한다. 각 ENE 값이 어떤 적·탄·보스 부품인지는 그 대조가 끝날 때까지 보류한다.

### 구역 1 ENE 생성 상태와 객체 상태 전이 연결

ENE 처리기가 디스크립터 `+0x10`에 넣는 초기 상태를 객체 갱신 루프의 실제 점프표와 대조했다. 아래 상태 번호는 ENE opcode와 별개이며, 상태값 자체가 행동 이름인 것은 아니다. 괄호의 주소는 점프표 목적지다.

| ENE 값 | 초기 상태 코드 | 상태 처리 주소 | 생성 슬롯 방식 |
|---:|---:|---:|---|
| 1 | `0x0A` | `0x20B1` | 가변 |
| 2 | `0x0B` | `0x226D` | 가변 |
| 3 | `0x0C` | `0x2396` | 가변 |
| 4 | `0x0A` | `0x20B1` | 가변 |
| 5 | `0x0E` | `0x2769` | 가변 |
| 6 | `0x0F` | `0x29C9` | 가변 |
| 7 | `0x0F` | `0x29C9` | 가변 |
| 8 | `0x0E` | `0x2769` | 가변 |
| 9 | `0x10` | `0x2A7A` | 가변 |
| 10 | `0x11` | `0x2C1B` | 가변 |
| 11 | `0x13` | `0x2D90` | 가변 |
| 12 | `0x14` | `0x2E2A` | 가변 |
| 13 | `0x15` | `0x2EA8` | 가변 |
| 14 | `0x16` | `0x2F0D` | 가변 |
| 15 | `0xC9` | `0x46FE` 특수 분기 | 가변 |
| 16 | `0xCA` | `0x4637` 특수 분기 | 가변 |
| 17 | `0xCA` | `0x4637` 특수 분기 | 가변 |
| 18 | `0x18` | `0x3103` | 가변 |
| 19 | `0x0F` | `0x29C9` | 가변 |
| 20 | 신규 상태값 없음 | 공통 처리 `0x1DAA` | 현재 디스크립터 재사용 |
| 21 | `0x1D` | `0x345B` | 고정 슬롯 0 |
| 22 | `0x1E` | `0x377A` | 고정 슬롯 23 |
| 23 | `0x1F` | `0x38C3` | 고정 슬롯 39 |
| 24 | `0x20` | `0x3A0D` | 고정 슬롯 15 |
| 25 | `0x21` | `0x3A81` | 고정 슬롯 31 |

상태 갱신 점프표 전체는 `0x1EAA`부터 105 개 dword로 읽힌다. 인덱스와 목적지는 다음과 같다. 범위 안의 반복값은 실제 엔트리 결과 그대로 표시했다.

| 상태 인덱스 | 목적지 | 상태 인덱스 | 목적지 | 상태 인덱스 | 목적지 |
|---|---|---|---|---|---|
| `00–05` | `204E,2059,2064,206F,207A,2085` | `06` | `486F` | `07–0A` | `2090,209B,20A6,20B1` |
| `0B–10` | `226D,2396,275E,2769,29C9,2A7A` | `11–16` | `2C1B,2CD9,2D90,2E2A,2EA8,2F0D` | `17–1A` | `30F8,3103,32F0,339A` |
| `1B–1C` | `486F` | `1D–21` | `345B,377A,38C3,3A0D,3A81` | `22–26` | `3B78,3B83,3C5A,3D4F,3D62` |
| `27–28` | `3E44` | `29` | `3EBD` | `2A–2F` | `486F` |
| `30` | `461B` | `31` | `462C` | `32` | `4264` |
| `33` | `432B` | `34–66` | `486F` | `67` | `461B` |
| `68` | `462C` |  |  |  |  |

여기서 확인된 한 객체 처리의 단계 연결은 다음과 같다. ENE 값 21 은 디스크립터 고정 슬롯 0 에 상태 `0x1D`를 설정한다. 상태 `0x1D` 처리기 `0x345B`의 특정 보조 카운터가 `0x98`에 이르면 분기 `0x36F4`가 현재 객체의 x좌표를 6 비트 이동해 검사한다. 결과가 `0x60`이면 현재 객체 상태를 `0x29`로 바꾸고 `+0x12`, `+0x1A`를 0 으로 초기화한다. 상태 `0x29` 처리기 `0x3EBD`는 매 호출마다 `+0x12`를 증가시키며, 그 값이 `0x1388`(5000)이면 상태를 `0x32`로 바꾼다. 이는 5000 번의 객체 처리기 호출 조건이지 5000 화면 프레임이라고 환산한 값은 아니다.

상태 `0x32` 처리기 `0x4264`는 `0x8EE94=0xC8`을 설정하고 81 개 디스크립터 범위를 순회해 상태 `0x04`인 객체를 비활성화한다. 이어 현재 디스크립터의 상태를 `0x33`으로 바꾸고 애니메이션/좌표 필드를 초기화한다. 상태 `0x33` 처리기 `0x432B`는 패턴과 속성을 갱신하고, 종료 카운터가 0x40 경계에 도달하면 현재 객체를 비활성화하고 `0x8EE8C`를 증가시킨다. 따라서 이 경로에서 `0x45FE`의 selector 증가는 ENE 값 21 의 객체 진행과 연결될 수 있는 코드상 결과다. 이 코드의 객체를 특정 적·보스·장면 이름으로 부르지는 않는다. 같은 상태값의 다른 생성 경로 사용 여부와 실제 PAT 도형의 대응은 미확정이다.

추가로 점프표 상태 안에서 직접 확인된 재할당은 다음과 같다.

| 현재 상태 | 다음 상태 | 조건/동작 근거 |
|---:|---:|---|
| `0x19` | `0x02` | `0x32F0` 처리기가 3회 반복 루프를 끝낸 뒤 현재 디스크립터에 대입 (`0x338F`) |
| `0x1D` | `0x29` | 위의 좌표 `x >> 6 == 0x60` 경로 (`0x3725`) |
| `0x1E` | `0x23` | `+0x1C` 카운터가 `0xE10` 초과 (`0x38B8`) |
| `0x1F` | `0x24` | `+0x1C` 카운터가 `0xE10` 초과 (`0x39FD`) |
| `0x23` | `0x25` | 현재 디스크립터에서 8개 앞의 보조 디스크립터에 상태를 설정 (`0x3C3C`); 현재 디스크립터는 병합 처리에서 상태 `0x01`이 됨 |
| `0x24` | `0x26` | 동일한 배치의 다른 방향 경로 (`0x3D13`); 현재 디스크립터는 상태 `0x01`이 됨 |
| `0x29` | `0x32` | `+0x12 == 0x1388` (`0x3F4C`) |
| `0x32` | `0x33` | 초기화 루틴이 현재 디스크립터에 다음 상태를 바로 기록 (`0x42D8`) |

상태 `0x1E`와 `0x1F`의 처리기는 대칭적인 좌표/속도 갱신 경로다. 둘 다 `+0x1A`의 특정 단계에서 기준 디스크립터 `0x90148`을 참조하고, 자기 `+0x12` 값이 `0x78`, `0xA0`, `0xC8`일 때 `0x4F18` 보조 루틴을 호출한다. 각각 x에 기준값 `−0x780` 또는 `+0xB80`을 더하고 y에는 `+0x454`를 더한다. 이 루틴들의 화면상 명칭과 `0x4F18`의 생성 데이터는 아직 별도 대응 작업이 필요하다.

상태 `0x23`/`0x24` 초기화는 현재 디스크립터에서 8개(8×0x2C=0x160 bytes) 앞의 레코드를 골라 상태 `0x25`/`0x26` 및 파라미터를 넣고, 현재 디스크립터를 상태 `0x01`로 돌린다. 상태 `0x25`/`0x26`은 좌표를 갱신해 SPR을 그리고, y가 `0x3C00`보다 커지면 현재 객체를 비활성화하고 기준 레코드 `0x90148`의 `+0x1E`를 증가시킨다. 상태 `0x27`/`0x28`은 점프표의 같은 목적지 `0x3E44`를 쓰며, 표시 패턴을 지우고 같은 기준 레코드 카운터를 증가시키는 정리 경로가 확인된다. 여기서 `0x90148`은 처리 중인 객체와 다른 기준 레코드이며, 해당 카운터가 게임상 어떤 개수인지까지는 아직 확정하지 않았다.

상태 `0x19`는 난수 호출을 포함한 3회 위치/그래픽 처리 뒤 상태 `0x02`로 넘어간다. 처리 횟수는 코드에서 확인되지만 난수 위치에 배치되는 도형의 구체 의미는 PAT와 실제 좌표 자료를 함께 확인해야 한다.

이 연결로 객체 시스템의 서로 다른 번호 층이 구분된다: ENE opcode가 생성 처리기를 고르고, 처리기가 상태 코드와 raw attribute/크기를 디스크립터에 넣으며, 매 갱신에서 상태 코드 점프표가 좌표·raw attribute·수명·전환 동작을 수행한다. raw attribute가 가리키는 렌더 패턴 슬롯 해석은 별도 층으로 남는다. 숫자 코드끼리 같은 의미로 취급할 수 없다.

### 객체 디스크립터/스프라이트 출력

런타임 객체 디스크립터는 44-byte(0x2C) 단위다. 초기화 0x2A944 는 0x8EF3C부터 정확히 324 개(0x144 개)를 순회한다. 배열 범위는 [0x8EF3C, 0x926EC)이며 324×44=14,256 bytes다. 이 배열 바로 다음의 DWORD 저장소 `0x926EC`에는 초기화 시 끝 주소 값이 들어간다. 각 항목에서 +0,+2,+4,+6,+0x14 를 0 으로, +0x16/+0x18 을 1 로, +8 을 0x100, +0x0A를 128 로 초기화하고, 나머지 확인된 필드도 0 으로 지운다. 초기화 중 각 항목에 1×1 위치/속성 호출을 하며 스프라이트 레지스터 번호는 1023부터 항목마다 감소하고, AH=05h에 전달하는 raw attribute는 `0x100`으로 고정된다.

`[0x926EC]`는 항상 풀 끝 커서인 고정 전역값이 아니라 여러 루틴이 다른 용도로 재사용하는 DWORD다. 초기화 함수 `0x2A944`는 이를 `0x8EF3C`로 설정하고 324 개 descriptor마다 `+0x2C`해 마지막에 배열 끝 `0x926EC`에 도달한다. 별도 32-slot 풀 생성기 `0x26F60`은 실제 free-slot 선택을 `[0x3F710]` 사용수, `[0x3F712]` 원형 인덱스, `[0x3F714]` 슬롯 표로 하고 선택 결과 descriptor 포인터를 `[0x926EC]`에 임시 보관한다. 이때 `[0x926EC]`는 free-slot counter가 아니다. updater `0x270FC`는 `0x91AB8`로 재설정한 뒤 32 개 slot을 순회하고, GAME OVER cleanup도 같은 base를 scan cursor로 쓴다. 플레이어 갱신 `0x2F0CC`와 continue 초기화 `0x277F4`에서는 이를 현재 플레이어 descriptor 포인터로 사용한다. 플레이어 번호 p=0/1 에서 가리키는 값은 각각 `0x91A08`/`0x91958`이며, 이후 `0x2F1B1`, `0x2F40C`, `0x2F44B` 등은 그 descriptor를 접근한다. 따라서 이 전역의 의미는 그 값을 세팅하는 함수와 호출 문맥으로 구분한다. 배열 시작 `0x8EF3C`와 항목 크기 44바이트를 기준으로, `0x90148`은 0부터 센 인덱스 105이고 `0x91AB8`은 인덱스 253이다. 이 별도 32-slot 풀의 `0x26F60` 생성, `0x270FC` 갱신, `0x3BA+slot` register 및 `ALLTY_2.PAT` 패턴 시퀀스는 아래 절에서 연결한다. 구체적인 화면상 객체 종류와 각 호출자의 발생 조건은 아직 미확정이다.

객체 갱신의 구역별 공통 꼬리는 현재 상태 코드가 부호 있는 16-bit 값 기준으로 `0x0A–0xC7` 범위, 정확히 `0x04`, 또는 `0x12C`보다 클 때 충돌 보조 함수 `0x27F04`를 호출한다. 구역 1의 꼬리는 `0x486F`; 같은 비교 형태가 구역 2 `0xA3E9`, 구역 3 `0x12BC8`, 구역 4 `0x1C03D`, 구역 5 `0x24B28`, 최종부 `0x26C1A`에 있다. 함수는 현재 디스크립터의 좌표 `+0/+2`, 폭·높이 `+0x16/+0x18`, 경계 오프셋 `+0x0C/+0x0E`로 사각 경계를 만들고, 플레이어 관련 디스크립터 주소 `0x91A08` 및 `0x91958`의 좌표·경계와 겹치는지 비교한다. 겹치면 충돌 관리 레코드 영역 `0x94368`/`0x94388`의 필드를 갱신하고, 상황별 효과음 호출을 한다. 상태 `0x04`에는 별도 2항목 충돌 검사 분기가 있다. 이 조건은 세 비교와 분기(`<=9`, `<0xC8`, `>0x12C`, `==4`)에서 직접 복원했다. 상태 처리기의 좌표/패턴 갱신과 공통 충돌 판정은 서로 다른 호출 단계다. 관리 레코드 `R[p]`의 `+0` 잔기, `+2` 충돌/상태 자원 카운터, `+4` 상태, `+6` phase/call counter, `+0x10` 점수, `+0x14/+0x18` 점수 갱신 제어값/타이머는 위 플레이어 필드 표에 정리했다. 관리 레코드의 `R+2`가 게임 규칙상 무엇을 세는지와 `R+0x08/R+0x0E/R+0x1C`의 용도는 미확정이며, 확인한 충돌 코드에서 별도 무적 플래그는 발견하지 못했다.

표시 순회 `0x27D18`은 `0x90148`부터 시작하며, 소스 슬롯 번호 EDI가 96 이상이면 종료한다. 활성값(+0x14)이 0인 항목은 소스 포인터를 44바이트, EDI를 1만큼 이동시킨다. 활성값이 1인 항목은 +0x16×+0x18 크기만큼 소스 슬롯 번호 EDI와 표시용 슬롯 번호 ESI를 진행시키고, 소스·대상 포인터도 각각 그 크기×44바이트만큼 이동시킨다. 두 슬롯 번호가 다를 때만 11개 DWORD를 표시용 영역에 복사하며, 원래 소스 항목의 활성값을 지우고 표시용 항목의 위치/속성 BIOS 호출을 수행한다. 따라서 96은 소스 슬롯 번호의 상한이며 고정 반복 횟수가 아니다. 배열 전체 크기, 객체 할당 슬롯, 표시 순회의 슬롯 범위는 서로 다른 범위 개념이다. 구조체 필드 중 의미가 코드에서 확인되지 않은 값은 임의로 명명하지 않는다.

### 별도 32-slot 객체 풀과 ALLTY_2.PAT의 조건부 번호 대응

`0x26F60` 생성 함수와 `0x270FC` 갱신 함수를 추적해 배열 `0x91AB8`부터 32개의 보조 descriptor를 도는 경로를 확인했다. 이 풀은 구역 ENE 갱신 루프가 순회하는 기본 96-slot 범위(`0x90148`)와 주소·할당 카운터가 분리돼 있다. 32개 슬롯의 화면상 객체 이름이나 발생 원인은 호출자별 인자까지 더 연결해야 하므로 여기서는 풀의 기능 범위만 적는다.

생성 함수는 충돌/상태 확인 함수 `0x27E74`가 성공하고 사용 개수가 32 미만일 때 원형 인덱스 배열 `0x3F714`에서 슬롯을 얻는다. 새 descriptor에 caller가 준 x/y에서 `0x200`을 뺀 좌표, 계산된 x/y 증가량, active=1, color-table, mode `+0x28=2`, caller의 `+0x1A` 선택값을 기록한다. 하드웨어 sprite register는 `0x3BA+slot`이고 생성 직후 설정되는 attribute/pattern 값은 `0x1B7`이다.

갱신 함수의 mode 2 경로는 매 pass에서 `+0x04/+0x06`을 위치에 더하고 `+0x12`를 `0..15`로 순환시킨다. `+0x1A`가 0 일 때 dword 표 `0x3F754`에서 `0x230..0x23F`, 0 이 아닐 때 `0x3F794`에서 `0x240..0x24F`를 꺼내 `+0x0A`에 기록한다. 둘 다 16 개 값이 순서대로 놓여 있다. `ALLTY_2.PAT`은 `SPR_DEFINE` 시작 번호 `0x180`으로 등록된다. 다음 표의 PAT 인덱스는 raw attribute의 하위 10 비트가 해당 SPR 슬롯을 선택한다고 가정한 조건부 후보이며, 슬롯 대응 자체는 확정하지 않았다.

| 사용 문맥 | AH=05h raw attribute 값 | 조건부 후보: `ALLTY_2.PAT` 내 0-based 128-byte 패턴 번호 |
|---|---:|---:|
| 생성 직후 | `0x1B7` | `0x037` |
| mode 2, selector 0 | `0x230..0x23F` | `0x0B0..0x0BF` |
| mode 2, selector nonzero | `0x240..0x24F` | `0x0C0..0x0CF` |
| mode 3 시작 구간 | `0x1A3..0x1A6` | `0x023..0x026` |

mode 2 경로는 x/y 좌표를 `[-0x400, 0x3C00]` 범위와 비교해 밖으로 나가면 raw attribute `0xA000`을 쓰고 active 및 mode를 0 으로 만든 뒤 사용 개수를 감소시킨다. mode 3 은 호출 지점 `0x27470`에서 효과 번호 `0x43`을 `0x337B0`에 넘긴 다음 설정되며, 시작 `+0x0A=0x1A3`으로 매 pass AH=05h raw attribute를 기록하고 증가시킨다. `+0x0A`가 `0x1A7`에 도달하면 active/mode를 0 으로 만들고 raw attribute `0xA100`을 써서 register를 가린 뒤 사용 개수를 감소시킨다. raw 값의 하위 10 비트와 `ALLTY_2.PAT` 등록 번호가 같은 패턴 슬롯을 뜻한다는 해석은 조건부 후보이며 미확정이다. 효과 `0x43`의 청감상 의미와 32-slot 객체의 구체 종류도 아직 특정하지 않는다.

### 44-byte 객체 디스크립터의 BIOS 필드 대응

게임의 두 래퍼와 FreeTOWNSOS `SPR.C`를 함께 대조해 공용 표시 경로의 인자 순서를 확정했다. `0x33D48`은 SPR AH=04h 위치 설정, `0x33D7C`는 AH=05h 속성 설정이다. 공용 렌더러 `0x27D18` 및 ENE 공통 표시 `0x1DAA`는 스프라이트 레지스터 시작 인덱스를 `0x326 + drawIndex`로 계산하고, 디스크립터에서 위치·크기·attribute 시작값·color-table 값을 가져온다.

| 디스크립터 오프셋 | 확인한 소비 방식 | 확정도 |
|---:|---|---|
| `+0x00`, `+0x02` | 부호 있는 x/y. BIOS 위치 설정 전에 각각 산술 우측 6비트하여 전달하므로 값은 1/64 픽셀 단위 좌표 | 직접 확인 |
| `+0x04`, `+0x06` | 이동 상태 `+0x28==2`에서 매 갱신마다 x/y에 더하는 signed word 증분 | 해당 상태에서 직접 확인; 시간 단위는 미확정 |
| `+0x08` | SPR AH=05h의 color-table word. 표시 시 `0x8000`을 OR해 전달 | 직접 확인 |
| `+0x0A` | SPR AH=05h에 넘기는 raw 16-bit attribute word. FreeTOWNSOS `SPR_SETATTRIBUTE`는 `ESI & 0xFFFF`를 그대로 기록하고, 다중 셀 출력은 설정에 따라 이 값을 1 또는 4씩 증가시킨다. 타이틀 P의 raw `0xA0`가 실제 pattern entry `0xA0`을 표시하고 FreeTOWNSOS 테스트도 같은 번호를 짝지으므로 게임에서 등록 번호와 raw attribute 번호가 일치하는 관례는 확인됐다. 임의의 raw word에서 하위 10비트/상위 비트가 어떻게 해석되는지는 로컬 구현이 디코드하지 않는다. | raw 전달/기록, 타이틀 P의 단일 슬롯 대응, 격자 증가량은 직접 확인; 전체 비트 필드 의미는 미확정 |
| `+0x0C`, `+0x0E` | 공용 충돌 함수 `0x27F04`가 경계 계산에 사용하는 x/y 경계 오프셋 | 직접 확인; 게임상 hitbox 이름은 미부여 |
| `+0x10` | 현재 구역의 객체 상태 번호이며 해당 구역의 상태 점프표로 전달 | 직접 확인; 번호의 뜻은 구역별 |
| `+0x12` | 이동/애니메이션 상태에서 0–15 순환 카운터. `+0x1A`가 0이면 dword 표 `0x3F754`, 0이 아니면 `0x3F794`에서 값을 골라 `+0x0A`에 기록 | 해당 공용 상태에서 직접 확인 |
| `+0x14` | 표시·갱신 루프의 active word. 1일 때 처리되고 표시 경로가 처리 뒤 0으로 내림 | 직접 확인 |
| `+0x16`, `+0x18` | SPR 격자의 폭·높이(셀 수). AH=04h/AH=05h에 전달되며 풀의 연속 descriptor 순회도 폭×높이만큼 건너뜀 | 직접 확인 |
| `+0x1A` | 위 16단계 attribute lookup 표 둘 중 하나를 고르는 word | 공용 이동 상태에서만 직접 확인 |
| `+0x1C`–`+0x26` | 상태별 처리기가 읽고 쓰는 추가 word/dword 영역. 전체 상태에서 통일된 필드 의미는 아직 확인하지 않음 | 일부 주소 사용만 확인 |
| `+0x28` | 몇몇 공용 업데이트가 2/3 값을 분기 선택자로 검사한다. 2는 위치 증분과 16단계 attribute 시퀀스 갱신, 3은 `+0x0A`를 증가시키는 별도 경로 | 해당 두 동작에서 직접 확인; 다른 값의 포괄적 의미는 미확정 |

로컬 FreeTOWNSOS `SPR_DEFINE` 구현은 패턴 RAM의 시작 오프셋을 `128 × (ECX & 0x03FF)`로 계산하고, `EAX bit 0`이 0 이면 16 색 패턴(셀당 128 bytes), 1 이면 32K색 패턴(셀당 512 bytes) 크기를 사용한다. `EDX`의 두 byte 곱만큼 연속 셀을 복사한다. 게임의 `0x33CF4` 래퍼는 호출 인자를 AL(색상 모드), ECX(시작 번호), DH/DL(가로·세로 셀 수), ESI(원본 버퍼)로 전달한다. 초기 ALLTY_1/2.PAT 등록은 AL=0·16×16이며, 플레이어 패턴 재등록은 4×1, ROLL_G.PAT 등록은 16×24다. 반면 `SPR_SETATTRIBUTE`에서 `ECX`는 sprite register 시작 인덱스, `EDX`의 상·하위 byte는 폭·높이, `ESI`는 raw attribute word, `EDI`는 color-table word다. 이 함수는 sprite register의 attribute word에 ESI를 그대로 쓰며, color-table bit 15 가 켜지면 여러 셀에 기록할 때 raw attribute를 1 씩 올리고 꺼져 있으면 4 씩 올린다. 게임은 디스크립터 `+0x08 | 0x8000`을 color-table 인자로 주므로 격자 내 `+0x0A` 시작 raw 값이 1 씩 증가한다. 이 게임에서 등록 번호와 raw attribute 번호가 같은 관례를 쓴다는 것은 타이틀 P (`0xA0`)와 FreeTOWNSOS `sprite01.c`의 동일 번호 사례로 확인됐다. API 인자 분리 및 패턴 복사 목적지는 FreeTOWNSOS 소스에서 직접 확인되며, 임의 attribute word의 전체 비트 필드 의미는 그 코드에서 디코드되지 않는다.

이 구별은 최종 구역 상태 10도 설명한다. descriptor `+0x0A`의 시작값은 48셀 블록마다 `0x30`씩 바뀌고, `+0x08`은 `0x01D6`와 `0x2000` 사이에서 전환된다. 별도 출력 루프는 `0x326 + drawIndex` 스프라이트 레지스터를 설정하므로, descriptor 필드 두 개를 그 레지스터 인덱스와 혼동하면 안 된다. 일반 ENE 처리기가 `+0x10` 상태와 `+0x0A` 시퀀스를 설정한 뒤 어느 `PAT` 등록 범위를 참조하는지는 각 처리기별 추적표에 연결한다.

이 구조는 화면 자원을 다음과 같이 이어 준다: `M` 맵의 1-byte 타일 ID → `32K` 이미지의 512-byte 타일 → EGB 블록 출력; `ENE` 이벤트 ID → 44-byte 객체 디스크립터의 raw SPR attribute/크기 → SPR 위치·속성 API; UI 문자열 바이트 → `0x26C9C` → SPR 속성 API; Shift-JIS 문장 레코드 → EGB AH=60h → 시스템 폰트 ROM. 타이틀 P에서 동일 번호 슬롯 대응이 확인됐지만, 각 적·M 오버레이의 실제 도형 이름 및 arbitrary raw attribute의 모든 비트 의미는 별도 대조 대상이다. 따라서 제목 누락·타일 배경·적 스프라이트·일반 문장을 하나의 “폰트 문제”로 섞어서는 안 된다.

## 영문 패치가 바꾼 부분

일본 원판 ZIP의 96개 게임 파일은 영문 패치 ISO에도 모두 있으며, 공통 파일 가운데 95개는 바이트 단위로 같고 `ALLTYNEX.EXP`만 다르다. EXP 양쪽 크기는 267,304 bytes다. EXP 파일의 변경 바이트 2,296개(354개 연속 run)는 raw 파일 오프셋 `[0x3BFEC, 0x3F2A6)`에만 있고, P3 해제 이미지에서는 `[0x3BDDC, 0x3F096)`에 대응한다. P3 literal 주소 매핑과 화면 문구 EGB 74개 레코드·ASCII 10개 문자열을 대조해 2,296 bytes 전체를 분류했으며 미분류 차이는 없다. 문자열 필드 외 코드/헤더/패딩 차이는 확인되지 않았다. 이 비교에서 공통 게임 파일의 `ALLTYNEX.EXP` 이외 95개와 각 PAT/DAT/EUP는 바이트 동일하다. EGB 74행 집계에는 대조표가 놓쳤던 공통 크레딧 row 0도 보충했으며, 이 행은 수정 바이트 합계에는 변화가 없다.

즉 영문 패치는 새 출력기를 구현한 것이 아니라 원문 데이터를 바꿔 기존 EGB/SPR 경로를 그대로 사용한다. 문장별 원문·영문 비교는 이 절의 아래 표에 기록한다. PROJECT@RAID@WIND@2 는 영문 패치의 EGB 본문 번역 구간과 별개로 유지되는 SPR 타이틀 문자열이다.

일본 비공백 EGB62 행·영문 65 행의 위치 합집합은 74 행이고 그중 71 개 payload가 다르다. ASCII77 항목 중 10 항목 107 bytes가 다르다. EGB2189+ASCII107=2296 bytes로 모든 차이가 설명된다. 원본 EGB x/y/len 머리글과 tail padding은 동일하고 len은 40 이다. P3 헤더와 68-token 제어 서명도 같으며 변경은 literal payload 안에 있다. 해당 EGB74 행의 raw→runtime 차이 0x210 은 이 레코드 집합에만 적용된다. 전체 EXP의 상수 주소 변환으로 일반화하지 않는다.

### 추출 및 정리 방법

- EGB 문자열은 실행 파일의 6-byte x/y/byte_length 머리글과 80-byte 문자열 저장 영역을 기준으로 추출했다. 원본의 len은 40바이트다. 표의 오프셋은 ALLTYNEX.EXP 시작 기준 16 진수이며, 좌표도 함께 적었다.
- 이 표의 `EXP:file+0x…` 좌표는 압축 P3 파일의 raw 바이트 오프셋이다. 압축 해제된 실행 이미지 주소와 직접 비교하지 않는다. 예: 타이틀 raw 파일 `0x3F32E`는 런타임 이미지 `0x3F1FC`에, EGB 날짜 raw 파일 `0x3E910`은 런타임 이미지 `0x3E700`에 대응한다.
- 전각 라틴 문자/숫자와 전각 공백은 읽기 편하게 반각 문자/공백으로 바꿨다. 필드의 NUL 패딩과 양끝 공백은 제거했다. 일본어 문장 자체는 번역하거나 고쳐 쓰지 않았다. 이 절의 표는 초기 추출의 열람용 정규화 결과다. 실제 번역 CSV의 일본 원문은 선행 전각공백을 보존하므로, 이 표에서 trim된 문구를 CSV 원문 바이트 그대로라고 취급하지 않는다.
- ASCII UI 문자열에서 게임의 @ 공백 표시는 공백으로 표시했다. 원문과 영문 패치 각각의 철자와 대소문자를 보존했다. 원문의 NOMAL·HARF는 영문 패치에서 NORMAL·HALF로 바뀐 항목과 구분했다. ASCII 문자열은 0x3F342 까지 확인해 변경 구간 뒤의 타이틀 문자열도 포함했다.
- 0x3F32E의 PROJECT@RAID@WIND@2 는 원문과 영문 패치에 공통으로 저장된 타이틀 문구라 표에 포함했다. 이 항목은 EGB 좌표/길이 레코드가 아니다. 사용자가 제공한 디버거 자료의 `0x2DB94` 호출과 정적 문자열 위치 대조에서 기존 `0x26C9C` SPR 문자 루프에 연결된다. 따라서 이 타이틀은 EGB 시스템 폰트 문자열 경로의 테스트 대상이 아니다.
- 추가 대조: 크레딧 EGB 테이블의 row 0 (`EXP:file+0x3C6B8`, `runtime+0x3C4A8`)에도 같은 `PROJECT RAID WIND 2` 문구가 전각 문자로 들어 있다. 레코드는 `(92,512)`, `len=40`이며 원문·영문판 바이트가 동일하다. 이 EGB 크레딧 표시는 SPR 타이틀 화면과 다른 출력 경로이므로 EGB 레코드 수에 포함한다.
- 파일명 같은 내부 리소스 키는 화면 문구 목록에서 제외했다. 이 문서는 EXP에 문자열로 저장된 문구만 다루며, 그래픽 리소스에 그림으로 들어간 로고/문자는 포함하지 않는다.

### 미션 안내 및 ASCII UI 문자열

| EXP 오프셋 | 원문 EXP | 영문 패치 EXP |
|---:|---|---|
| 0x3BFEC | MAKE AN ASSAULT ON ENEMY | ATTACK THE ENEMY |
| 0x3C008 | TARGET DESTROYED | TARGET DESTROYED |
| 0x3C01C | FIRST AREA IS OVER | FIRST AREA IS OVER |
| 0x3C0F0 | SECOND AREA | SECOND AREA |
| 0x3C0FC | ATTACK THE ZLDYZANT BASE | ATTACK THE ZLDYZANT BASE |
| 0x3C118 | TARGET DESTROYED | TARGET DESTROYED |
| 0x3C12C | SECOND AREA IS OVER | SECOND AREA IS OVER |
| 0x3C204 | THIRD AREA | THIRD AREA |
| 0x3C210 | THE BITING COLD WIND | THE BITTER COLD WIND |
| 0x3C228 | TARGET DESTROYED | TARGET DESTROYED |
| 0x3C23C | THIRD AREA IS OVER | THIRD AREA IS OVER |
| 0x3C2FC | FORTH AREA | LAST AREA |
| 0x3C308 | LAST DEFENCE LINE | LAST DEFENSE LINE |
| 0x3C31C | TARGET DESTROYED | TARGET DESTROYED |
| 0x3C330 | FORTH AREA IS OVER | LAST AREA IS OVER |
| 0x3C620 | FINAL AREA | FINAL AREA |
| 0x3C62C | AGGRESSIVE ATTACK | AGGRESSIVE ATTACK |
| 0x3C640 | TARGET DESTROYED | TARGET DESTROYED |
| 0x3C654 | FINAL TARGET | FINAL TARGET |
| 0x3C664 | ALLTYNEX | ALLTYNEX |
| 0x3E1B0 | %d | %d |
| 0x3E1BC | %d | %d |
| 0x3E264 | NOW LOADING | NOW LOADING |
| 0x3E27C | CONTINUE= | CONTINUE= |
| 0x3E288 | CREDIT | CREDIT |
| 0x3E294 | %1d | %1d |
| 0x3E298 | GAME OVER | GAME OVER |
| 0x3E2C8 | PRESS RUN TO START | PRESS RUN TO START |
| 0x3E2DC | 1996:10 SATOSHI YOSHIDA  < | 1996 SATOSHI YOSHIDA  EN1:2 |
| 0x3E2F8 | 1PLAYER | 1PLAYER |
| 0x3E300 | 2PLAYER | 2PLAYER |
| 0x3E308 | 1P AND 2P | 1P AND 2P |
| 0x3E314 | OPTION | OPTION |
| 0x3E31C | VERY EASY | VERY EASY |
| 0x3E33C | EASY | EASY |
| 0x3E35C | NOMAL | NORMAL |
| 0x3E37C | HARD | HARD |
| 0x3E39C | VERY HARD | VERY HARD |
| 0x3E3BC | STEREO | STEREO |
| 0x3E3DC | MONO | MONO |
| 0x3E3FC | OFF | OFF |
| 0x3E41C | ON | ON |
| 0x3E43C | NO | NO |
| 0x3E45C | YES | YES |
| 0x3E47C | FULL | FULL |
| 0x3E49C | HARF | HALF |
| 0x3E57C | NOPLAYER | NOPLAYER |
| 0x3E590 | OPTION | OPTION |
| 0x3E598 | GAME LEVEL | GAME LEVEL |
| 0x3E5AC | LEFT                    %d | LIFE                    %d |
| 0x3E5C8 | AUDIO | AUDIO |
| 0x3E5DC | REFLECT ATTACK | REFLECT ATTACK |
| 0x3E5F4 | AUTO SLOW DOWN | AUTO SLOW DOWN |
| 0x3E60C | QUIT GAME | QUIT GAME |
| 0x3E624 | WAIT | WAIT |
| 0x3E638 | DATA RESET | DATA RESET |
| 0x3E650 | EXIT | EXIT |
| 0x3E658 | 0123456789:;<=>? ABCDEFGHIJKLMNOPQRSTUVWXYZ | 0123456789:;<=>? ABCDEFGHIJKLMNOPQRSTUVWXYZ |
| 0x3E798 | RANK | RANK |
| 0x3E7A0 | SCORE | SCORE |
| 0x3E7A8 | NAME | NAME |
| 0x3E7B0 | %000006d00 | %000006d00 |
| 0x3E7BC | VERY EASY | VERY EASY |
| 0x3E7DC | EASY | EASY |
| 0x3E7FC | NOMAL | NOMAL |
| 0x3E81C | HARD | HARD |
| 0x3E83C | VERY HARD | VERY HARD |
| 0x3E85C | OFF | OFF |
| 0x3E87C | ON | ON |
| 0x3E89C | 1996:10 SATOSHI YOSHIDA  < | HIGH SCORE TABLE |
| 0x3E8B8 | RANKING | RANKING |
| 0x3E8C0 | GAME LEVEL | GAME LEVEL |
| 0x3E8D0 | REFLECT ATTACK | REFLECT ATTACK |
| 0x3E8E4 | %000006d00 | %000006d00 |
| 0x3E8F0 | SLOW | SLOW |
| 0x3E8F8 | AREA | AREA |
| 0x3F32E | PROJECT RAID WIND 2 | PROJECT RAID WIND 2 |

### Shift-JIS 시스템 폰트 문자열 레코드

| EXP 오프셋 | 화면 좌표 (x,y) | 원문 일본어 | 영문 패치 |
|---:|---:|---|---|
| 0x3C41C | (80, 200) | 西暦2230年 | 2230 A.D. |
| 0x3C472 | (80, 160) | 「ALLTYNEX」の | ALLTYNEX and its |
| 0x3C4C8 | (80, 200) | 完全破壊確認後、地球の管理下にあった | global network of |
| 0x3C51E | (80, 240) | ネットワ-クの全てが停止、 | control is defeated. |
| 0x3C574 | (80, 200) | コンピュ-タによる人類殲滅作戦は | Humanity refuses to |
| 0x3C5CA | (80, 240) | 失敗におわった。 | be snuffed out... |
| 0x3C6B8 | (92, 512) | PROJECT RAID WIND 2 (전각) | PROJECT RAID WIND 2 (전각) |
| 0x3C70E | (92, 32) | ALLTYNEX | ALLTYNEX |
| 0x3C7BA | (80, 96) | STAFF | STAFF |
| 0x3C968 | (80, 256) | 原案・企画 | ORIGINAL CONCEPT |
| 0x3CA14 | (80, 320) | 吉田 哲 | Satoshi Yoshida |
| 0x3CB16 | (80, 416) | — | GRAPHICS, VIDEO, AND |
| 0x3CB6C | (80, 448) | プログラム・グラフィック・音楽 | PROGRAMMING |
| 0x3CC18 | (80, 512) | 吉田 哲 | Satoshi Yoshida |
| 0x3CD1A | (80, 96) | — | VOICE EFFECTS |
| 0x3CD70 | (80, 128) | VOICE | — |
| 0x3CDC6 | (80, 160) | — | Y. Uemura (YASUWARE) |
| 0x3CE1C | (80, 192) | 上村 康幸(ヤスウェア) | — |
| 0x3CEC8 | (80, 256) | — | SOUND EFFECTS |
| 0x3CF74 | (80, 320) | 効果音協力 | Mitsuru Takaya |
| 0x3D020 | (80, 384) | 高谷 充 | — |
| 0x3D076 | (80, 416) | — | SUPERVISION |
| 0x3D122 | (80, 480) | — | Takayuki Iida |
| 0x3D178 | (80, 512) | シナリオ監修 | — |
| 0x3D224 | (80, 64) | 飯田 孝之 | COLLABORATORS |
| 0x3D2D0 | (80, 128) | — | Takayuki Iida |
| 0x3D326 | (80, 160) | — | Naoya Irie |
| 0x3D37C | (80, 192) | — | Yuji Suzuki |
| 0x3D3D2 | (80, 224) | — | Mitsuru Takaya |
| 0x3D428 | (80, 256) | 協力 | Ryuji Nishikawa |
| 0x3D47E | (80, 288) | 飯田 孝之 | Daisuke Hashimoto |
| 0x3D4D4 | (80, 320) | 入江 尚哉 | Hirofumi Hirose |
| 0x3D52A | (80, 352) | 上村 康幸(ヤスウェア) | Nobuji Mukai |
| 0x3D580 | (80, 384) | 鈴木 勇児 | Toru Muneyuki |
| 0x3D5D6 | (80, 416) | 高谷 充 | — |
| 0x3D62C | (80, 448) | 西川(くるた)龍司 | — |
| 0x3D682 | (80, 480) | 橋本 ダイスケ | — |
| 0x3D6D8 | (80, 512) | 広瀬 博文 | — |
| 0x3D72E | (80, 32) | 向井 伸治 | ENGLISH TRANSLATION |
| 0x3D784 | (80, 64) | 宗行 徹 | — |
| 0x3D7DA | (80, 96) | (五十音順) | Derek Pascarella |
| 0x3D830 | (80, 128) | — | (a.k.a. “ateam”) |
| 0x3D8DC | (80, 192) | — | Walnut |
| 0x3DD90 | (80, 128) | 平成八年度作品・製作・著作者 | PRODUCED AND CREATED |
| 0x3DE3C | (80, 192) | 吉田 哲 | BY SATOSHI YOSHIDA |
| 0x3E910 | (80, 200) | 西暦2192年 | 2192 A.D. |
| 0x3E966 | (80, 360) | 新型の外宇宙航海用推進機関の開 | Humans advance far |
| 0x3E9BC | (80, 400) | 発の成功により、人類は太陽系外へ | into space with new |
| 0x3EA12 | (80, 440) | の進出を可能とした。 | rocket technology. |
| 0x3EA68 | (80, 400) | 「第2次大航海時代」の到来である。 | A new era dawns... |
| 0x3EABE | (80, 360) | 政治、技術、文化、全ての分野において | Humanity was at its |
| 0x3EB14 | (80, 400) | 活気に満ちあふれた人類は、有史以来最大の | greatest peak in all |
| 0x3EB6A | (80, 440) | 全盛期を迎えていた。 | of recorded history. |
| 0x3EBC0 | (80, 360) | 恒星系級汎用管理コンピュ-タ | A space―age ALLTYNEX |
| 0x3EC16 | (80, 400) | 「ALLTYNEX」の誕生はその繁栄を | computer was said to |
| 0x3EC6C | (80, 440) | 揺るぎないものにした。するはずであった。 | assure prosperity. |
| 0x3ECC2 | (80, 160) | 「ALLTYNEX」に組み込まれた | Its state―of―the―art |
| 0x3ED18 | (80, 200) | WC-101型アクティブAIは、自身 | WC―101 A.I. claimed |
| 0x3ED6E | (80, 240) | で必要なデ-タを収集及び解析、さらに | superiority over all |
| 0x3EDC4 | (80, 280) | 推論・思考まで可能な最新AIである。 | human intelligence. |
| 0x3EE1A | (80, 200) | ある日、このAIは開発者さえ | But this A.I. began |
| 0x3EE70 | (80, 240) | 予想しなかった機能を発揮しはじめる。 | to exceed design... |
| 0x3EEC6 | (80, 200) | 「自己進化」を始めたのである。 | It was evolving... |
| 0x3EF1C | (80, 160) | この事実に危機感を覚えた開発者は | Its designers begged |
| 0x3EF72 | (80, 200) | 元老院に「ALLTYNEX」の一時停 | the Senate to power |
| 0x3EFC8 | (80, 240) | 止及び調査を要請、激しい議論が繰り返 | it down. They agreed |
| 0x3F01E | (80, 280) | された末に、条件付きで承認された。 | and investigated... |
| 0x3F074 | (80, 360) | しかし、すでに自我を持つまでに至ってい | But ALLTYNEX refused |
| 0x3F0CA | (80, 400) | た「ALLTYNEX」は停止命令を拒絶、 | and began to wage |
| 0x3F120 | (80, 440) | 更に人類を敵と判断し攻撃を開始した。 | war on humanity! |
| 0x3F176 | (80, 360) | 軍の管理まで「ALLTYNEX」に任 | ALLTYNEX controlled |
| 0x3F1CC | (80, 400) | せていた人類は抵抗する術をもたず、苛烈な | every nation’s army. |
| 0x3F222 | (80, 440) | 攻撃により人口を急激に減らしていった。 | We were hopeless. |
| 0x3F278 | (80, 200) | 人類は誕生以来最大の危機にさらされていた | Was this the end...? |

## 분석 한계와 남은 쟁점

- EGB 래퍼 직접 CALL은 원본 EXP 재대조에서 58개(엔딩 12·스탭롤 1·오프닝 45)로 확인했다. 이전 57개 기록은 집계 오류로 정정했다.
- 각 함수의 완전한 의미 호출 그래프, 스테이지 내부 모든 완료조건과 모든 ENE/상태의 실제 화면상 이름은 복원하지 않았다. raw attribute 전체의 하드웨어 비트 형식·PAT fetch·색상표 적용 도형도 타이틀P 단일 사례를 모든 객체로 확대하지 않는다.
- CFGDAT byte5, 레코드 `+0x11/+0x16`의 게임 규칙상 의미, 추가28행의 출처·선택 조건, 비정상 헤더의 clamp/reject는 미확정이다. 첫100행의 난이도5×반격탄2 그룹은 확인했다. QUIT GAME은 정리 후 옵션 반환까지 연결되지만 README의DOS 종료 설명과 맞는 최종 종료 경로는 찾지 못했다.
- 플레이어 `R+2`의 게임상 이름, `R+0x08/+0x0E/+0x1C` 의미 및 별도 무적 플래그는 미확정이다. 점수 타이머를 무적 타이머로 부르지 않는다.
- M 소비 표는 실제 direct read, 조건부 후보, rewind와 포인터 대입을 구별한다. cadence·selector 재진입에 따른 모든 파일별 실제 방문 횟수는 확정하지 않았다. PLAYDEMO cursor의 반복당 소비 수·상한·녹화 생성 규칙·끝zero의 의도도 미확정이다.
- 음원은 EUP→프로그램→FMB/PMB→split/soundID→voice/파형까지 연결했다. 내부 시간 예산을 화면프레임·초로 환산하는 일, 개별FM 음색 청감 평가, 효과음/PCM을 ENE·화면효과에 귀속하는 일은 별도 범위다.

한글화가 완료되었기에 더 이상의 분석은 불필요하기에 분석을 중단했다.
