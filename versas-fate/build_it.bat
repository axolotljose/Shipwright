@echo off
setlocal enabledelayedexpansion
REM ===================================================================
REM  build_it.bat - builds Ship of Harkinian with the Versa's Fate mod
REM
REM  Just double-click this file. It will:
REM    1. check the dependencies are present
REM    2. make sure the mod's patch is applied (it already is)
REM    3. configure + compile Release
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
    echo  ERROR: no "soh" folder next to this script.
    echo         Unzip the whole download and run build_it.bat from inside it.
    pause
    exit /b 1
)

REM ---- 1. are the two dependency folders present? --------------------
REM  GitHub's "Download ZIP" never includes folders that are links to
REM  other repositories, which leaves libultraship\ and torch\ empty and
REM  makes the build impossible. This catches that case early.
if not exist "%ROOT%\libultraship\CMakeLists.txt" goto :missing_deps
if not exist "%ROOT%\torch\CMakeLists.txt" goto :missing_deps
echo  Dependencies: libultraship + torch found

REM ---- 2. is the mod's patch applied? --------------------------------
if exist "%ROOT%\soh\soh\VersasFateWarp.cpp" (
    echo  Patch: already applied
    goto :find_build
)
echo  Patch: not applied - applying it now...
if not exist "%ROOT%\versas-fate\tools\apply_patch.py" (
    echo.
    echo  ERROR: the patch and its installer are both missing.
    echo         Re-download the project and try again.
    pause
    exit /b 1
)
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: python was not found. Install Python 3 from python.org
    echo         ^(tick "Add python.exe to PATH"^) and run this again.
    pause
    exit /b 1
)
python "%ROOT%\versas-fate\tools\apply_patch.py" --soh-src "%ROOT%"
if errorlevel 1 (
    echo.
    echo  ERROR: applying the patch failed - see the message above.
    pause
    exit /b 1
)

:find_build
REM ---- 3. pick a build folder ----------------------------------------
REM  Only folders that already contain generated project files are
REM  trusted. A folder left behind by an earlier failed attempt has a
REM  CMakeCache.txt but no ALL_BUILD.vcxproj, and building in it gives
REM  "error MSB1009: project file does not exist".
set "BUILD="
if not "%~1"=="" set "BUILD=%~1"

if not defined BUILD if exist "%ROOT%\build\ALL_BUILD.vcxproj" set "BUILD=%ROOT%\build"
if not defined BUILD if exist "%ROOT%\out\build\ALL_BUILD.vcxproj" set "BUILD=%ROOT%\out\build"
if not defined BUILD (
    for /d %%D in ("%ROOT%\*") do (
        if not defined BUILD if exist "%%D\ALL_BUILD.vcxproj" set "BUILD=%%D"
    )
)
if not defined BUILD set "BUILD=%ROOT%\build"

where cmake >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: cmake was not found on your PATH.
    echo         Easiest fix: open "Developer Command Prompt for VS 2022"
    echo         from the Start menu, then drag this file into that window
    echo         and press Enter.
    pause
    exit /b 1
)

echo  Build folder: %BUILD%
echo.
echo  Configuring - this is a one-time step, a few minutes...
echo.
if exist "%BUILD%\CMakeCache.txt" (
    cmake -S "%ROOT%" -B "%BUILD%"
) else (
    cmake -S "%ROOT%" -B "%BUILD%" -G "Visual Studio 17 2022" -A x64
)
if errorlevel 1 (
    echo.
    echo  That build folder is unusable - configuring a fresh one instead.
    echo.
    set "BUILD=%ROOT%\build-versasfate"
    cmake -S "%ROOT%" -B "%BUILD%" -G "Visual Studio 17 2022" -A x64
    if errorlevel 1 (
        echo.
        echo  Configure failed (see above). Most common causes:
        echo    - Visual Studio 2022 with "Desktop development with C++"
        echo      is not installed
        echo    - the libultraship or torch folder is empty
        pause
        exit /b 1
    )
)

echo.
echo  Compiling Release - the first build takes 10-30 minutes...
echo.
cmake --build "%BUILD%" --config Release
if errorlevel 1 (
    echo.
    echo  BUILD FAILED. The compiler output above says why.
    echo  Nothing was installed and your game was not touched.
    pause
    exit /b 1
)

REM ---- 4. find the exe we just built ---------------------------------
set "EXE="
if exist "%BUILD%\soh\Release\soh.exe" set "EXE=%BUILD%\soh\Release\soh.exe"
if not defined EXE if exist "%BUILD%\Release\soh.exe" set "EXE=%BUILD%\Release\soh.exe"
if not defined EXE (
    for /f "delims=" %%F in ('dir /s /b "%BUILD%\soh.exe" 2^>nul') do set "EXE=%%F"
)
if not defined EXE (
    echo.
    echo  The build succeeded but soh.exe was not found under:
    echo    %BUILD%
    echo  Look for it there and run it; then copy
    echo  versas-fate\VersasFate.o2r into a "mods" folder next to it.
    pause
    exit /b 1
)

for %%A in ("%EXE%") do set "EXEDIR=%%~dpA"
echo.
echo  Built:        %EXE%

REM ---- 5. install the mod next to the game ---------------------------
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
echo   With the ocarina out, play:
echo     A, C-Up, C-Down, C-Left, C-Right, A
echo   keyboard defaults:  X, Up, Down, Left, Right, X
echo.
echo   Saria (or any Kokiri in Kokiri Forest) also sings it for you
echo   the first time you talk to them with the ocarina.
echo  ===================================================================
echo.
pause
exit /b 0

:missing_deps
echo.
echo  ===================================================================
echo   PROBLEM: libultraship\ or torch\ is empty.
echo.
echo   These two folders are links to other projects, and GitHub's
echo   "Download ZIP" does NOT include them. Without them the game
echo   cannot be built at all.
echo.
echo   Fix: download the complete package instead, which has them
echo   inside, then double-click build_it.bat in that one:
echo.
echo   https://github.com/axolotljose/Shipwright/releases/download/versas-fate-build/Shipwright-VersasFate-with-dependencies.zip
echo.
echo   (If you have git installed, cloning with
echo    "git clone --recurse-submodules" also fixes it.)
echo  ===================================================================
echo.
pause
exit /b 1
