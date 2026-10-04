# Build Input Images

한글 패치 빌드에 사용하는 원본 게임 ZIP과 FreeTOWNSOS 부팅 ISO를 두는 폴더다.

## 파일 구성

| 파일 | 용도 |
| --- | --- |
| `alltynex_fmtowns.zip` | 일본 원판 게임 자료. 빌드가 ZIP 안의 게임 파일을 읽고, 완성 ISO를 복원하는 xdelta의 기준 파일로도 사용한다. |
| `CDIMG.ISO` | FreeTOWNSOS 부팅 입력. 빌드가 운영체제 파일과 부팅 구조를 가져와 게임 자동 실행 ISO를 만든다. |

FreeTOWNSOS의 상위 고지는 [FreeTOWNSOS-LICENSE.md](../../licenses/FreeTOWNSOS-LICENSE.md)에 있다.

## 원본 게임 준비

원본 Alltynex는 개발자가 [SITER SKAIN 배포 페이지](https://www.siterskain.com/artifact/)에서 무료로 제공한다. **ALLTYNEX for FM TOWNS** 링크로 받은 파일을 이 폴더에 그대로 둔다. 압축을 풀거나 다시 압축할 필요가 없다.

빌드는 다음 입력 파일의 SHA-256을 확인한다. 다른 버전이나 수정된 파일이면 오류로 중단한다.

| 파일 | SHA-256 |
| --- | --- |
| `alltynex_fmtowns.zip` | `19b662f038e50e99535f60dbe6e07a77e269f574ed9250d46fc0655bb2aa6b3a` |
| `CDIMG.ISO` | `cf05150bb1db4e82dc2fd7b617cf4dd8f222f88b36b06589054748b2097e7142` |

## 빌드

프로젝트 루트에서 실행한다.

```powershell
python tools/build_alltynex_korean_freeos_from_zip.py
```

결과는 `Output/Alltynex (Kor v1.0).iso`와 `Output/Alltynex (Kor v1.0).xdelta`다. 번역은 [문자열 CSV 안내](../Strings/README.md)를 참조한다. 전체 절차는 [한글 빌드 안내](../../doc/Alltynex-Korean-Build.md), 외부 자료 고지는 [THIRD-PARTY-NOTICES.md](../../licenses/THIRD-PARTY-NOTICES.md)에 있다.
