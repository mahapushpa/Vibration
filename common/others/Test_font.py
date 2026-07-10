from tkinter import *
from tkinter.font import Font

root = Tk()
root.title("Login GUI")

# Define font styles
title_font = Font(family="Helvetica", size=18, weight="bold")
label_font = Font(family="Arial", size=12)
label_font1 = Font(family="Courier New", size=12)
entry_font = Font(family="Arial", size=12)

# Create widgets with specified fonts
title_label = Label(root, text="Login", font=title_font)
title_label.pack(pady=10)

username_label = Label(root, text="Username:", font=label_font)
username_label.pack()
username_entry = Entry(root, font=entry_font)
username_entry.pack(pady=5)

password_label = Label(root, text="Password:", font=label_font)
password_label.pack()
password_entry = Entry(root, show="*", font=entry_font)
password_entry.pack(pady=5)

login_button = Button(root, text="Login", font=label_font)
login_button.pack(pady=10)

login_button = Button(root, text="Login", font=label_font1)
login_button.pack(pady=10)

root.mainloop()