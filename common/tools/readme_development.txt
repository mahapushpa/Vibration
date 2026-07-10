=======================================================
  VibMTool - Developer README for EXE Build and Debug
=======================================================

This README is intended for internal development and maintenance of the EXE build 
process using PyInstaller and optional PyArmor protection.

Contents:
---------
- VibMTool.exe                : The generated executable (test version with console)
- hidden_imports.txt         : Auto-generated list of hidden imports
- build_exe_production.bat   : Build script (copied from ../common/tools/)
- readme_template.txt        : This developer-facing help file

-------------------------------------
  1. EXECUTABLE BEHAVIOR (Dev Mode)
-------------------------------------
- The current build uses `--console` (i.e., no `--windowed`) to enable debug output.
  This helps diagnose runtime issues.
- All `common/` modules are included in the EXE bundle via `--add-data`.
  By default, **all subfolders** under `common/` will be copied unless filtered.

To reduce size and avoid unnecessary folders (like `tools/`, `docs/`, `tests/`):
  ➤ You must adjust either:
    [A] PyArmor obfuscation step (selective protection) OR  
    [B] The `--add-data` argument to include only required folders.

--------------------------------------
  2. BUILD SCRIPT STRUCTURE (Overview)
--------------------------------------
- `%PRJ_NAME%` and `%PRJ_ROOT%` must be defined at the top of the batch file.
- Output is placed in:
    > dist/%PRJ_NAME%/
  The EXE name and folder will match `%PRJ_NAME%`.

- Existing dist folder is auto-deleted before new build:
    > IF EXIST %DIST_DIR%%PRJ_NAME% rmdir /s /q ...

- Obfuscation (PyArmor) is optional. Enable by setting:
    > DO_OBFUSCATION=1
  And define the exact folders to obfuscate using:
    > OBF_MODULES=common/core common/modules

------------------------------
  3. DEVELOPER DEBUG TIPS
------------------------------
✔ Use `--console` for development to see exceptions or import errors.

✔ If `ModuleNotFoundError: No module named 'common'` appears:
    - Ensure correct relative path is used for `--add-data`
    - Check `sys.path.insert(...)` logic in your main script
    - Validate the final EXE folder has the correct `common/` structure

✔ If using PyArmor:
    - Ensure each target folder has `__init__.py` inside
    - Obfuscated folders must be copied with correct structure
    - For release builds, rename obfuscated folder to `protected/` and update batch script

✔ If using new packages or subfolders:
    - Update `hidden_imports.txt` before rebuilding
    - Or pass new `--hidden-import` args in batch file

--------------------------------------
  4. RELEASE VERSION TIPS (Optional)
--------------------------------------
For production release builds:
- Use `--windowed` to hide the debug console
- Use a custom icon via:
    > --icon=your_icon.ico
- Optionally remove `.bat`, `.txt`, and development files from final zip

-------------------------------
  5. DO NOTs / CAVEATS
-------------------------------
✘ Do not manually edit `dist/` contents.
✘ Do not include unnecessary folders from `common/` unless required.
✘ Do not skip adding `__init__.py` in Python packages — PyInstaller will miss them.

-----------------------------------
  End of Developer README
-----------------------------------
