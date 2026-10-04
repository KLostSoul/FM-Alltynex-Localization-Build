# HANME Font

`han_hanme.fnt`는 한글 음절을 조합하는 데 사용하는 16×16 자모 폰트다. 원본은 [iolo/8x4x4-fonts](https://github.com/iolo/8x4x4-fonts/tree/main/src)에서 제공한다.

| 파일 | 용도 |
| --- | --- |
| `han_hanme.fnt` | 한글 패치 ISO 빌드에 사용하는 16×16 원형 자모 폰트 |
| `HANME.FNT` | 24×24로 변환한 자모 폰트 사본. 현재 ISO 빌드와 토큰표 생성 명령은 원형 폰트에서 직접 변환한다. |

## 빌드에서의 사용

빌드는 `tools/alltynex_font.py`로 자모 조각 360개를 24×24 비트맵으로 변환하고, 생성 ISO의 `/ALLTYNEX/HANME.FNT`에 넣는다. 변환한 FNT를 별도 출력 파일로 만들지는 않는다.

게임의 EGB 한글 출력 후크는 FNT를 메모리에 적재한 뒤 조합 토큰표가 지정하는 초성·중성·종성 비트맵을 OR 합성하여 음절을 출력한다. FNT에 완성형 음절을 하나씩 저장하는 방식이 아니다.

번역과 토큰표는 [문자열 CSV 안내](../Import/Strings/README.md), 전체 출력 과정은 [한글 빌드 안내](../doc/Alltynex-Korean-Build.md#4-fnt조합-토큰음절-합성)를 참조한다.

## License

Copyright (c) 2025 Dongsu Jang <iolo@kakao.com>.

SIL Open Font License 1.1을 적용한다. 전체 고지는 [LICENSE-OFL.txt](../licenses/LICENSE-OFL.txt), 출처와 적용 범위는 [서드 파티 공지](../licenses/THIRD-PARTY-NOTICES.md)에 있다.
