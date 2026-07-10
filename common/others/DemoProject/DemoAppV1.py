import os, sys
from pathlib import Path

# Patch sys.path for frozen or dev
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
CURRENT_DIR = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
COMMON_DIR = os.path.abspath(os.path.join(CURRENT_DIR, 'common'))
if COMMON_DIR not in sys.path:
    sys.path.insert(0, COMMON_DIR)

import tkinter as tk
from common.utils.demo_helper import greet

def launch_gui():
    root = tk.Tk()
    root.title("Demo App V1")
    root.geometry("300x120")
    label = tk.Label(root, text=greet("Demo User"), font=("Segoe UI", 12))
    label.pack(pady=20)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()
