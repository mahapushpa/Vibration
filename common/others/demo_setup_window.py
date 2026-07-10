import tkinter as tk
from tkinter import ttk

def demo_setup_window(parent):
    win = tk.Toplevel(parent)
    win.title("Master Setup")
    win.geometry("750x380")

    # === Constants for uniform padding ===
    PAD_SIDE = 10    # Left/right gap from window
    PAD_TOP = 10     # Top gap from window
    PAD_BETWEEN = 10 # Space between internal frames
    PAD_BOTTOM = 10  # Bottom gap for buttons

    # === Main frame ===
    main_frame = ttk.Frame(win)
    main_frame.pack(fill="both", expand=True, padx=PAD_SIDE, pady=PAD_TOP)

    # === Row 0: Meta Section (2 frames) ===
    meta_frame = ttk.Frame(main_frame)
    meta_frame.grid(row=0, column=0, sticky="nw")

    meta1 = ttk.LabelFrame(meta_frame, text="Client and Order Info", padding=6)
    meta2 = ttk.LabelFrame(meta_frame, text="Product Revision Info", padding=6)
    meta1.grid(row=0, column=0, sticky="nw")
    meta2.grid(row=0, column=1, sticky="nw", padx=PAD_BETWEEN)

    # === Row 1: Parameter Section (3 frames) ===
    param_frame = ttk.Frame(main_frame)
    param_frame.grid(row=1, column=0, pady=(PAD_TOP, 0), sticky="nw")

    param1 = ttk.LabelFrame(param_frame, text="Hardware", padding=6)
    param2 = ttk.LabelFrame(param_frame, text="Analog", padding=6)
    param3 = ttk.LabelFrame(param_frame, text="System", padding=6)
    param1.grid(row=0, column=0, sticky="nw")
    param2.grid(row=0, column=1, sticky="nw", padx=PAD_BETWEEN)
    param3.grid(row=0, column=2, sticky="nw", padx=PAD_BETWEEN)

    # === Row 2: Button Bar ===
    btn_frame = ttk.Frame(main_frame)
    btn_frame.grid(row=2, column=0, pady=PAD_BOTTOM, sticky="ew")
    btn_frame.columnconfigure(0, weight=1)
    btn_frame.columnconfigure(1, weight=1)

    btn_save = ttk.Button(btn_frame, text="Save", width=12)
    btn_cancel = ttk.Button(btn_frame, text="Cancel", width=12, command=win.destroy)
    btn_save.grid(row=0, column=0, sticky="w", padx=(0, PAD_SIDE))
    btn_cancel.grid(row=0, column=1, sticky="e", padx=(PAD_SIDE, 0))

    # Optional: Configure uniform layout in param frames
    for pf in [param1, param2, param3]:
        for i in range(4):
            pf.columnconfigure(i, weight=0)

# === Run demo ===
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # hide root
    demo_setup_window(root)
    root.mainloop()
