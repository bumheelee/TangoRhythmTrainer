#!/bin/bash
# 빌드 없이 바로 실행 (Python 소스 실행 모드). 최초 1회만 패키지를 설치합니다.
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3) || { echo "python3 가 필요합니다: https://www.python.org/downloads/macos/"; read -n 1 -s -r; exit 1; }
"$PY" -c "import tkinter" 2>/dev/null || { echo "tkinter 없음. python.org 설치본 사용 또는 'brew install python-tk'"; read -n 1 -s -r; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
python -c "import librosa, soundfile" 2>/dev/null || python -m pip install --upgrade pip librosa soundfile numpy scipy numba llvmlite audioread pooch soxr
python tango_music_score_gui.py
