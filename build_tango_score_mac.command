#!/bin/bash
# Tango Music Score Generator - macOS .app builder (double-click in Finder)
cd "$(dirname "$0")" || exit 1

echo "====================================================="
echo "  Tango Music Score Generator - macOS App Builder"
echo "====================================================="

fail() { echo; echo "BUILD FAILED: $1"; echo "위 오류 메시지를 확인하세요."; read -n 1 -s -r -p "아무 키나 누르면 닫힙니다."; exit 1; }

echo; echo "[1/5] Python / Tk 확인..."
PY=$(command -v python3) || fail "python3 를 찾지 못했습니다. https://www.python.org/downloads/macos/ 에서 Python 3.10~3.13 설치 후 다시 실행하세요."
"$PY" --version
"$PY" -c "import tkinter" 2>/dev/null || fail "이 Python에 tkinter가 없습니다. python.org 설치본을 쓰거나, Homebrew라면 'brew install python-tk' 를 실행하세요."
for f in maximo_logo.png maximo_icon.ico maximo_icon.icns TangoMusicScoreGenerator_mac.spec; do
  [ -f "$f" ] || fail "$f 파일이 없습니다."
done

echo; echo "[2/5] 가상환경(.venv) 준비..."
[ -d .venv ] || "$PY" -m venv .venv || fail "가상환경 생성 실패"
source .venv/bin/activate

echo; echo "[3/5] 필수 패키지 설치 (최초 1회 인터넷 필요)..."
python -m pip install --upgrade pip || fail "pip 업그레이드 실패"
python -m pip install --upgrade pyinstaller librosa soundfile numpy scipy numba llvmlite audioread pooch soxr || fail "패키지 설치 실패"

echo; echo "[4/5] 이전 빌드 정리..."
rm -rf build dist

echo; echo "[5/5] .app 빌드 중 (수 분 걸릴 수 있습니다)..."
python -m PyInstaller --noconfirm --clean TangoMusicScoreGenerator_mac.spec || fail "PyInstaller 빌드 실패"

# 다른 Mac으로 옮길 때 쓰는 zip (macOS 확장 속성 보존)
if command -v ditto >/dev/null 2>&1; then
  ditto -c -k --sequesterRsrc --keepParent dist/TangoMusicScoreGenerator.app dist/TangoMusicScoreGenerator_mac.zip
fi

echo; echo "====================================================="
echo " BUILD COMPLETE"
echo " 앱:  $(pwd)/dist/TangoMusicScoreGenerator.app"
echo " zip: $(pwd)/dist/TangoMusicScoreGenerator_mac.zip  (다른 Mac 배포용)"
echo "====================================================="
open dist
read -n 1 -s -r -p "아무 키나 누르면 닫힙니다."
