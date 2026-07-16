# status_bar.py
#-------------------------------------------------------------------------------
import tkinter as tk

_statusbar_ref = None  # Optional global reference

def set_status_bar_handler(handler):
    """Register StatusBarHandler instance for global use."""
    global _statusbar_ref
    _statusbar_ref = handler

def update_status_bar(key, value=None, remove=False, alert=False, tone=None):
    if _statusbar_ref:
        _statusbar_ref.update(key, value, remove, alert, tone)

def reset_status_bar():
    if _statusbar_ref:
        _statusbar_ref.reset()
        update_status_bar("System", "Ready")

#-------------------------------------------------------------------------------
class StatusBarHandler:
    def __init__(self, parent_frame, style_dict=None):
        
        from vibmshared.utils.gui_utils import STATUS_LABEL_STYLE
        
        self.status_var = tk.StringVar()
        self._parts = {}

        # style_dict is now actually applied; default preserves the previous
        # hard-coded appearance for callers that pass nothing (VibMScope).
        style = style_dict or STATUS_LABEL_STYLE

        self.status_bar = tk.Label(
            parent_frame, text="", textvariable=self.status_var, **style
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Auto-register and set initial message
        set_status_bar_handler(self)
        reset_status_bar()

    def update(self, key, value=None, remove=False, alert=False, tone=None):
        if remove:
            self._parts.pop(key, None)
        else:
            self._parts[key] = value

        self._refresh()

        # Optional alert tone / color
        if alert:
            self.status_bar.config(bg="lightcoral")
            if tone:
                try:
                    from vibmshared.utils.utils_helpers import play_audio  # Adjust as needed
                    play_audio(tone)
                except Exception:
                    print('Audio device is not available')
        else:
            self.status_bar.config(bg="lightgrey")

    def reset(self):
        self._parts.clear()
        self._refresh()

    def _refresh(self):
        text = " | ".join(f"{k}: {v}" for k, v in self._parts.items())
        max_len = 100
        if len(text) > max_len:
            text = text[:max_len - 3].rstrip() + "..."
        self.status_var.set(text)

#-------------------------------------------------------------------------------
    # test_status_bar.py
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Adds 'project_root'

    from core.product_meta       import ProductMeta
    root = tk.Tk()
    ProductMeta.configure('vibmscope')  # or 'VibrationAnalyser', 'vibmtool'        
    ProductMeta.set_icon(root)
    ProductMeta.set_title(root)    
    root.update_idletasks()
    root.state('zoomed')
    root.update()
    sb = StatusBarHandler(root)
    update_status_bar("Test", "Running")
    root.after(2000, lambda: update_status_bar("Test", "Completed"))
    root.after(4000, lambda: reset_status_bar())
    root.mainloop()
