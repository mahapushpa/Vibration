#-------------------------------------------------------------------------------
# GUI Utilities for Production Tool — Cleaned and Reviewed
#-------------------------------------------------------------------------------
"""
This module defines reusable GUI utilities for the Production Tool GUI:
- Tkinter widget styles and layout constants
- Widget drawing and value extraction helpers
- Tooltip handling class for on-hover help text
- Final window geometry adjustments for popups
"""

import  tkinter as tk
from    tkinter import ttk
from    tkinter.filedialog import asksaveasfilename

# Constants for uniform padding ----------------------------------
PAD_SIDE = 10    # Left/right gap from window
PAD_TOP  = 10    # Top gap from window
PAD_BETWEEN = 10 # Space between internal frames
PAD_BOTTOM  = 10  # Bottom gap for buttons

PAD_Y        = (4, 2)
PAD_X_LABEL  = (8, 4)
PAD_X_WIDGET = (0, 8)

#-------------------------------------------------------------------------------
# Widget Style Constants
#-------------------------------------------------------------------------------
# Font configuration
DEFAULT_FONT = ("Segoe UI", 9)
WIDGET_FONT  = ("Segoe UI", 10)
BUTTON_FONT  = ("Segoe UI", 11)
LOG_FONT     = ("Courier New", 11)
FRAME_FONT   = ("Arial", 11, "bold")
STATUS_FONT  = ("Arial", 11, "italic")
LABEL_FONT   = ("Segoe UI", 9, "bold")

# Button style
BUTTON_STYLE = {
    'fg': 'black',
    'justify': "center",
    'relief': "raised",
    'bd': 1,
    'padx': 6,
    'pady': 0,
    'height': 1,
    'cursor':"hand2",
    'font': BUTTON_FONT,
}

# Drop down style
BUTTON_DROP_DOWN_STYLE = {
    'fg': 'black',
    'relief': "raised",
    'bd': 1,
    'padx': 5,
    'pady': 4,
    'height': 1,
    'cursor':"hand2",
    'font': BUTTON_FONT,
}

# GUI Widget styles
WIDGET_STYLE_FRAME     = "Custom.TLabelframe"
WIDGET_STYLE_LABEL     = "Custom.TLabel"
WIDGET_STYLE_ENTRY     = "Custom.TEntry"
WIDGET_STYLE_CHECK     = "Custom.TCheckbutton"
WIDGET_STYLE_DROPDOWN  = "Custom.TMenubutton"
WIDGET_STYLE_BUTTON    = "Custom.TButton"
WIDGET_STYLE_VALUE     = "Value.TLabel"

WIDGET_STYLE_HEADER = {
    'font': ("Segoe UI", 9, "bold"),
    'foreground': "#333333",
}

# Button layout packing (spacing) – consistent across all toolbars
BUTTON_PACK_OPTIONS = {
    'side': 'left',
    'padx': (4, 4),   # Left, Right
    'pady': 2,
    'ipady': 1
}

BUTTON_PACK_OPTIONS_RIGHT = {
    'side': 'right',
    'padx': (4, 4),   # Left, Right
    'pady': 2,
    'ipady': 1
}

# Toolbar and Status Bar shared appearance
TOOLBAR_STYLE = {
    'bg': "lightgrey",
    'bd': 1,
    'relief': "sunken",
    'highlightthickness': 1,
}

# # Status bar label (text) style — visually aligned but independently tunable
STATUS_LABEL_STYLE = {
    'font': STATUS_FONT,
    'fg': "black",
    'bg': "lightgrey",
    'anchor': "w",
    'bd': 1,                   
    'padx': 4,
    'pady': 6,
    'height': 1,               
    'relief': "sunken",        
    'highlightthickness': 1,   
}

# Log window style
LOG_WIDGET_STYLE = {
    'font': LOG_FONT,
    'wrap': "word",
}

BUTTON_TOOLTIPS = {
    's': "System configuration options",
    'a': "ADC configuration options",
    'l': "Clear logs from the log window",
    'g': "Save logs to specified file",
    'q': "Exit the application",
}

# ------ SETUP Redraw as per needed Size ---------------------------
def finalize_geometry(parent, size: str = "adjust"):
    """Adjust window size to fit content with small padding."""
    parent.withdraw()                   # Step 1: Hide the window temporarily
    parent.update_idletasks()           # Calculate required layout
    if size == "adjust": 
        width = parent.winfo_reqwidth()    
        height = parent.winfo_reqheight()
    else:
        width = parent.winfo_width()     # self.win.winfo_width()
        height = parent.winfo_height()   # self.win.winfo_height()

    x = parent.winfo_screenwidth() // 2 - (width // 2)
    y = parent.winfo_screenheight() // 2 - (height // 2)
    parent.geometry(f"{width}x{height}+{x}+{y}")  # Step 3: Set final size
    parent.deiconify()

    # -------------------------------------------------------------------
def finalize_frame_layout(frame):
    """Set consistent column weights and internal padding for layout polish."""
    for i in range(4): # adjust if more columns are used
        frame.columnconfigure(i, weight=0) # horizontal space
        frame.rowconfigure(i, weight=0)    # vertical space

def set_widget_style():
    """Define shared ttk styles for widgets used across the GUI."""
    style = ttk.Style()
    style.theme_use("default")  # clam respects all styling

    readonly_bg = "#f0f0f0" # instead of "SystemButtonFace"
    # Main LabelFrame style
    style.configure("Custom.TLabelframe", padding=6)

    # Header label inside LabelFrame
    style.configure("Custom.TLabelframe.Label", font=FRAME_FONT)
        
    # Label style
    style.configure("Custom.TLabel", font=LABEL_FONT, padding=2)

    # Entry style
    # style.configure("Custom.TEntry", font=WIDGET_FONT, padding=4, relief="flat")
    # Entry widget: editable and read-only
    style.configure("Custom.TEntry",
                    font=WIDGET_FONT,
                    foreground="black",
                    fieldbackground="white",
                    padding=4)
    style.map("Custom.TEntry",
            foreground=[("readonly", "black")],
            fieldbackground=[("readonly", readonly_bg)])  # Gray background for read-only
    
    # Checkbutton style
    style.configure("Custom.TCheckbutton", font=WIDGET_FONT, padding=4, relief="flat", 
        indicatoron=True,      # Explicitly make it a standard checkbutton
        anchor="w",            # Align to the left if needed
        focuscolor="",         # Remove unwanted focus color
    )

    # Combobox: editable and read-only (dropdown arrow remains in read-only)
    style.configure("Custom.TCombobox",
                    font=WIDGET_FONT,
                    padding=4)

    style.map("Custom.TCombobox",
              foreground=[("readonly", "black")],
              fieldbackground=[("readonly", readonly_bg)])
    
    # Dropdown style (OptionMenu uses Menubutton)
    style.configure("Custom.TMenubutton", font=WIDGET_FONT, padding=4, relief="raised")

    # Button style (if ttk.Button used later)
    style.configure("Custom.TButton", font=WIDGET_FONT, padding=4, relief="raised")
    style.configure(WIDGET_STYLE_VALUE, font=("Segoe UI", 11, "bold"), foreground="navy")

# --------------------------------------
# Single Button Factory from One Definition
# --------------------------------------
def create_simple_button(toolbar, definition, tooltip=True):
    """
    Create one button from a single (label, underline, action, key, align_right) tuple.
    Returns the tk.Button object.
    """
    label, underline, action, key, align_right = definition

    btn = tk.Button(
        toolbar,
        text=label,
        underline=underline,
        command=wrap_with_beep(action),
        **BUTTON_STYLE,
    )
    pack_opts = BUTTON_PACK_OPTIONS_RIGHT if align_right else BUTTON_PACK_OPTIONS
    btn.pack(**pack_opts)

    if tooltip:
        try:
            btn.tooltip = Tooltip(btn, f"Ctrl+{key.upper()} - {label}")
        except ImportError:
            pass

    return btn
# --------------------------------------
# Simple Button Generator Utility
# --------------------------------------
def create_simple_button_all(toolbar, button_definitions, tooltip=True):
    """Create a set of buttons based on button_definitions.
       Returns: dict of key -> button widget."""
    buttons = {}
    for label, underline, action, key, align_right in button_definitions:
        btn = tk.Button(
            toolbar,
            text=label,
            underline=underline,
            command=wrap_with_beep(action),
            **BUTTON_STYLE,
        )
        pack_opts = BUTTON_PACK_OPTIONS_RIGHT if align_right else BUTTON_PACK_OPTIONS
        btn.pack(**pack_opts)

        if tooltip:
            tooltip_text = f"Ctrl+{key.upper()} - {label}"
            try:
                btn.tooltip = Tooltip(btn, tooltip_text)
            except ImportError:
                pass

        buttons[key.lower()] = btn
    return buttons

# --------------------------------------
# Dropdown Utility (for ButtonManager)
# --------------------------------------
def create_dropdown_button(parent, label, underline_idx, key, item_list, tooltip_msg):
    menu_button = tk.Menubutton(
        parent,
        text=label + ' ▼ ',
        underline=underline_idx,
        direction='below',
        **BUTTON_DROP_DOWN_STYLE,
    )

    menu = tk.Menu(menu_button, tearoff=0, font=("Segoe UI", 11))
    for i, (item_label, underline, callback, shortcut) in enumerate(item_list):
        if i > 0:   # separator BETWEEN items only (was a leading separator on every item)
            menu.add_separator()
        menu.add_command(label=item_label, underline=underline, command=wrap_with_beep(callback))
        # 'shortcut' field is reserved/unused for now (menu accelerators not wired)

    menu_button.config(menu=menu, cursor="hand2")
    menu_button.pack(**BUTTON_PACK_OPTIONS)

    try:
        menu_button.tooltip = Tooltip(menu_button, tooltip_msg)
    except ImportError:
        pass

    return menu_button, menu
# --------------------------------------
# Shared Shortcut Binding Helper
# --------------------------------------
def wrap_with_beep(func):
    def wrapped():
        from vibmshared.utils.utils_helpers import play_audio
        func()
        play_audio()
    return wrapped

def bind_shortcut_pair(root_window, key_char, callback):
    wrapped = wrap_with_beep(callback)
    root_window.bind(f'<Control-{key_char.lower()}>', lambda e: wrapped())
    root_window.bind(f'<Control-{key_char.upper()}>', lambda e: wrapped())
 
# Reusable GUI widget value extraction
# ------------------------------------
def get_widget_value(widget):
    if isinstance(widget, tk.Entry):
        return widget.get()
    if isinstance(widget, ttk.Checkbutton):
        return "true" if getattr(widget, 'var', tk.BooleanVar()).get() else "false"
        # return "true" if widget.state() in ("1", "true") else "false"

    if isinstance(widget, ttk.OptionMenu):
       # For OptionMenu, value must be accessed via attached .var
       # widget.get() does not exist, so we attach widget.var manually
       return widget.var.get() if hasattr(widget, "var") else "" 
       # return widget.cget("text")
    return ""

# Utility widget drawer (imported by both module drawing)
# -------------------------------------------------------------
def draw_widget(parent, row, col, flat_key, gui_def, val):
    """Draws label + widget (entry/check/dropdown) on given row and col offset."""
    widget = None
    label  = gui_def.get("label", flat_key)
    widget_type = gui_def.get("widget", "entry")
    base_col = col * 2
    ttk.Label(parent, style=WIDGET_STYLE_LABEL, text=label).grid(
        row=row, column=base_col + 0, sticky="e", padx=PAD_X_LABEL, pady=PAD_Y
    )

    if widget_type == "entry":
        ent = ttk.Entry(parent, style=WIDGET_STYLE_ENTRY, width=8)
        ent.insert(0, val)
        ent.grid(row=row, column=base_col + 1, sticky="w", padx=PAD_X_WIDGET, pady=PAD_Y)
        widget = ent

    elif widget_type == "check":
        var = tk.BooleanVar(value=(str(val).lower() in ("1", "true")))
        
        cb  = ttk.Checkbutton(parent, style=WIDGET_STYLE_CHECK, variable=var, 
            onvalue=True, offvalue=False, takefocus=False)  # Prevent focus ring
        cb.grid(row=row, column=base_col + 1, sticky="w", padx=PAD_X_WIDGET, pady=PAD_Y)
        cb.var = var              # attach for later access
        widget = cb

    elif widget_type == "dropdown":
        var  = tk.StringVar(value=val)
        opts = gui_def.get("options", [])
        om = ttk.OptionMenu(parent, var, val, *opts)
        om["style"] = WIDGET_STYLE_DROPDOWN
        om.grid(row=row, column=base_col + 1, sticky="w", padx=PAD_X_WIDGET, pady=PAD_Y)
        # For OptionMenu, value must be accessed via attached .var
        # widget.get() does not exist, so we attach widget.var manually
        om.var = var  # Explicitly attach the var, it is needed for dropdown.
        widget = om

    return widget

# Utility widget drawer for Program param section(imported by module drawing)
# -------------------------------------------------------------
def draw_widget_for_program(parent, row, col_offset, flat_key, gui_def, val, value_state):
    """Draws checkbox + label + widget (entry/check/dropdown) per program parameter."""
    checkbox_var = tk.BooleanVar(value=True)  # Default: selected
    widget = None
    label = gui_def.get("label", flat_key)
    widget_type = gui_def.get("widget", "entry")

    base_col = col_offset * 3  # Each item takes 3 columns

    # Label
    ttk.Label(parent, text=label, style=WIDGET_STYLE_LABEL).grid(
        row=row, column=base_col + 0, sticky="e", padx=PAD_X_LABEL, pady=PAD_Y
    )

    # Value Widget
    if widget_type == "entry":
        ent = ttk.Entry(parent, style=WIDGET_STYLE_ENTRY, width=12)
        ent.insert(0, val)
        ent.configure(state=value_state)
        ent.grid(row=row, column=base_col + 1, sticky="w", padx=PAD_X_WIDGET, pady=PAD_Y)
        widget = ent

    elif widget_type == "check":
        var = tk.BooleanVar(value=(str(val).lower() in ("1", "true")))
        cb = ttk.Checkbutton(parent, style=WIDGET_STYLE_CHECK, variable=var, 
                             onvalue=True, offvalue=False, takefocus=False)
        if value_state == "readonly":
            cb.state(["disabled"])
        cb.grid(row=row, column=base_col + 1, sticky="w", padx=PAD_X_WIDGET, pady=PAD_Y)
        cb.var = var
        widget = cb

    elif widget_type == "dropdown":
        var = tk.StringVar(value=val)
        opts = gui_def.get("options", [])
        om = ttk.OptionMenu(parent, var, val, *opts)
        om["style"] = WIDGET_STYLE_DROPDOWN
        om.grid(row=row, column=base_col + 1, sticky="w", padx=PAD_X_WIDGET, pady=PAD_Y)
        if value_state == "readonly":
            om.state(["disabled"])
        om.var = var
        widget = om

    # Selection checkbox
    chk = ttk.Checkbutton(parent, variable=checkbox_var, takefocus=False)
    chk.grid(row=row, column=base_col + 2, padx=(4, 0), pady=PAD_Y, sticky="e")
    
    return widget, checkbox_var

# --------------------------------------
# Shared Dummy Callback for Dropdown Sample
# --------------------------------------
def dummy_callback_live():
    print("Live Mode selected")

def dummy_callback_offline():
    print("Offline Mode selected")

def apply_tooltip(widget, label, tooltip_dict, default_suffix="operation for the device"):
    """
    Attach a tooltip to a widget using a dictionary with fallback text.

    Args:
        widget         : Tkinter widget to attach tooltip to
        label (str)    : Label used as key (typically button text)
        tooltip_dict   : Dict containing tooltips {lowercase_label: text}
        default_suffix : Fallback suffix for missing keys (default: 'operation for the device')
    """
    key = label.lower()
    tooltip_text = tooltip_dict.get(key, f"{label} {default_suffix}")
    Tooltip(widget, tooltip_text)

#-------------------------------------------------------------------------------
class Tooltip:
    # Tooltip helper
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event = None):
        if self.tipwindow or not self.text:
            return

        # Calculate desired position
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2

        # Estimate tooltip width
        root = self.widget.winfo_toplevel()
        screen_width = root.winfo_screenwidth()

        # Create tip window off-screen temporarily to measure it
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)

        label = tk.Label(tw, text=self.text, background="#ffffe0",
                         relief="solid", borderwidth=1,
                         font=("Segoe UI", 9))
        label.pack(ipadx=2)

        tw.update_idletasks()
        tooltip_width = tw.winfo_reqwidth()

        # Adjust X if tooltip would go off screen
        if x + tooltip_width > screen_width - 10:
            x = screen_width - tooltip_width - 10

        tw.wm_geometry(f"+{x}+{y}")

    def hide_tip(self, event = None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None
   
#-------------------------------------------------------------------------------
class CustomToolbar_tk(tk.Frame):
    # Flat Toolbar for Pure Tkinter GUI
    """Simplified toolbar with consistent styling, buttons added externally."""
    def __init__(self, parent):
        super().__init__(parent, **TOOLBAR_STYLE)
        self.pack(side = tk.TOP, fill = tk.X, padx = 0, pady = 0)

    def add_button(self, text, command, side = tk.LEFT, padding = 4):
        """Add a button to the toolbar dynamically."""
        button = ttk.Button(self, text = text, command = command)
        button.pack(side = side, padx = padding)
        return button

    def set_message(self, msg):
        """Compatibility placeholder."""
        pass

#-------------------------------------------------------------------------------
class CustomToolbar_mat:
    """Simplified Matplotlib toolbar with styled status message line."""

    def __init__(self, canvas_, parent_):
        from    matplotlib.backends.backend_tkagg import NavigationToolbar2Tk        
        self.toolitems = ()  # Hide all default buttons
        super().__init__(canvas_, parent_)

        self.configure(bg = "lightgrey", relief = "flat", bd = 1, highlightthickness = 2)

        for child in self.winfo_children():  # left over of canvas are hided by below loop
            try:
                child.configure(bg = "lightgrey", relief = "flat", bd = 0, highlightthickness = 0)
            except:
                pass

        self.pack_configure(side = tk.TOP, fill = tk.X, padx = 0, pady = 0)
        
        try:
            self.message.pack_forget()  # Hide status bar if it exists
        except AttributeError:
            pass

    def set_message(self, msg):
        """Suppress default mpl status messages."""
        pass

#-------------------------------------------------------------------------------
class CustomYesNoDialog:
    """
#-------------------------------------------------------------------------------
# CustomYesNoDialog for controlled Yes/No prompts with X-button handling
#-------------------------------------------------------------------------------
    A reusable Yes/No dialog with proper handling for the X button (window close).
    Usage:
        dlg = CustomYesNoDialog(parent, "Title", "Message text here")
        result = dlg.get_result
        if result is None:
            # Closed with X
        elif result is True:
            # Yes selected
        else:
            # No selected
    """

    def __init__(self, parent, title, message):
        import tkinter as tk
        self.parent = parent
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("300x120")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_cancel)

        tk.Label(self.dialog, text=message, wraplength=280, justify="left").pack(pady=10)

        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(pady = 5)
        tk.Button(btn_frame, text="Yes", width=10, command=self.on_yes).pack(side="left", padx=10)
        tk.Button(btn_frame, text="No",  width=10, command=self.on_no).pack(side="left",  padx=10)

        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_rootx() + parent.winfo_width() // 2 - 150
        y = parent.winfo_rooty() + parent.winfo_height() // 2 - 60
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.wait_window()

    def on_yes(self):
        self.result = True
        self.dialog.destroy()

    def on_no(self):
        self.result = False
        self.dialog.destroy()

    def on_cancel(self):
        self.result = None
        self.dialog.destroy()

    def get_result(self):
        return self.result

