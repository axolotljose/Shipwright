@echo off
setlocal enabledelayedexpansion
REM ===================================================================
REM  build_it.bat - builds Ship of Harkinian with the Versa's Fate mod
REM
REM  Just double-click this file. It will:
REM    1. check the dependencies are present
REM    2. make sure the mod's patch is applied (it already is)
REM    3. find Visual Studio and its C++ tools
REM    4. configure + compile Release
REM    5. copy VersasFate.o2r into the "mods" folder next to soh.exe
REM
REM  Every message is also written to build_it.log next to this file.
REM  Optional:  build_it.bat "C:\path\to\your\build\folder"
REM ===================================================================

REM ---- 0. never close the window -------------------------------------
REM  Double-clicking a .bat gives a console that disappears the moment the
REM  script ends (or crashes), taking the error message with it. Re-launch
REM  inside "cmd /k" once, so the window always stays open with the full
REM  scrollback.
if /i not "%~1"=="_vf_inner" (
    if not "%~1"=="" set "VF_BUILD_DIR=%~1"
    start "Versa's Fate - build" cmd /k ""%~f0" _vf_inner"
    exit /b
)

cd /d "%~dp0.."
set "ROOT=%CD%"
set "LOG=%ROOT%\build_it.log"
set "ARG1=%VF_BUILD_DIR%"

echo.> "%LOG%"
echo  Ship of Harkinian root: %ROOT%
echo  Ship of Harkinian root: %ROOT% >> "%LOG%"
echo  Log file: %LOG%

if not exist "%ROOT%\soh" (
    echo.
    echo  ERROR: no "soh" folder next to this script.
    echo         Unzip the whole download and run build_it.bat from inside it.
    goto :fail
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
    goto :fail
)
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: python was not found. Install Python 3 from python.org
    echo         ^(tick "Add python.exe to PATH"^) and run this again.
    goto :fail
)
python "%ROOT%\versas-fate\tools\apply_patch.py" --soh-src "%ROOT%"
if errorlevel 1 (
    echo.
    echo  ERROR: applying the patch failed - see the message above.
    goto :fail
)

:find_build
REM ---- 3. pick a build folder ----------------------------------------
REM  Only folders that already contain generated project files are
REM  trusted. A folder left behind by an earlier failed attempt has a
REM  CMakeCache.txt but no ALL_BUILD.vcxproj, and building in it gives
REM  "error MSB1009: project file does not exist".
set "BUILD="
if not "%ARG1%"=="" set "BUILD=%ARG1%"

if not defined BUILD if exist "%ROOT%\build\ALL_BUILD.vcxproj" set "BUILD=%ROOT%\build"
if not defined BUILD if exist "%ROOT%\out\build\ALL_BUILD.vcxproj" set "BUILD=%ROOT%\out\build"
if not defined BUILD (
    for /d %%D in ("%ROOT%\*") do (
        if not defined BUILD if exist "%%D\ALL_BUILD.vcxproj" set "BUILD=%%D"
    )
)
if not defined BUILD set "BUILD=%ROOT%\build-versasfate"
echo  Build folder: %BUILD%

REM ---- 4. find Visual Studio, CMake and the C++ tools ---------------
REM  "The C compiler identification is unknown" is what CMake says when
REM  it cannot run a C compiler at all - on Windows that almost always
REM  means Visual Studio is missing, or was installed without the
REM  "Desktop development with C++" workload. Find out which, and say so,
REM  instead of letting CMake fail with a message nobody can act on.
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "VSPATH="
set "VSANY="
set "VSVER="
if exist "%VSWHERE%" (
    for /f "usebackq tokens=*" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2^>nul`) do set "VSPATH=%%I"
    for /f "usebackq tokens=*" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationVersion 2^>nul`) do set "VSVER=%%I"
    if not defined VSPATH (
        for /f "usebackq tokens=*" %%I in (`"%VSWHERE%" -latest -products * -property installationPath 2^>nul`) do set "VSANY=%%I"
    )
) else (
    echo  vswhere.exe not found - no Visual Studio installer on this PC.
)

if not defined VSPATH goto :no_compiler

echo  Visual Studio: %VSPATH%
echo  VS version:    %VSVER%
echo  Visual Studio: %VSPATH% (%VSVER%) >> "%LOG%"

set "GENERATOR=Visual Studio 17 2022"
for /f "tokens=1 delims=." %%V in ("%VSVER%") do (
    if "%%V"=="16" set "GENERATOR=Visual Studio 16 2019"
    if "%%V"=="18" set "GENERATOR=Visual Studio 17 2022"
)
echo  Generator:     %GENERATOR%

set "CMAKE="
where cmake >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%C in ('where cmake') do if not defined CMAKE set "CMAKE=%%C"
)
if not defined CMAKE if exist "%VSPATH%\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" (
    set "CMAKE=%VSPATH%\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
)
if not defined CMAKE (
    echo.
    echo  ERROR: cmake was not found, on your PATH or inside Visual Studio.
    echo         Re-run the Visual Studio Installer, click "Modify" and tick
    echo         "Desktop development with C++" ^(it includes CMake^).
    goto :fail
)
echo  CMake:         %CMAKE%
echo  CMake:         %CMAKE% >> "%LOG%"

REM  Put the MSVC toolchain on PATH for this window. The Visual Studio
REM  generator does not need it, but it makes any other generator work.
call "%VSPATH%\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1

REM ---- 5. configure ---------------------------------------------------
if exist "%BUILD%\CMakeCache.txt" if not exist "%BUILD%\ALL_BUILD.vcxproj" (
    echo  That folder is left over from a failed attempt - starting it fresh.
    rmdir /s /q "%BUILD%"
    if exist "%BUILD%" (
        echo.
        echo  ERROR: could not delete %BUILD%
        echo         Close any program using it, or delete the folder yourself.
        goto :fail
    )
)

echo.
echo  Configuring - this is a one-time step, a few minutes...
echo.
powershell -NoProfile -Command "& '%CMAKE%' -S '%ROOT%' -B '%BUILD%' -G '%GENERATOR%' -A x64 2>&1 | Tee-Object -FilePath '%LOG%' -Append; exit $LASTEXITCODE"
if errorlevel 1 goto :configure_failed_retry

goto :compile

:configure_failed_retry
echo.
echo  Configure failed in that folder - wiping it and trying once more.
echo.
rmdir /s /q "%BUILD%" 2>nul
powershell -NoProfile -Command "& '%CMAKE%' -S '%ROOT%' -B '%BUILD%' -G '%GENERATOR%' -A x64 2>&1 | Tee-Object -FilePath '%LOG%' -Append; exit $LASTEXITCODE"
if errorlevel 1 goto :configure_failed

:compile
echo.
echo  Compiling Release - the first build takes 10-30 minutes...
echo  (leave this window open; nothing is downloading, it is your CPU)
echo.
powershell -NoProfile -Command "& '%CMAKE%' --build '%BUILD%' --config Release --parallel 2>&1 | Tee-Object -FilePath '%LOG%' -Append; exit $LASTEXITCODE"
if errorlevel 1 (
    echo.
    echo  BUILD FAILED. The compiler errors are above, and in
    echo    %LOG%
    echo  Nothing was installed and your game was not touched.
    goto :fail
)

REM ---- 6. find the exe we just built ---------------------------------
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
    goto :fail
)

for %%A in ("%EXE%") do set "EXEDIR=%%~dpA"
echo.
echo  Built:        %EXE%

REM ---- 7. install the mod next to the game ---------------------------
set "MODSRC=%ROOT%\versas-fate\VersasFate.o2r"
if not exist "%MODSRC%" (
    echo  NOTE: %MODSRC% is missing, so the mod was NOT installed.
    goto :fail
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

REM ===================================================================
REM  failure paths
REM ===================================================================
:configure_failed
echo.
echo  ===================================================================
echo   CONFIGURE FAILED
echo.
echo   CMake could not set up a build with %GENERATOR%.
echo   What the messages above usually mean:
echo.
echo    "The C compiler identification is unknown"
echo       the C++ tools are missing or CMake cannot start them. Open the
echo       Visual Studio Installer, click Modify, and tick the workload
echo       "Desktop development with C++", then run this again.
echo.
echo    a message about libultraship or torch
echo       those folders are empty - use the download with dependencies.
echo.
echo   The full output is saved in:
echo     %LOG%
echo  ===================================================================
goto :fail

:no_compiler
echo.
echo  ===================================================================
echo   NO C COMPILER FOUND
echo.
if defined VSANY (
    echo   Visual Studio is installed here:
    echo     %VSANY%
    echo   ...but WITHOUT the C++ tools, which is exactly why CMake says
    echo   "The C compiler identification is unknown".
    echo.
    echo   Fix ^(one time, about 10 minutes of downloading^):
    echo     1. open the "Visual Studio Installer" from the Start menu
    echo     2. click Modify on that installation
    echo     3. tick the box "Desktop development with C++"
    echo     4. click Modify / Install and let it finish
    echo     5. run build_it.bat again
) else (
    echo   This PC has no Visual Studio with C++ tools at all, and the game
    echo   cannot be compiled without them.
    echo.
    echo   Fix ^(one time^): install the free Build Tools and tick the
    echo   "Desktop development with C++" workload:
    echo.
    echo     https://aka.ms/vs/17/release/vs_BuildTools.exe
    echo.
    echo   ^(Visual Studio Community from visualstudio.microsoft.com works
    echo    too, as long as "Desktop development with C++" is ticked.^)
    echo.
    echo   Then run build_it.bat again.
)
echo.
echo   TIP: you can also let GitHub build it for you instead - see the
echo   "Windows: the one download that actually builds" section in
echo   versas-fate\README.md.
echo  ===================================================================
goto :fail

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
echo   https://github.com/axolotljose/Shipwright/raw/arena/01a0f751-shipwright/versas-fate/download/Shipwright-VersasFate-with-dependencies.zip
echo.
echo   (If you have git installed, cloning with
echo    "git clone --recurse-submodules" also fixes it.)
echo  ===================================================================
goto :fail

:fail
echo.
echo  -------------------------------------------------------------------
echo   Stopped. Nothing was installed and your game was not touched.
echo   Full log: %LOG%
echo  -------------------------------------------------------------------
echo.
pause
exit /b 1
