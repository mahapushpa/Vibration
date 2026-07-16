"""
path_manager.py - Manages sys.path and output directories (log, data, config)
Clean import setup for modular Python projects with structured folders.
"""

import os
import sys
import logging
from pathlib import Path

#-------------------------------------------------------------------------------
# Define project-relative folders to be added to sys.path
USEFUL_FOLDERS = [
    'vibmshared/core',
    'vibmshared/utils',
    'vibmshared/modules',
    # Add more here as needed
]

#-------------------------------------------------------------------------------
class PathManager:
    """
    Manages sys.path and project-relative folders:
    - Adds selected source folders (vibmshared/core, etc.)
    - Creates project-specific output folders (data, log, config)
    - Returns final resolved paths for ini/config usage
    """
    # Declare class-level subfolders_added for static access and class level
    subfolders_added = []
    
    def __init__(self, main_file: str, useful_folders: list[str]):
        """
        Initialize with the path of the main script (typically __file__).
        Adjust root folder for VS code and frozen EXE cases.
        """
        # Detect PyInstaller EXE mode
        if getattr(sys, 'frozen', False):
            # Executable: use the folder where EXE is located
            self.project_root = Path(sys.executable).resolve().parent
            self.project_root_parent  = Path(sys._MEIPASS)
        else:
            # Script mode (VS Code, normal Python): use source file's parent
            self.project_root = Path(main_file).resolve().parent
            self.project_root_parent  = self.project_root.parent            

        self.final_output_paths = {}  # Will store resolved folder paths
        self.output_folders_created = []
        # Populate class-level subfolders_added for static and class access
        PathManager.subfolders_added = []

        self.add_selected_folders(useful_folders)

    def add_selected_folders(self, folders: list[str]):
        """
        Add specific subfolders (relative to project root parent) to sys.path.
        Skips duplicates and invalid folders. Always adds project root itself.
        """
        from vibmshared.core.common import default_PathSettings

        # Add each requested subfolder relative to the project root parent
        for folder in folders:
            path = (self.project_root_parent / folder).resolve()
            if path.is_dir() and str(path) not in sys.path:
                sys.path.append(str(path))
                self.subfolders_added.append(str(path))

        # Always add the project root
        if str(self.project_root) not in sys.path:
            sys.path.append(str(self.project_root))
            self.subfolders_added.append(str(self.project_root))

        # Ensure and track output folders from default_PathSettings
        self.ensure_output_folders(default_folders = default_PathSettings)
       
    def ensure_output_folders(self, default_folders: dict):
        """
        Create output folders relative to project root.
        Save resolved absolute paths into self.final_output_paths.
        """

        for key, rel_path in default_folders.items():
            full_path = (self.project_root / rel_path).resolve()
            try:
                full_path.mkdir(parents=True, exist_ok=True)
                self.output_folders_created.append(str(full_path))
                self.final_output_paths[key] = str(full_path)
            except Exception as e:
                logging.error(f"[PathManager] Failed to create folder '{full_path}': {e}")

    @staticmethod
    def find_file_in_subfolders(filename: str) -> Path | None:
        """
        Searches for the given filename in all registered subfolders.
        Returns the full path if found, else None.
        """
        for folder in PathManager.subfolders_added:
            full_path = Path(folder) / filename
            if full_path.exists():
                return full_path
        return None
    
    def find_file_in_subfolders1(self, filename: str) -> Path | None:
        """
        Searches for the given filename in all registered subfolders.
        Returns the full path if found, else None.
        """
        for folder in self.subfolders_added:
            full_path = Path(folder) / filename
            if full_path.exists():
                return full_path
        return None
    
    def get_output_path_settings(self) -> dict:
        """
        Return the resolved path dictionary for use in INI or config logic.
        """
        return self.final_output_paths.copy()
    
    def get_relative_path_settings(self) -> dict:
        """
        Return output paths as relative strings (relative to project root),
        suitable for writing into INI files.
        """
        rel_paths = {}
        for k, abs_path in self.final_output_paths.items():
            rel_path = Path(abs_path).relative_to(self.project_root)
            rel_paths[k] = str(rel_path)
        return rel_paths

    def get_config_path(self) -> str:
        """Return the config path to use in INI or config logic."""
        return self.final_output_paths.get("config_path", "./config")

    def get_relative_path(self, abs_path: str) -> str:
        """
        Convert an absolute path to a path relative to project root.
        Falls back to original if conversion fails.
        """
        try:
            return f".\{os.path.relpath(abs_path, self.project_root)}"
        except Exception:
            return abs_path

    def get_absolute_path(self, filename: str) -> str:
        """Return absolute path from filename inside config folder."""
        return os.path.normpath(os.path.join(self.get_config_path(), filename))

    def get_file_name_only(self, full_path: str) -> str:
        """Extract filename from full or relative path."""
        return Path(full_path).name
            
    def summary(self):
        """
        Print a summary of all added and created paths.
        """
        print("[PathManager] Subfolders added to sys.path:")
        for path in self.subfolders_added:
            print("  ->", path)
        print("[PathManager] Output folders ensured:")
        for path in self.output_folders_created:
            print("  ->", path)
