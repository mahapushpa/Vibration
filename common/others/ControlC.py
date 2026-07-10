import signal
import tkinter as tk

tk_root = tk.Tk()

signal.signal(signal.SIGINT, lambda x, y: tk_root.destroy())

tk_check = lambda: tk_root.after(500, tk_check)

tk_root.after(500, tk_check)

tk_root.bind_all("<Control-c>", lambda e: tk_root.destroy())

tk_root.mainloop()
