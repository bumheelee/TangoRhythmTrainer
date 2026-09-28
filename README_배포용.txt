Tango Music Score Generator v2
Windows EXE 배포 안내

[1. 프로그램 소개]
Tango Music Score Generator v2는 음원 파일을 분석하여 탱고 리듬 트레이너에서 사용할 수 있는 OSZ 채보와 음악 분석 데이터를 자동으로 생성합니다.

입력: MP3 / WAV / FLAC / OGG / M4A / AAC / WMA 등
출력: OSZ / music_score_v2.json / 선택적으로 Events CSV

※ 생성되는 music_score_v2.json은 실제 악보를 그대로 복원한 것이 아니라 음원에서 추출한 박자·온셋·강세·음역·스펙트럼 등의 정보를 이용한 '음악 구조 데이터'입니다.

[2. 실행]
TangoMusicScoreGenerator.exe를 더블클릭합니다.
Python 설치는 필요하지 않습니다. (EXE가 정상적으로 빌드된 경우)

[3. 기본 사용법]
① 음원 폴더 → 찾아보기 → 음원이 들어 있는 폴더 선택
② 출력 폴더 → 결과를 저장할 폴더 선택
③ 기본 설정은 Lv1/Lv2/Lv3 모두 생성, Musical Mode입니다.
④ '▶ 음원 일괄 분석 및 OSZ 생성' 클릭
⑤ 처리 로그에서 진행 상황 확인
⑥ 완료 후 출력 폴더의 OSZ 파일을 사용합니다.

[4. 주요 옵션]
기본 Level: Lv1 / Lv2 / Lv3 중 하나를 기본 채보 난이도로 선택합니다.
Lv1은 단순한 리듬 중심, Lv2는 중간 밀도, Lv3는 보다 촘촘한 이벤트를 사용하는 용도입니다.

Mode:
- musical: 음악적 강세와 음원 이벤트를 종합한 기본 모드
- tango: 탱고 리듬 특성을 반영한 이벤트 선택
- beat: 박자 중심
- salient: 두드러지는 온셋 중심
- instrument: 음역/악기 역할에 가까운 이벤트 분류 중심

Lv1/Lv2/Lv3 모두 생성: 한 음원에서 세 난이도를 동시에 생성합니다.
모든 Mode 생성: 선택 가능한 모든 채보 모드를 생성합니다. 파일 수가 크게 늘어날 수 있습니다.
하위 폴더 포함: 선택한 폴더 아래의 하위 폴더까지 음원을 검색합니다.
Events CSV 생성: 분석된 음악 이벤트를 CSV로 저장합니다.

박자: 기본 4박. 2/3/4 중 선택합니다.
Subdivision: 한 박을 2/4/8분할하여 분석/채보 기준으로 사용합니다.
Offset(ms): 전체 채보 타이밍을 밀리초 단위로 보정합니다. 예: 50이면 50ms 늦게 시작하도록 조정합니다.
Downbeat: 다운비트 기준을 직접 지정할 때 사용합니다. 일반적인 사용에서는 비워두는 것을 권장합니다.
Pack 이름: OSZ 내부의 Beatmap/팩 관련 이름으로 사용됩니다.

[5. 출력 예]
음원: Mi dolor.mp3

출력 폴더:
Mi dolor - music_score_v2.json
Mi dolor - musical-Lv1.osz
Mi dolor - musical-Lv2.osz
Mi dolor - musical-Lv3.osz
Mi dolor - events.csv (CSV 옵션 사용 시)

[6. OSZ 사용]
생성된 .osz 파일은 기존 Tango 리듬 트레이너 HTML에서 불러올 수 있습니다.
OSZ 내부에는 채보(.osu)와 해당 음원이 포함됩니다.

[7. 권장 설정]
처음 사용하는 경우:
- Mode: musical
- Lv1/Lv2/Lv3 모두 생성: 체크
- 모든 Mode 생성: 체크하지 않음
- 하위 폴더 포함: 필요할 때만 체크
- Events CSV: 분석 결과를 확인하고 싶을 때만 체크
- 박자: 4
- Subdivision: 4
- Offset: 0
- Downbeat: 공란

[8. 오류가 발생하는 경우]
'No module named librosa'와 같은 오류가 EXE에서 발생한다면 EXE가 잘못 빌드된 것입니다. 배포용으로는 의존성 수집이 적용된 최신 빌드를 사용해야 합니다.

특정 음원에서 분석 오류가 발생하면 해당 음원의 파일 형식과 처리 로그를 확인합니다.

[9. 중요한 한계]
이 프로그램은 음원에서 실제 종이 악보를 복원하는 프로그램이 아닙니다.
BPM, beat, onset, 강세, 음역, 스펙트럼 등의 정보를 기반으로 리듬게임용 채보를 자동 생성합니다.
따라서 실제 연주자의 정확한 멜로디/화음/악기별 악보와 완전히 일치하지 않을 수 있습니다.
