@echo off
setlocal EnableExtensions
setlocal EnableDelayedExpansion

cd /d "%~dp0"

set "PY_SPEC=%~1"
set "PY_EXE=%~2"

if "%PY_SPEC%"=="" (
    echo Enter Python version to build local libs for ^(examples: 3.7, 3.11^).
    set /p "PY_SPEC=Python version [3.11]: "
    if "!PY_SPEC!"=="" set "PY_SPEC=3.11"
)

call :NormalizePySpec "%PY_SPEC%"
if errorlevel 1 exit /b 1

set "PYTHON_SELECTOR=%PY_SPEC_NORM%"
if not "%PY_EXE%"=="" set "PYTHON_SELECTOR=%PY_EXE%"

set "TARGET_DIR=libs\%PY_TAG%"
echo Selected Python version: %PY_SPEC_NORM% ^(%PY_TAG%^)

echo [1/3] Checking uv...
where uv >nul 2>nul
if errorlevel 1 (
    echo uv is not installed. Installing with PowerShell...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo Failed to install uv.
        exit /b 1
    )

    set "UV_BIN=%USERPROFILE%\.local\bin"
    if exist "%UV_BIN%\uv.exe" set "PATH=%UV_BIN%;%PATH%"
)

echo [2/3] Preparing %TARGET_DIR% folder for Python %PY_SPEC_NORM%...
if not exist "libs" mkdir "libs"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

echo [3/3] Installing dependencies into %TARGET_DIR%...
if "%PY_SPEC_NORM%"=="3.7" (
    uv pip install --python "%PYTHON_SELECTOR%" --target .\%TARGET_DIR% --upgrade ^
        "numpy<1.22" "scipy<1.8" "matplotlib<3.6" "opencv-python<4.8" "pillow<10" "pyside6<6.5"
    if errorlevel 1 (
        echo Core dependency installation failed for Python %PY_SPEC_NORM%.
        if not "%PY_EXE%"=="" echo Python executable was: %PY_EXE%
        echo Make sure Python %PY_SPEC_NORM% is installed and available to uv.
        echo You can also pass an explicit interpreter path as 2nd argument.
        exit /b 1
    )

    uv pip install --python "%PYTHON_SELECTOR%" --target .\%TARGET_DIR% --upgrade openimageio
    if errorlevel 1 (
        echo Warning: openimageio could not be installed for Python %PY_SPEC_NORM%.
        echo Trying OpenEXR fallback for EXR support...
        uv pip install --python "%PYTHON_SELECTOR%" --target .\%TARGET_DIR% --upgrade "OpenEXR<3" "Imath<1"
        if errorlevel 1 (
            echo Warning: OpenEXR fallback installation also failed.
            echo EXR read/write may be unavailable; PNG/JPG workflow can still work.
        ) else (
            echo OpenEXR fallback installed successfully.
        )
    )
) else (
    uv pip install --python "%PYTHON_SELECTOR%" --target .\%TARGET_DIR% --upgrade ^
        numpy scipy matplotlib openimageio opencv-python pyside6 pillow
    if errorlevel 1 (
        echo Dependency installation failed for Python %PY_SPEC%.
        exit /b 1
    )
)

echo.
echo Done. Dependencies were installed into .\%TARGET_DIR%
exit /b 0

:NormalizePySpec
set "RAW=%~1"
set "RAW=%RAW: =%"

if "%RAW%"=="" (
    echo Invalid Python version.
    exit /b 1
)

for /f "tokens=1,2 delims=." %%A in ("%RAW%") do (
    set "MAJOR=%%A"
    set "MINOR=%%B"
)

if "%MINOR%"=="" (
    set "MAJOR="
    set "MINOR="
    if "%RAW%"=="37" (
        set "MAJOR=3"
        set "MINOR=7"
    )
    if "%RAW%"=="38" (
        set "MAJOR=3"
        set "MINOR=8"
    )
    if "%RAW%"=="39" (
        set "MAJOR=3"
        set "MINOR=9"
    )
    if "%RAW%"=="310" (
        set "MAJOR=3"
        set "MINOR=10"
    )
    if "%RAW%"=="311" (
        set "MAJOR=3"
        set "MINOR=11"
    )
    if "%RAW%"=="312" (
        set "MAJOR=3"
        set "MINOR=12"
    )
    if "%RAW%"=="313" (
        set "MAJOR=3"
        set "MINOR=13"
    )

    if "%MAJOR%"=="" (
        echo Invalid Python version format: %RAW%
        echo Use values like 3.7, 3.11, 37, or 311.
        exit /b 1
    )
)

set "PY_SPEC_NORM=%MAJOR%.%MINOR%"
set "PY_TAG=py%MAJOR%%MINOR%"
exit /b 0
