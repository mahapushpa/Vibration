from tkinter import *
from tkinter import ttk
import  tkinter as tk

root = Tk() 
root.geometry("300x200") 

w = Label(root, text ='GeeksForGeeks', font = "50") 
w.pack() 

Checkbutton1 = IntVar() 
val = "true"
var = IntVar(value=(str(val).lower() in ("1", "true")))

Button1 = ttk.Checkbutton(
                    root, 
                    text = "Tutorial", 
                    variable = var, 
                    onvalue = 1, 
                    offvalue = 0,
                    takefocus=False,  # ✅ Prevent focus ring
                    ) 
    
Button1.pack() 

mainloop()