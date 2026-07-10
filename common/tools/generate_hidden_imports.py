"""
Hybrid Hidden Import Generator
- Combines strengths of old and new versions
- Robust parsing using AST
- CLI support with --output
- Merges output from multiple folders
- Filters standard libraries and deduplicates entries
"""

import os
import sys
import ast
import sysconfig
import argparse
from pathlib import Path
from typing import Set

# -------------------------
# STANDARD LIBRARIES (excluded)
# -------------------------
STANDARD_LIBS = set(sys.builtin_module_names)
STANDARD_LIBS.update(sysconfig.get_paths().keys())

# -------------------------
# Local module patterns (excluded)
# -------------------------
LOCAL_MODULES = ['core', 'utils', 'modules', 'production', 'common', 'vibmscope']

# -------------------------
# Function: Extract Imports from One File
# -------------------------
def extract_imports_from_file(file_path: Path) -> Set[str]:
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            node = ast.parse(f.read(), filename=str(file_path))
        for n in ast.walk(node):
            if isinstance(n, ast.Import):
                for alias in n.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom):
                if n.module:
                    imports.add(n.module.split('.')[0])
    except Exception as e:
        print(f"[WARN] Failed to parse {file_path}: {e}")
    return imports

# -------------------------
# Function: Walk Folder & Collect Imports
# -------------------------
def collect_imports(paths: list) -> Set[str]:
    all_imports = set()
    for path_str in paths:
        path = Path(path_str)
        if not path.exists():
            print(f"[WARN] Path does not exist: {path_str}")
            continue
        
        # If wildcard (e.g., *.py)
        if path.is_file() or "*" in path.name:
            for file in path.parent.glob(path.name):
                if file.suffix == ".py":
                    all_imports |= extract_imports_from_file(file)
        else:
            for file in path.rglob("*.py"):
                all_imports |= extract_imports_from_file(file)
    return all_imports

# -------------------------
# Function: Filter Imports
# -------------------------
def filter_imports(modules: Set[str]) -> Set[str]:
    final = set()
    for mod in modules:
        if mod in STANDARD_LIBS:
            continue
        if any(mod.startswith(prefix) for prefix in LOCAL_MODULES):
            continue
        final.add(mod)
    # Override tkinter with tkinter.ttk
    final = {mod if mod != "tkinter" else "tkinter.ttk" for mod in final}        
    return final

# -------------------------
# Main
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate hidden imports for PyInstaller")
    parser.add_argument("paths", nargs="+", help="Paths to scan (folders or *.py files)")
    parser.add_argument("--output", required=True, help="Output file to save imports")
    args = parser.parse_args()

    print("[INFO] Generating hidden imports...")
    raw_imports = collect_imports(args.paths)
    hidden_imports = filter_imports(raw_imports)

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        for imp in sorted(hidden_imports):
            f.write(f"--hidden-import {imp}\n")

    #print(f"[OK] Hidden imports written to: {output_path}")

if __name__ == "__main__":
    main()
