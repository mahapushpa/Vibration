import ctypes
user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Per-monitor DPI-aware
except:
    ctypes.windll.user32.SetProcessDPIAware()       # Fallback for Win < 8.1

import tkinter as tk
root = tk.Tk()

width_px  = root.winfo_screenwidth()
height_px = root.winfo_screenheight()
dpi       = root.winfo_fpixels("1i")

width_in  = width_px / dpi
height_in = height_px / dpi

print('Width: %i px, Height: %i px' % (width_px, height_px))
print('Width: %f in, Height: %f in' % (width_in, height_in))
print('Width: %f dpi' % (dpi))

[w, h] = [user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)]
print('Size is %f %f' % (w, h))

curr_dpi = w*96/width_px
print('Current DPI is %f' % (curr_dpi))
# from pylab import rcParams
# rcParams['figure.dpi'] = curr_dpi