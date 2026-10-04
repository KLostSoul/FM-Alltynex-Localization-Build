# Build Inputs

한글 패치 빌드에 사용하는 게임·부팅 자료와 번역 CSV를 모아 둔 폴더다.

| 폴더 | 내용 | 안내 |
| --- | --- | --- |
| `Img` | 원본 게임 ZIP과 FreeTOWNSOS 부팅 ISO | [이미지 입력 안내](Img/README.md) |
| `Strings` | 번역 문자열·출력 좌표와 한글 조합 토큰 CSV | [문자열 CSV 안내](Strings/README.md) |

번역과 EGB 출력 좌표는 `Strings/Alltynex_Korean.csv`에서 편집한다. `Strings/Alltynex_Hangul_Tokens.csv`는 빌드 과정에서 자동 갱신된다.

프로젝트 루트에서 다음 명령으로 빌드한다.

```powershell
python tools/build_alltynex_korean_freeos_from_zip.py
```

결과는 `Output/Alltynex (Kor v1.0).iso`와 `Output/Alltynex (Kor v1.0).xdelta`다. 전체 절차는 [한글 빌드 안내](../doc/Alltynex-Korean-Build.md)를 참조한다.
