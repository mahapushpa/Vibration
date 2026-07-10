import sys
from datetime import datetime
from pathlib import Path

def generate_readme(project_name: str, output_folder: str):
    readme = Path(output_folder) / "README.txt"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"{project_name} Executable Package",
        "-" * (len(project_name) + 21),
        "",
        f"Build Date     : {now}",
        "Python Version : 3.10+ recommended",
        "Dependencies   : None (Standalone EXE)",
        "",
        "How to Run:",
        "1. Double-click the EXE file",
        "2. The application will open the GUI interface",
        "",
        "Notes:",
        "- If the EXE does not open, ensure your system allows running unsigned apps",
        "- If needed, run from command line to see errors",
        "",
        "Troubleshooting:",
        "- Missing DLLs: Update your Windows environment",
        "- Blocked by Antivirus: Whitelist the EXE or build it locally",
        "",
        "Folder Contents:",
        "- [EXE File]         - Main executable",
        "- README.txt         - This file",
        "- hidden_imports.txt - Internal tool usage record (for developers)",
        "",
        "© YourCompanyName or Author, YYYY"
    ]

    with readme.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_readme.py <ProjectName> <OutputFolder>")
        sys.exit(1)
    generate_readme(sys.argv[1], sys.argv[2])
