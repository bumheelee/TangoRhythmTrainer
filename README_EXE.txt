Tango Music Score Generator v2 - Windows EXE 만들기

1. 이 폴더 전체를 Windows PC로 복사합니다.
2. Python 3.10~3.13이 설치되어 있는지 확인합니다.
3. build_tango_score_exe.bat 를 더블클릭합니다.
4. 빌드가 끝나면 dist\TangoMusicScoreGenerator.exe 가 생성됩니다.
5. 이후에는 생성된 EXE만 다른 PC에서 실행할 수 있습니다.

포함 파일: maximo_logo.png / maximo_icon.ico (MAXIMO TANGO 로고 - GUI 상단 및 EXE 아이콘). 빌드 시 자동으로 EXE에 포함됩니다.

주의:
- 최초 EXE 빌드 시 인터넷 연결이 필요합니다. PyInstaller 및 분석 라이브러리를 설치합니다.
- 생성된 EXE는 음원 폴더를 선택하고 Lv1/Lv2/Lv3, mode, 하위폴더 검색 등을 GUI에서 설정할 수 있습니다.
- 출력물은 OSZ + music_score_v2.json이며, CSV 옵션을 켜면 events.csv도 생성합니다.

■ 키 수 설정
- GUI의 "키 수"에서 2키/4키 중 선택합니다 (기본 2키). 선택한 키 수에 맞춰 OSZ가 생성되며 파일명 끝에 -2K / -4K 가 붙습니다.
- 탱고 리듬 트레이너(휴대폰)는 2키/4키 채보를 모두 읽을 수 있고, 2키가 좌우 탭 화면과 가장 잘 맞습니다.

■ 학생 배포용 (학생배포용 폴더)
- 탱고_리듬_트레이너.html : 학생 휴대폰/PC에서 실행하는 리듬 트레이너
- 탱고_리듬_트레이너_사용법.png : 카카오톡 공유용 사용법 이미지
- 구글드라이브에는 html 파일과 songs 폴더(곡명.osz)를 공유하세요.
