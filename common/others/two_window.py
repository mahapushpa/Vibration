import numpy as np
from tkinter import *
import tkinter as tk
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

if mpl.get_backend() != 'TkAgg':
    mpl.use("TkAgg", force = True)

class Window(Frame):
    def __init__(self, master = None):
        Frame.__init__(self, master)
        self.master = master
        self.master.title(' GUI Window ')
        self.master.state('zoomed')
        self.master.update()

        etiquette1 = Label(self.master, text = "Main Window for GUI with Maximised", bg = "darkgrey")
        etiquette1.pack(side = tk.TOP, fill = tk.X)

        etiquette2 = Label(self.master, text = "Status Bar of Main Window", bg = "darkgrey")
        etiquette2.pack(side = tk.BOTTOM, fill = tk.X)

        fig1, (ax1, ax2) = plt.subplots(nrows = 2, ncols = 1,
            height_ratios = [1, 1],     # vertical division of space in plots                                 
            gridspec_kw = {
                'top':    0.96,
                'bottom': 0.08,
                'left':   0.06,
                'right':  0.95,
                'hspace': 0.30,         # vertical spacing between plots
            }        
        )

        self.canvas  = FigureCanvasTkAgg(fig1, self.master)
        self.canvas.get_tk_widget().pack(side = tk.TOP, fill = tk.BOTH, expand = True, padx = 0, pady = 0)

        ax1.plot(np.linspace(0, 1, 100), np.sin(2 * np.pi * 5 * np.linspace(0, 1, 100)))
        ax1.set_title("Main GUI Plot 1 - Sine Wave", fontsize = 12)
        ax2.plot(np.linspace(0, 1, 100), np.linspace(0, 50, 100), color = 'red')
        ax2.set_title("Main GUI Plot 2 - Linear Ramp", fontsize = 12)
        ax1.set_xlabel("Frequency (Hz)", fontsize = 10)
        ax2.set_xlabel("Magnitude (dB)", fontsize = 10)        
        self.canvas.draw_idle()

        # self.new  = self.New_Window()

    def New_Window(self):
        win = Toplevel(self.master)
        win.title("TF Window")
        etiquette1 = Label(win, text="TF Window Status", bg = "lightgrey")
        etiquette1.pack(side = tk.BOTTOM, fill = tk.X)
        win.state('zoomed')
        win.update()

        fig1, ax1 = plt.subplots(nrows = 1, ncols = 1,
            gridspec_kw = {
                'top':    0.90,
                'bottom': 0.10,
                'left':   0.06,
                'right':  0.95,
            }        
        )
        canvas1  = FigureCanvasTkAgg(fig1, master = win)
        canvas1.get_tk_widget().pack(side = tk.TOP, fill = tk.BOTH, expand = True, padx = 0, pady = 0)
        # canvas1.get_tk_widget().place(x = 0, y = 0, relwidth = 1, relheight = 0.95)

        freqs = np.linspace(0, 100, 500)
        tf_vals = 20 * np.log10(np.abs(np.sin(2 * np.pi * freqs / 100)) + 0.1)  # Dummy TF data with floor
        ax1.plot(freqs, tf_vals, color="red")
        ax1.set_title("Transfer Function - TF View", fontsize = 16)
        ax1.set_xlabel("Frequency (Hz)")
        ax1.set_ylabel("Magnitude (dB)")

        # Status bar at the bottom
        # label = tk.Label(win, text="TF Window Status", bg = "lightgrey")
        # label.place(relx = 0, rely = 0.95, relwidth = 1, relheight = 0.05)

        canvas1.draw_idle()

    def New_Window1(self):
        win = Toplevel(self.master)
        win.title("TF Window")
        win.state("zoomed")
        win.update()
        
        frame = Frame(win)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.rowconfigure(0, weight=1)
        frame.rowconfigure(1, weight=0)
        frame.columnconfigure(0, weight=1)

        # Label at bottom
        # status = Label(frame, text="TF Window Status", bg="lightgrey")
        # status.pack(side=tk.BOTTOM, fill=tk.X)

        # Canvas fills remaining space
        fig1, ax1 = plt.subplots(
            nrows=1, ncols=1, #constrained_layout=True,
            gridspec_kw={
                'top': 0.90, 'bottom': 0.10, 'left': 0.06, 'right': 0.95,
            }
        )
        canvas1 = FigureCanvasTkAgg(fig1, master=frame)
        # canvas1.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # canvas1.get_tk_widget().place(x=0, y=0, relwidth=1, relheight=1)

        canvas1.get_tk_widget().grid(row=0, column=0, sticky='nsew')  # Fill all space
        label = Label(frame, text="Status Bar", bg="lightgrey")
        label.grid(row=1, column=0, sticky='ew')  # Full width
        
        # Plot
        freqs = np.linspace(0, 100, 500)
        tf_vals = 20 * np.log10(np.abs(np.sin(2 * np.pi * freqs / 100)) + 0.1)
        ax1.plot(freqs, tf_vals, color="red")
        ax1.set_title("Transfer Function - TF View", fontsize=16)
        ax1.set_xlabel("Frequency (Hz)")
        ax1.set_ylabel("Magnitude (dB)")
        canvas1.draw_idle()
        
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    import ctypes
    user32 = ctypes.windll.user32
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(0) # Reset to clean system DPI context, it must
        ctypes.windll.shcore.SetProcessDpiAwareness(1) # Apply desired DPI behavior (primary monitor)
    except:
        ctypes.windll.user32.SetProcessDPIAware()
    
    root = Tk()
    main = Window(root)
    # new  = main.New_Window()
    main.mainloop()