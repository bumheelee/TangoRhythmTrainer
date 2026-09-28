Tango Music Score Generator v2 - macOS 버전

■ 방법 A. 바로 실행 (가장 간단)
1. 이 폴더 전체를 Mac에 복사합니다.
2. Python 3.10~3.13 설치 (https://www.python.org/downloads/macos/ 의 설치본 권장 - tkinter 포함).
3. run_tango_score_mac.command 를 더블클릭합니다. (최초 1회 패키지 자동 설치, 인터넷 필요)

■ 방법 B. 독립 실행 앱(.app) 만들기
1. build_tango_score_mac.command 를 더블클릭합니다.
2. 끝나면 dist/TangoMusicScoreGenerator.app 이 생성됩니다. Applications 폴더로 옮겨 쓰면 됩니다.
3. 다른 Mac에 배포할 때는 dist/TangoMusicScoreGenerator_mac.zip 을 전달하세요.
   (앱은 빌드한 Mac과 같은 칩(Apple Silicon/Intel)에서 동작합니다. 양쪽에서 쓰려면 각각 빌드하세요.)

■ 처음 실행 시 막힐 때
- .command 파일이 "권한 없음"으로 안 열리면 터미널에서:  chmod +x *.command
- "확인되지 않은 개발자" 경고: 파일을 우클릭 → 열기 → 열기.  또는 터미널에서:
    xattr -cr TangoMusicScoreGenerator.app
- 개발자 인증서로 서명/공증하지 않은 앱이라 위 경고는 정상입니다.
- 음원 폴더 접근 권한 팝업이 뜨면 "허용"을 누르세요.

■ 참고
- Windows용은 기존 build_tango_score_exe.bat 를 그대로 사용하세요.
- 로고: maximo_logo.png (GUI 상단), maximo_icon.icns (앱 아이콘).

■ 키 수 설정
- GUI의 "키 수"에서 2키/4키 중 선택합니다 (기본 2키). 선택한 키 수에 맞춰 OSZ가 생성되며 파일명 끝에 -2K / -4K 가 붙습니다.
- 탱고 리듬 트레이너(휴대폰)는 2키/4키 채보를 모두 읽을 수 있고, 2키가 좌우 탭 화면과 가장 잘 맞습니다.

■ 학생 배포용 (학생배포용 폴더)
- 탱고_리듬_트레이너.html : 학생 휴대폰/PC에서 실행하는 리듬 트레이너
- 탱고_리듬_트레이너_사용법.png : 카카오톡 공유용 사용법 이미지
- 구글드라이브에는 html 파일과 songs 폴더(곡명.osz)를 공유하세요.
