# 현재 빌드 도구

실제 배포 빌드는 다음 명령으로 실행합니다.

```bat
python tools\build_alltynex_korean_freeos_from_zip.py
```

- `build_alltynex_korean_freeos_from_zip.py`: Import 원본 ZIP과 번역 CSV를 사용하여 Output에 FreeTOWNSOS 한글 ISO와 원본 ZIP 기준 xdelta를 생성합니다.
- `alltynex_xdelta.py`: xdelta3 실행 파일을 찾아 ZIP에서 ISO를 복원하는 패치를 생성합니다.
- `alltynex_lock.py`: 빌드·토큰표 갱신이 동시에 같은 자료를 변경하지 않도록 작업 공간을 잠급니다.
- `xdelta3.exe`: 공식 Windows x64 v3.2.1 실행 파일입니다. 상위 설명은 `xdelta3-README.md`, 라이선스는 [xdelta3-LICENSE.txt](../licenses/xdelta3-LICENSE.txt)에 있습니다.
- `build_hangul_composition_token_table.py`: 번역에 필요한 한글 음절의 조합 토큰표를 갱신합니다.
- `build_alltynex_ui_strings.py`: SPR UI 문자열·하단 크레딧 슬롯·잔존 N 초기화를 적용합니다.
- `alltynex_binary.py`: ISO 레코드, EXP/P3 처리와 기계어 작성 공통 코드입니다.
- `alltynex_font.py`: HANME 자모 구성과 24×24 폰트 생성 공통 코드입니다.
- `alltynex_egb.py`: 현재 EGB 한글 출력 후크와 문자열 레코드 생성 코드입니다.

부팅 OS 입력은 `Import/Img/CDIMG.ISO`다. 라이선스는 [안내](../licenses/THIRD-PARTY-NOTICES.md)를 참조한다. 통합 문서는 [한글 빌드](../doc/Alltynex-Korean-Build.md)에 있다.

Windows x64에서는 `tools/xdelta3.exe`를 사용한다. `--xdelta3 PATH`로 다른 실행 파일을 직접 지정할 수 있으며 다른 환경에서는 PATH에 설치된 xdelta3를 찾는다. xdelta 생성이 실패하면 전체 빌드도 실패로 표시한다.

ISO와 xdelta를 임시 경로에서 모두 생성한 뒤 결과 파일을 교체한다. 생성 실패 시 기존 결과를 보존하며, 교체 중 오류가 나면 이미 교체한 파일을 이전 결과로 복구한다.

복구도 실패하면 기존 파일의 백업을 삭제하지 않고 `Output/alltynex-build-*`에 보존한다. 빌드는 실패로 표시하며 로그에 복구 폴더를 출력한다. 해당 폴더의 `RECOVERY.txt`에 원래 파일을 복원할 위치가 기록된다.

같은 프로젝트에서 다른 빌드나 저장이 진행 중이면 새 작업은 파일을 변경하기 전에 중단한다. 잠금은 운영체제가 관리하며 정상 종료·오류·프로세스 종료 시 해제된다. 잠금 파일은 시스템 임시 폴더에 두며 Output에는 생성하지 않는다.
