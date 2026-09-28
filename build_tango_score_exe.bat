@echo off
setlocal
cd /d "%~dp0"

echo =====================================================
echo   Tango Music Score Generator - Windows EXE Builder
echo =====================================================

echo.
echo [1/4] Checking Python and logo files...
if not exist maximo_logo.png (echo maximo_logo.png is missing. & goto :error)
if not exist maximo_icon.ico (echo maximo_icon.ico is missing. & goto :error)
python --version
if errorlevel 1 goto :python_error

echo.
echo [2/4] Installing / updating required packages...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install --upgrade pyinstaller librosa soundfile numpy scipy numba llvmlite audioread pooch soxr
if errorlevel 1 goto :error

echo.
echo [3/4] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist TangoMusicScoreGenerator.spec.bak del /q TangoMusicScoreGenerator.spec.bak

echo.
echo [4/4] Building EXE with explicit librosa dependency collection...
python -m PyInstaller --noconfirm --clean TangoMusicScoreGenerator.spec
if errorlevel 1 goto :error

echo.
echo =====================================================
echo BUILD COMPLETE
 echo.
echo EXE:
echo %~dp0dist\TangoMusicScoreGenerator.exe
echo =====================================================
pause
exit /b 0

:python_error
echo.
echo Python was not found. Install Python 3.10-3.13 and try again.
pause
exit /b 1

:error
echo.
echo BUILD FAILED.
echo Check the error message above.
pause
exit /b 1
