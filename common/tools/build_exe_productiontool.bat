@echo off
REM ====================================================
REM      PyInstaller Batch Build Script Template
REM ====================================================
REM - Builds a Python EXE using PyInstaller and PyArmor
REM - Place this batch file inside:  project_root\<YourProject>\
REM - Output will go to:             project_root\distribution\<EXE_FOLDER>
REM ====================================================

SETLOCAL ENABLEEXTENSIONS

REM -------- USER INPUTS: MODIFY ONLY THESE 3 LINES --------
REM -------- Version suffix
SET PRJ_VER=V1
REM -------- Main Name prefix
SET PRJ_FOLDER=ProductionTool

REM -------- Distrubtion Folder, where exe is created
SET PRJ_OUT=distribution

REM -------- DERIVED NAMES: NO NEED TO EDIT --------
SET PRJ_NAME=%PRJ_FOLDER%%PRJ_VER%
SET MAIN_FILE=%PRJ_NAME%.py
SET EXE_NAME=%PRJ_NAME%

REM -------- PATH SETUP --------
SET PRJ_ROOT=..
SET PRJ_DIR=%PRJ_ROOT%\%PRJ_FOLDER%
SET ICON_FILE=%PRJ_DIR%\%PRJ_NAME%.ico
SET DIST_ROOT=%PRJ_ROOT%\%PRJ_OUT%
SET DIST_DIR=%DIST_ROOT%\%EXE_NAME%

REM -------- MODULE PATHS (ADJUST ONLY IF STRUCTURE CHANGES)(space-separated) --------
SET LOCAL_MODULES=%PRJ_ROOT%\common\core %PRJ_ROOT%\common\modules %PRJ_ROOT%\common\utils
SET PROJECT_FILES=%PRJ_ROOT%\%PRJ_FOLDER%

REM ====================================================
REM           START: HEADER SUMMARY FOR USER
REM ====================================================
echo.
echo [BUILD SCRIPT INFO]
echo -----------------------------
echo Project Name     : %PRJ_NAME%
echo Project Folder   : %PRJ_DIR%
echo Output EXE Name  : %EXE_NAME%.exe
echo Output Folder    : %DIST_DIR%
echo Main Script      : %MAIN_FILE%
echo -----------------------------
echo.

REM ====================================================
REM           CLEANUP PREVIOUS BUILD FILES
REM ====================================================
echo [INFO] Cleaning previous build artifacts...
IF EXIST "hidden_imports.txt" del /q "hidden_imports.txt"
IF EXIST "%EXE_NAME%.spec" del /q "%EXE_NAME%.spec"
IF EXIST %DIST_DIR%%PRJ_NAME% rmdir /s /q %DIST_DIR%%PRJ_NAME%
IF EXIST "%PRJ_ROOT%\build_temp" rmdir /s /q "%PRJ_ROOT%\build_temp"

REM ====================================================
REM           REMOVE __pycache__ folder from common
REM ====================================================
echo [INFO] Cleaning up __pycache__ folders...
for /d /r "%PRJ_ROOT%\common" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)

REM ====================================================
REM           REMOVE __pycache__ folder from project 
REM ====================================================
echo [INFO] Cleaning up __pycache__ folders...
for /d /r "%PRJ_ROOT%\%PRJ_FOLDER%" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)

REM ====================================================
REM           GENERATE HIDDEN IMPORTS
REM ====================================================
REM Hidden imports not needed now, but kept for future issues
python %PRJ_ROOT%\common\tools\generate_hidden_imports.py --output hidden_imports.txt %LOCAL_MODULES% %PROJECT_FILES%
IF ERRORLEVEL 1 (
    echo [ERROR] Hidden import generation failed. Aborting.
    EXIT /B 1
)
echo [OK] Hidden import generation complete.

REM ====================================================
REM           OBFUSCATE 'common/' USING PYARMOR
REM -O - is capital 'O', small is not acceptable
REM ====================================================
echo [INFO] Obfuscating 'common/' with PyArmor...
rmdir /s /q %PRJ_ROOT%\common_obf >nul 2>&1

:: Only obfuscate needed folders
pyarmor --silent gen %PRJ_ROOT%\common\core -O %PRJ_ROOT%\common_obf\core
pyarmor --silent gen %PRJ_ROOT%\common\utils -O %PRJ_ROOT%\common_obf\utils
pyarmor --silent gen %PRJ_ROOT%\common\modules -O %PRJ_ROOT%\common_obf\modules

IF ERRORLEVEL 1 (
    echo [ERROR] Obfuscation failed.
    EXIT /B 1
)
echo [OK] Obfuscation complete.

REM ====================================================
REM           BUILD EXE WITH PYINSTALLER
REM ====================================================
REM -------- RUN PYINSTALLER --------
REM --noconfirm	Auto-overwrite previous build outputs
REM --clean	Remove temp/cache files before build
REM --onedir	Output in folder (not a single EXE)
REM --windowed	No console window (for GUI apps)
REM --distpath	Where to put the final EXE folder
REM --workpath	Temp folder used during build
REM --add-data A;B	Include A folder in final output as B
REM --hidden-import	Force-includes hidden/dynamic modules
REM "%PROJECT_FILES%\%MAIN_FILE%"	The Python script to convert into an EXE
REM  --add-data "%PRJ_ROOT%\%PRJ_FOLDER%;%PRJ_FOLDER%" ^
REM  --hidden-import hidden_imports.txt ^

echo [INFO] Building EXE: %EXE_NAME%.exe ...

SET QT_API=pyqt5

pyinstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --log-level=WARN ^
  --name %EXE_NAME% ^
  --icon "%ICON_FILE%" ^
  --distpath "%DIST_ROOT%" ^
  --workpath "%PRJ_ROOT%\build_temp" ^
  --add-data "%PRJ_ROOT%\common_obf\core;./common" ^
  --add-data "%PRJ_ROOT%\common_obf\utils;./common" ^
  --add-data "%PRJ_ROOT%\common_obf\modules;./common" ^
  --add-data "%PRJ_ROOT%\common\core\maps_logo.ico;./common/core" ^
  --add-data "%PRJ_ROOT%\%PRJ_FOLDER%\*.py;%PRJ_FOLDER%" ^
  --add-data "%PRJ_ROOT%\%PRJ_FOLDER%\*.ico;%PRJ_FOLDER%" ^
  "%PROJECT_FILES%\%MAIN_FILE%"

IF ERRORLEVEL 1 (
    echo [ERROR] PyInstaller failed.
    EXIT /B 1
)
echo [OK] Build completed: %DIST_DIR%\%EXE_NAME%.exe

REM ====================================================
REM           COPY README FILE TO OUTPUT
REM ====================================================
echo [INFO] Copying readme.txt ...
copy /Y %PRJ_ROOT%\common\tools\readme_client.txt "%DIST_DIR%\readme.txt" >nul 2>&1

REM ====================================================
REM     VERSIONED OUTPUT FOLDER & PORTABLE ZIP (A+B)
REM ====================================================
echo [INFO] Versioning output folder and creating portable ZIP...
REM Below two lines give 24 hrs format
REM for /f %%a in ('wmic os get localdatetime ^| find "."') do set DTS=%%a
REM set "TIMESTAMP=%DTS:~2,6%_%DTS:~8,2%%DTS:~10,2%"

REM Uses system time and date (locale-independent)
for /f %%a in ('wmic os get localdatetime ^| find "."') do set DTS=%%a
SET "yy=%DTS:~2,2%"
SET "mm=%DTS:~4,2%"
SET "dd=%DTS:~6,2%"
SET "hr=%DTS:~8,2%"
SET "min=%DTS:~10,2%"

REM === Convert 24-hour time to 12-hour format with AM/PM ======================
SET "ampm=AM"
CALL SET /A h12=hr

IF %hr% GEQ 12 SET "ampm=PM"
IF %hr% GTR 12 CALL SET /A h12=hr - 12
IF %hr% EQU 0 SET "h12=12"

REM === Pad hour and minute if needed ===
IF %h12% LSS 10 SET "h12=0%h12%"
IF %min% LSS 10 SET "min=0%min%"

REM === Final timestamp for filename ===
SET "TIMESTAMP=%yy%%mm%%dd%_%ampm%%h12%%min%"

set "NEW_DIST_DIR=%DIST_ROOT%\%EXE_NAME%_%TIMESTAMP%"

REM -- Rename dist\<EXE_NAME> -> dist\<EXE_NAME>_<TIMESTAMP>
IF EXIST "%DIST_DIR%" (
  echo [INFO] Renaming "%DIST_DIR%" to "%NEW_DIST_DIR%"
  pushd "%DIST_ROOT%"
  ren "%EXE_NAME%" "%EXE_NAME%_%TIMESTAMP%"
  popd
) ELSE (
  echo [WARN] Dist folder not found: "%DIST_DIR%"
)

REM -- Create portable ZIP alongside the folder
IF EXIST "%NEW_DIST_DIR%" (
  echo [INFO] Creating portable zip: "%NEW_DIST_DIR%.zip"
  powershell -NoLogo -NoProfile -Command "Compress-Archive -Path '%NEW_DIST_DIR%\*' -DestinationPath '%NEW_DIST_DIR%.zip' -Force"
) ELSE (
  echo [WARN] Skipping zip; folder not found: "%NEW_DIST_DIR%"
)

REM ====================================================
REM           CLEANUP TEMP FILES
REM ====================================================
del /q hidden_imports.txt >nul 2>&1
del /q "%EXE_NAME%.spec" >nul 2>&1
IF EXIST "%PRJ_ROOT%\build_temp" rmdir /s /q "%PRJ_ROOT%\build_temp"
IF EXIST "%PRJ_ROOT%\common_obf" rmdir /s /q "%PRJ_ROOT%\common_obf"
IF EXIST "%PRJ_ROOT%\%PRJ_FOLDER%_obf" rmdir /s /q "%PRJ_ROOT%\%PRJ_FOLDER%_obf"

echo [DONE] Build script finished successfully.
ENDLOCAL

