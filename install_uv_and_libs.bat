@echo off
setlocal EnableExtensions

cd /d "%~dp0"

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

echo [2/3] Preparing libs folder...
if not exist "libs" mkdir "libs"

echo [3/3] Installing dependencies into libs...
uv pip install --target .\libs --upgrade ^
  numpy scipy matplotlib openimageio opencv-python pyside6
if errorlevel 1 (
    echo Dependency installation failed.
    exit /b 1
)

echo.
echo Done. Dependencies were installed into .\libs
exit /b 0
