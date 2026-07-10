import tkinter as tk
from tkinter import ttk

style = ttk.Style()
style.theme_use("clam")  # clam respects all styling

# Custom Entry style
style.configure("Custom.TEntry",
    font=("Segoe UI", 10),
    foreground="black",              # default text
    fieldbackground="white",         # default background
    padding=4)

# Specific for readonly
style.map("Custom.TEntry",
    foreground=[("readonly", "black")],
    fieldbackground=[("readonly", "#f0f0f0")])  # light gray

root = tk.Tk()
# entry = ttk.Entry(root, style="Custom.TEntry", width=30)
# entry.insert(0, "Test Value")
# entry.configure(state="readonly")  # important: AFTER insert
# entry.pack(padx=10, pady=20)

frame = tk.Tk()
for i in range(5):
    var = tk.BooleanVar(value=True)
    chk = ttk.Checkbutton(frame, variable=var)
    chk.grid(row=i, column=0)

    label = ttk.Label(frame, text=f"Param {i}")
    label.grid(row=i, column=1)

    entry = ttk.Entry(frame)
    entry.grid(row=i, column=2)

root.mainloop()

