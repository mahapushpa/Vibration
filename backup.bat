@echo off
setlocal EnableDelayedExpansion
REM ============================================================================
REM  BACKUP.BAT — Universal Clean + Timestamped Backup Creator for Python Projects
REM ============================================================================
REM
REM  [WHAT THIS DOES]
REM   - Cleans up Python temp files and folders
REM   - Creates a .RAR archive with proper timestamp and folder structure
REM   - Supports selective folder inclusion
REM   - Automatically saves to a backup folder (protected from overwrite)
REM   - Designed to be reused across projects with minimal changes
REM
REM  [USAGE]
REM   - Double-click or run from command line
REM   - Ensure WinRAR is installed and WINRAR_EXE is correctly set
REM   - Adjust INCLUDE_ONLY to match folder names in your project
REM
REM  [CUSTOMIZABLE SETTINGS]
REM   SET "BAK_FOLDER=."                 => Project root to scan
REM   SET "WINRAR_EXE=..."               => Path to WinRAR's rar.exe
REM   SET "BACKUP_DEST=..\backup"        => Final backup folder, one folder up
REM   SET "BACKUP_PREFIX=Software"       => Filename prefix
REM   SET "INCLUDE_ONLY=common,gui"      => Comma-separated folders to include
REM   SET "EXCLUDE_ONLY=common,gui"      => Comma-separated folders to exclude
REM   SET "INCLUDE_FILES=common,gui"     => Comma-separated files to include
REM   SET "EXCLUDE_FILES=common,gui"     => Comma-separated files to exclude
REM
REM  [OUTPUT FORMAT]
REM   - Backup file: Software_YYMMDD_AMHHMM.rar
REM     e.g., Software_250909_PM1212.rar
REM   - Archive will preserve full folder structure
REM   - Archive created silently, beep on success
REM
REM ============================================================================

REM === USER SETTINGS ==========================================================
SET "BAK_FOLDER=."
SET "WINRAR_EXE=C:\Program Files (x86)\WinRAR\rar.exe"
SET "BACKUP_DEST=..\backup"
SET "BACKUP_PREFIX=Software"
SET "PRJ_NAME=VibrationTableRevA"

REM Comma-separated folders, files, wjen ^ used, remove quotes, no indent allowed
SET "INCLUDE_ONLY=common,productiontool,vibmscope"
SET EXCLUDE_ONLY=common/others, common/tools,^
productiontool/config,productiontool/data,productiontool/logs,^
vibmscope/config,vibmscope/data,vibmscope/logs

REM SET "INCLUDE_FILES=common/tools/backup.bat"
REM SET "EXCLUDE_FILES=common/core/maps_logo.ico"

REM === CLEAN TEMP FILES =======================================================
echo [INFO] Cleaning up temp files and folders...
for /d /r "%BAK_FOLDER%" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)

SET "CLEAN_EXT=pyo pyc log bak tmp"
for %%E in (%CLEAN_EXT%) do (
    echo [CLEAN] Deleting *.%%E under "%BAK_FOLDER%" ...
    attrib -r -h -s "%BAK_FOLDER%\*.%%E" /s /d >nul 2>&1
    del /s /f /q "%BAK_FOLDER%\*.%%E" >nul 2>&1
)

REM === CREATE TIMESTAMP =======================================================
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
SET "BACKUP_NAME=%BACKUP_PREFIX%_%PRJ_NAME%_%TIMESTAMP%.rar"

REM === PREP INCLUDE LIST ======================================================
SET "INCLUDE_LIST_FILE=_include_list.txt"
IF EXIST "%INCLUDE_LIST_FILE%" DEL "%INCLUDE_LIST_FILE%" >nul

echo [INFO] Preparing list of folders to include...
SETLOCAL EnableDelayedExpansion
SET "LIST=%INCLUDE_ONLY%"
:parse_loop
FOR /F "tokens=1* delims=," %%a IN ("!LIST!") DO (
    IF EXIST "%BAK_FOLDER%\%%a" (
        echo Including folder: %%a
        echo %BAK_FOLDER%\%%a\>>"%INCLUDE_LIST_FILE%"
    ) ELSE (
        echo [WARN] Skipping missing folder: %%a
    )
    SET "LIST=%%b"
    IF DEFINED LIST GOTO parse_loop
)
ENDLOCAL

REM echo === INCLUDE LIST ===
REM type "%INCLUDE_LIST_FILE%"
REM echo ====================

REM === PROTECT EXISTING BACKUP ================================================
IF NOT EXIST "%BACKUP_DEST%" mkdir "%BACKUP_DEST%"
IF EXIST "%BACKUP_DEST%\%BACKUP_NAME%" (
    echo [WARN] Backup %BACKUP_NAME% already exists. Aborting.
    EXIT /B 1
)

REM === CREATE BACKUP USING WINRAR =============================================
echo [INFO] Creating archive: %BACKUP_NAME%
"%WINRAR_EXE%" a -r -ibck -idq "%BACKUP_NAME%" @"%INCLUDE_LIST_FILE%"

REM === REMOVE EXCLUDED PATHS FROM ARCHIVE =====================================
IF DEFINED EXCLUDE_ONLY (
    SETLOCAL EnableDelayedExpansion
    echo [INFO] Removing excluded folders from archive...
    FOR %%e IN (%EXCLUDE_ONLY%) DO (
        SET "exclude_win=%%e"
        SET "exclude_win=!exclude_win:/=\!"
        echo    - Deleting contents: !exclude_win!\*
        "%WINRAR_EXE%" d -df -idq "%BACKUP_NAME%" *!exclude_win!\*
        echo    - Deleting folder itself: !exclude_win!\
        "%WINRAR_EXE%" d -idq "%BACKUP_NAME%" !exclude_win!        
    )
    ENDLOCAL
)

REM === REMOVE EXCLUDED FILES ==================================================
IF DEFINED EXCLUDE_FILES (
    echo [INFO] Removing excluded files from archive...
    SETLOCAL EnableDelayedExpansion
    FOR %%f IN (%EXCLUDE_FILES%) DO (
        SET "exclude_file=%%f"
        SET "exclude_file=!exclude_file:/=\!"
        echo    - Excluding file: !exclude_file!
        "%WINRAR_EXE%" d -df "%BACKUP_NAME%" !exclude_file!
    )
    ENDLOCAL
)

REM === FORCE-ADD SPECIFIC FILES (even if their folders weren't included) =====
IF DEFINED INCLUDE_FILES (
    echo [INFO] Adding specific files into archive...
    SETLOCAL EnableDelayedExpansion
    FOR %%f IN (%INCLUDE_FILES%) DO (
        SET "inc_file=%%f"
        REM Normalize to Windows separators
        SET "inc_file=!inc_file:/=\!"
        IF EXIST "%BAK_FOLDER%\!inc_file!" (
            echo    - Including file: !inc_file!
            "%WINRAR_EXE%" a -idq "%BACKUP_NAME%" "%BAK_FOLDER%\!inc_file!"
        ) ELSE (
            echo [WARN] Missing include file: !inc_file!
        )
    )
    ENDLOCAL
)

REM === COPY TO FINAL DESTINATION ==============================================
MOVE /Y "%BACKUP_NAME%" "%BACKUP_DEST%" >nul
DEL "%INCLUDE_LIST_FILE%" 2>nul

echo [SUCCESS] Backup created: %BACKUP_DEST%\%BACKUP_NAME%"

REM === BEEP ON COMPLETION =====================================================
powershell -c "[console]::beep(2000,50)"

EXIT /B 0
REM ============================================================================
