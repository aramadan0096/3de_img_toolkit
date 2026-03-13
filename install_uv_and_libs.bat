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

if "%PY_SPEC_NORM%"=="3.7" if "%PY_EXE%"=="" (
    call :FindPy37Interpreter
    if not "!PY37_FOUND!"=="" (
        set "PYTHON_SELECTOR=!PY37_FOUND!"
        echo Auto-detected Python 3.7 interpreter: !PYTHON_SELECTOR!
    )
)

echo [1/4] Checking uv...
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

echo [2/4] Rebuilding .venv for Python %PY_SPEC_NORM%...
if exist ".venv" (
    rmdir /s /q ".venv"
    if exist ".venv" (
        echo Failed to remove existing .venv.
        echo Close shells/tools using .venv and run again.
        exit /b 1
    )
)

uv venv --python "%PYTHON_SELECTOR%" .venv
if errorlevel 1 (
    echo Failed to create .venv with Python %PY_SPEC_NORM%.
    if "%PY_SPEC_NORM%"=="3.7" if "%PY_EXE%"=="" (
        echo Python 3.7 was not auto-detected.
        echo Pass explicit interpreter path, for example:
        echo   install_uv_and_libs.bat 3.7 "C:\Users\%USERNAME%\Downloads\3DEqualizer4\sys_data\py37_inst\python.exe"
    )
    if not "%PY_EXE%"=="" echo Python executable was: %PY_EXE%
    exit /b 1
)

set "PYTHON_SELECTOR=.venv\Scripts\python.exe"

echo [3/4] Preparing %TARGET_DIR% folder for Python %PY_SPEC_NORM%...
if not exist "libs" mkdir "libs"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

echo [4/4] Installing dependencies into %TARGET_DIR%...
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

if "%MAJOR%" NEQ "3" (
    echo Unsupported Python major version: %MAJOR%
    echo Use Python 3.x values like 3.7 or 3.11.
    exit /b 1
)

if "%MINOR%"=="" (
    echo Invalid Python version format: %RAW%
    echo Use values like 3.7, 3.11, 37, or 311.
    exit /b 1
)

if not "%MINOR%"=="7" if not "%MINOR%"=="8" if not "%MINOR%"=="9" if not "%MINOR%"=="10" if not "%MINOR%"=="11" if not "%MINOR%"=="12" if not "%MINOR%"=="13" (
    echo Unsupported Python minor version: %MINOR%
    echo Use supported versions: 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13.
    exit /b 1
)

set "PY_TAG=py%MAJOR%%MINOR%"
exit /b 0

:FindPy37Interpreter
set "PY37_FOUND="

if exist "%USERPROFILE%\Downloads\3DEqualizer4\sys_data\py37_inst\python.exe" (
    set "PY37_FOUND=%USERPROFILE%\Downloads\3DEqualizer4\sys_data\py37_inst\python.exe"
    exit /b 0
)

for /f "delims=" %%P in ('where py 2^>nul') do (
    set "PY_LAUNCHER=%%P"
    goto :TryPyLauncher37
)
goto :EndFindPy37

:TryPyLauncher37
for /f "delims=" %%E in ('"%PY_LAUNCHER%" -3.7 -c "import sys; print(sys.executable)" 2^>nul') do (
    if exist "%%E" set "PY37_FOUND=%%E"
)

:EndFindPy37
exit /b 0
