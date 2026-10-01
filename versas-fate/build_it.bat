@echo off
setlocal enabledelayedexpansion
REM ===================================================================
REM  build_it.bat - builds Ship of Harkinian with the Versa's Fate patch
REM
REM  Just double-click this file. It will:
REM    1. make sure the patch is applied (it already is on this branch)
REM    2. find your build folder, or configure one with Visual Studio 2022
REM    3. compile Release
REM    4. copy VersasFate.o2r into the "mods" folder next to soh.exe
REM
REM  Optional:  build_it.bat "C:\path\to\your\build\folder"
REM ===================================================================

cd /d "%~dp0.."
set "ROOT=%CD%"
echo.
echo  Ship of Harkinian root: %ROOT%
if not exist "%ROOT%\soh" (
    echo.
    echo  ERROR: this script lives inside the Ship of Harkinian repo, but no
    echo         "soh" folder was found next to it. Unzip the branch so that
    echo         versas-fate\ sits next to soh\, then run it again.
    pause
    exit /b 1
)

REM ---- 1. make sure the patch is in the source -----------------------
if exist "%ROOT%\soh\soh\VersasFateWarp.cpp" (
    echo  Patch: already applied (soh\soh\VersasFateWarp.cpp present)
    goto :find_build
)
echo  Patch: not applied - applying it now...
set "PATCHER=%ROOT%\versas-fate\tools\apply_patch.py"
if not exist "%PATCHER%" (
    echo.
    echo  ERROR: the patch is missing and versas-fate\tools\apply_patch.py was
    echo         not found. Check out the complete branch and try again.
    pause
    exit /b 1
)
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: python was not found on your PATH. Install Python 3 from
    echo         python.org ^(tick "Add python.exe to PATH"^) and run this again.
    pause
    exit /b 1
)
python "%PATCHER%" --soh-src "%ROOT%"
if errorlevel 1 (
    echo.
    echo  ERROR: applying the patch failed. See the message above.
    pause
    exit /b 1
)

:find_build
REM ---- 2. find or create a build folder ------------------------------
set "BUILD="
if not "%~1"=="" if exist "%~1\CMakeCache.txt" set "BUILD=%~1"
if not defined BUILD if exist "%ROOT%\build\CMakeCache.txt" set "BUILD=%ROOT%\build"
if not defined BUILD if exist "%ROOT%\out\build\CMakeCache.txt" set "BUILD=%ROOT%\out\build"
if not defined BUILD (
    for /d %%D in ("%ROOT%\*") do (
        if not defined BUILD if exist "%%D\CMakeCache.txt" set "BUILD=%%D"
    )
)
if not defined BUILD (
    for /d %%D in ("%ROOT%\out\build\*") do (
        if not defined BUILD if exist "%%D\CMakeCache.txt" set "BUILD=%%D"
    )
)

where cmake >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: cmake was not found on your PATH. Easiest fix: open the
    echo         "Developer Command Prompt for VS 2022" from the Start menu and
    echo         run:   "%ROOT%\versas-fate\build_it.bat"
    pause
    exit /b 1
)

if not defined BUILD (
    echo.
    echo  No configured build folder found - configuring one with Visual
    echo  Studio 2022 now. This is a one-time step and takes a few minutes.
    echo.
    cmake -S "%ROOT%" -B "%ROOT%\build" -G "Visual Studio 17 2022" -A x64
    if errorlevel 1 (
        echo.
        echo  Configure failed ^(see above^). If you already have a build
        echo  folder under another name, pass it in:
        echo      build_it.bat "D:\path\to\build"
        pause
        exit /b 1
    )
    set "BUILD=%ROOT%\build"
)

echo  Build folder: %BUILD%
echo.
echo  Compiling Release - the first build can take 10-30 minutes...
echo.
cmake --build "%BUILD%" --config Release
if errorlevel 1 (
    echo.
    echo  BUILD FAILED. The compiler output above says why. Nothing was
    echo  installed and the game was not touched.
    pause
    exit /b 1
)

REM ---- 3. locate the exe we just built -------------------------------
set "EXE="
if exist "%BUILD%\soh\Release\soh.exe" set "EXE=%BUILD%\soh\Release\soh.exe"
if not defined EXE if exist "%BUILD%\Release\soh.exe" set "EXE=%BUILD%\Release\soh.exe"
if not defined EXE (
    for /f "delims=" %%F in ('dir /s /b "%BUILD%\soh.exe" 2^>nul') do set "EXE=%%F"
)
if not defined EXE (
    echo.
    echo  The build succeeded but no soh.exe was found under %BUILD%.
    echo  Run the game from wherever it landed; then copy
    echo  versas-fate\VersasFate.o2r into a "mods" folder next to it.
    pause
    exit /b 1
)

for %%A in ("%EXE%") do set "EXEDIR=%%~dpA"
echo.
echo  Built:        %EXE%

REM ---- 4. install the mod where the game will read it ----------------
set "MODSRC=%ROOT%\versas-fate\VersasFate.o2r"
if not exist "%MODSRC%" (
    echo  NOTE: %MODSRC% is missing, so the mod was NOT installed.
    pause
    exit /b 1
)

if not exist "%EXEDIR%mods" mkdir "%EXEDIR%mods"
copy /y "%MODSRC%" "%EXEDIR%mods\VersasFate.o2r" >nul
echo  Mod installed: %EXEDIR%mods\VersasFate.o2r

if not exist "%EXEDIR%oot.o2r" (
    for /f "delims=" %%F in ('dir /s /b "%ROOT%\oot.o2r" 2^>nul') do (
        if not exist "%%~dpFmods" mkdir "%%~dpFmods"
        copy /y "%MODSRC%" "%%~dpFmods\VersasFate.o2r" >nul
        echo  Mod also installed next to: %%F
    )
)

echo.
echo  ===================================================================
echo   DONE. Start the game:
echo     "%EXE%"
echo.
echo   Then, with the ocarina out, play:
echo     A, C-Up, C-Down, C-Left, C-Right, A
echo   keyboard defaults:  X, Up, Down, Left, Right, X
echo  ===================================================================
echo.
pause
