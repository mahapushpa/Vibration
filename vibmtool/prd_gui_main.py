#-------------------------------------------------------------------------------
# Production Main GUI — Cleaned and Reviewed
#-------------------------------------------------------------------------------
import logging
import tkinter as tk
from   tkinter.filedialog import asksaveasfilename
from   tkinter import scrolledtext, filedialog

from   functools import partial
from   datetime import datetime

#-------------------------------------------------------------------------------
from tool_features    import IS_ENABLED
from prd_gui_setup   import SetupManager, SummaryDialog
from vibmshared.core.common   import get_session_flag
from vibmshared.modules.cmd_helpers import write_module_direct, read_module_direct

from vibmshared.utils.gui_utils     import (
    CustomToolbar_tk,
    LOG_WIDGET_STYLE,
    STATUS_LABEL_STYLE,
    bind_shortcut_pair, 
    create_simple_button, 
    create_dropdown_button,	    
)
from vibmshared.utils.status_bar    import (
    update_status_bar, 
    reset_status_bar,
    StatusBarHandler,
)

#-------------------------------------------------------------------------------
class LogManager:
    """Manages log widget and basic actions like color, timestamp, save."""
    def __init__(self, parent_frame, path_handler):
        self.parent_frame = parent_frame
        self.path_handler = path_handler
        self.config_dir   = self.path_handler.get_config_path()
        
        # Log area
        self.log_widget = scrolledtext.ScrolledText(
            self.parent_frame,
            **LOG_WIDGET_STYLE
        )
        self.log_widget.pack(fill = tk.BOTH, expand = True)

        self._init_tags()
        self.log("== Production Tool Ready ==", tag="info")
        
#-------------------------------------------------------------------------------
    def _init_tags(self):
        self.log_widget.tag_config('send',  foreground = 'blue')
        self.log_widget.tag_config('recv',  foreground = 'green')
        self.log_widget.tag_config('error', foreground = 'red')
        self.log_widget.tag_config('info',  foreground = 'black')

#-------------------------------------------------------------------------------
    def log(self, message, tag="info"):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted = f"[{timestamp}] {message}\n"
        self.log_widget.insert(tk.END, formatted, tag)
        self.log_widget.see(tk.END)  # Auto-scroll to bottom
        
#-------------------------------------------------------------------------------
    def clear_log(self):
        self.log_widget.delete('1.0', tk.END)

#-------------------------------------------------------------------------------
    def save_log(self, event = None):
        """Save current log text to a user-selected file inside config folder (production logs)."""
        # Use default directory from path handler
        default_dir  = getattr(self, 'config_dir', ".")  # fallback if not available
        default_name = "production_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"

        file_path = filedialog.asksaveasfilename(
            initialdir=default_dir,
            initialfile=default_name,
            defaultextension=".log",
            filetypes=[
                ("Log files", "*.log"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ],
            title="Save Production Log"
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.log_widget.get('1.0', tk.END))
                self.log(f"Production log saved to: {file_path}", tag = "info")
                print(f"[INFO] Production log saved to: {file_path}")
                
            except Exception as e:
                self.log(f"Failed to save production log: {e}", tag = "error")
                print(f"[ERROR] Failed to save production log: {e}")
                
#-------------------------------------------------------------------------------
class ButtonManager:
    def __init__(self, parent_frame, root_window, toolbar, cmd_handler, 
                                        con_handler, log_handler, path_handler):
        self.parent_frame = parent_frame
        self.root_window  = root_window
        self.toolbar      = toolbar
        self.cmd_handler  = cmd_handler
        self.con_handler  = con_handler
        self.log_handler  = log_handler
        self.path_handler = path_handler
        
        # Button reference dictionary
        self.buttons   = {}
        self.dropdowns = {}
		        
        self.create_simple_buttons()
        self.create_dropdown_buttons()
        self.bind_all()

    #---------------------------------------------------------------------------
    def create_simple_buttons(self):
        self.button_definitions = [
              # label,        u_idx, function,              shortcut, align_right
            ("Quit System",     0, self.quit_button,            'q', True),  # Ctrl+Q
            ("Clear Logs",      8, self.clr_log_button,         'g', True),  # ctrl+G
            ("Save Logs",       5, self.save_log_button,        'l', True),  # Ctrl+L
            ("Master Setup",    0, self.master_setup_button,    'm', False),
            ("Device Setup",    0, self.device_setup_button,    'd', False),
            ("Device Build",    0, self.device_program_button,  'p', False),
            ("Summary",         0, self.summary_button,         's', True),
        ]
        
        # One-liner: build all buttons and keep the dict
        # self.buttons = create_simple_button_all(self.toolbar, self.button_definitions)
        
        for definition in self.button_definitions:
            # label = definition[0]
            # if label == "Export Data":  # EXAMPLE condition to skip
                # continue
            btn = create_simple_button(self.toolbar, definition)
            self.buttons[definition[3].lower()] = btn  # key is shortcut
        
    #---------------------------------------------------------------------------
    def create_dropdown_buttons(self):
        if IS_ENABLED("ENABLE_SETUP_DROPDOWN"):
            # 'u' ("Data Set_u_p"): 'd' collided with the Device Setup button
            # shortcut — rekeyed proactively so enabling the flag is safe.
            self.dropdowns['u'] = create_dropdown_button(
                parent=self.toolbar,
                label="Data Setup",
                underline_idx=8,
                key='u', # Ctrl+U
                item_list=[
                ("Master Setup", 0, self.master_setup_button, 'm'),
                ("Device Setup", 0, self.device_setup_button, 'd'),
                ("Summary",      0, self.summary_button,      's'),
            ],
            tooltip_msg = "Ctrl+U - Select Data Setup"
            )

        if IS_ENABLED("ENABLE_BRD_DROPDOWN"):
            self.dropdowns['b'] = create_dropdown_button(
                parent=self.toolbar,
                label="Board",
                underline_idx=0,
                key='b', # Ctrl+B		
                item_list=[        
                ("Board Set", 6, self.brd_set_button, 's'),
                ("Board Get", 6, self.brd_get_button, 'g'),
            ],
            tooltip_msg="Ctrl+B - Select Board"
            )

        if IS_ENABLED("ENABLE_ADC_DROPDOWN"):
            self.dropdowns['a'] = create_dropdown_button(
                parent=self.toolbar,
                label="ADC",
                underline_idx=0,
                key='a', # Ctrl+A		
                item_list=[        
                ("ADC Set", 4, self.adc_set_button, 's'),
                ("ADC Get", 4, self.adc_get_button, 'g'),
            ],
            tooltip_msg="Ctrl+A - Select ADC"
            )

        if IS_ENABLED("ENABLE_SYS_DROPDOWN"):
            # Ctrl+S belongs to the Summary button; 'y' (SYstem) is free ([T3])
            self.dropdowns['y'] = create_dropdown_button(
                parent=self.toolbar,
                label="System",
                underline_idx=1,
                key='y', # Ctrl+Y
                item_list=[
                ("System Set", 7, self.sys_set_button, 's'),
                ("System Get", 7, self.sys_get_button, 'g'),
            ],
            tooltip_msg="Ctrl+Y - Select System"
            )
		
    #---------------------------------------------------------------------------
    def master_setup_button(self):
        try:
            mgr = SetupManager(self.root_window, self.log_handler,
                                self.path_handler, setup_mode = "master")
        except Exception as e:
            self.log_handler.log(f"Master Setup Error: {e}", tag = "error")
            return

        if getattr(mgr, 'completed', False):   # not on error/cancel/abort
            reset_status_bar()
            update_status_bar("MASTER", "Data")

    #---------------------------------------------------------------------------
    def device_setup_button(self):
        try:
            mgr = SetupManager(self.root_window, self.log_handler,
                                self.path_handler, setup_mode = "device")
        except Exception as e:
            self.log_handler.log(f"Device Setup Error: {e}", tag = "error")
            return

        if getattr(mgr, 'completed', False):   # not on error/cancel/abort
            reset_status_bar()
            update_status_bar("DEVICE", "Data")

    #---------------------------------------------------------------------------
    def device_program_button(self):
        try:
            mgr = SetupManager(self.root_window, self.log_handler,
                                self.path_handler, setup_mode = "program",
                                cmd_handler = self.cmd_handler)
        except Exception as e:
            self.log_handler.log(f"Device Build Error: {e}", tag = "error")
            return

        if getattr(mgr, 'completed', False):   # not on error/cancel/abort
            reset_status_bar()
            update_status_bar("BUILD", "Device")

    #---------------------------------------------------------------------------
    def summary_button(self):
        try:
            dlg = SummaryDialog(self.root_window, self.log_handler, self.path_handler)
        except Exception as e:
            self.log_handler.log(f"Summary Error: {e}", tag = "error")
            return

        if getattr(dlg, 'completed', False):   # only when the master loaded
            reset_status_bar()
            update_status_bar("SUMMARY", "Prepared")

    #---------------------------------------------------------------------------
    def save_log_button(self):
        self.log_handler.save_log()
        update_status_bar("LOG", "Saved")

    #---------------------------------------------------------------------------
    def brd_set_button(self):
        write_module_direct(self.cmd_handler, self.log_handler, module = 'BRD')

    def brd_get_button(self):
        read_module_direct(self.cmd_handler, self.log_handler, module = 'BRD')

    #---------------------------------------------------------------------------
    def sys_set_button(self):
        write_module_direct(self.cmd_handler, self.log_handler, module = 'SYS')

    #---------------------------------------------------------------------------
    def sys_get_button(self):
        read_module_direct(self.cmd_handler, self.log_handler, module = 'SYS')

    #---------------------------------------------------------------------------
    def adc_set_button(self):
        write_module_direct(self.cmd_handler, self.log_handler, module = 'ADC')

    #---------------------------------------------------------------------------
    def adc_get_button(self):
        read_module_direct(self.cmd_handler, self.log_handler, module = 'ADC')

    #---------------------------------------------------------------------------
    def clr_log_button(self):
        self.log_handler.clear_log()
        update_status_bar("LOG", "Cleared")

    #---------------------------------------------------------------------------
    def quit_button(self):
        ser_port = getattr(self.con_handler, 'serial_port', None)
        connection = get_session_flag('connection')
        if connection == 'serial_port' and ser_port:
            try:
                if ser_port.isOpen():
                    ser_port.close()
                    print("Serial port closed.")
            except Exception as e:
                print(f"Serial port close error: {e}")
        self.parent_frame.quit()
        print("Application closed successfully.")
        logging.info("Application closed successfully.")
        
    #---------------------------------------------------------------------------
    def bind_all(self):
        for key, (menu_button, menu) in self.dropdowns.items():
            open_menu = partial(self.popup_menu, menu_button, menu)
            self.root_window.bind(f'<Control-{key}>', open_menu)
            self.root_window.bind(f'<Control-{key.upper()}>', open_menu)

        for _, _, action, key, _ in self.button_definitions:
            bind_shortcut_pair(self.root_window, key, action)

        # Ctrl+F -> Focus Log Widget
        self.root_window.bind('<Control-f>', lambda e: self.log_handler.log_widget.focus_set())

        # Ctrl+C -> Allow clipboard copy only if widget is a Text box (disable exit)
        def allow_copy_only(event):
            if isinstance(event.widget, tk.Text):
                return  # allow normal copy
            return "break"

        self.root_window.bind_all("<Control-c>", allow_copy_only)
        self.root_window.focus_set()

    #---------------------------------------------------------------------------
    def popup_menu(self, menu_button, menu, event = None):
        x = menu_button.winfo_rootx()
        y = menu_button.winfo_rooty() + menu_button.winfo_height()
        menu.tk_popup(x, y)
        menu.grab_release()

    #---------------------------------------------------------------------------
    def set_button_state(self, key, enabled = True):
        """
        Enable or disable a button by key name (e.g., 's', 'e', 'q').
        Optionally changes visual style to indicate state.
        set_button_state('r', False) to disable
        self.button_manager.set_button_state('r', False)  # Disable Recording
        self.button_manager.set_button_state('t', False)  # Disable Transmissibility

        """
        btn = self.buttons.get(key.lower()) or self.dropdowns.get(key.lower())
        if isinstance(btn, tuple):      # dropdowns store (menu_button, menu)
            btn = btn[0]
        if btn:
            if enabled:
                btn.config(state='normal', fg='black')
            else:
                btn.config(state='disabled', fg='gray')

    #---------------------------------------------------------------------------
    def get_button_state(self, key):
        """Return True if button is enabled, False otherwise."""
        btn = self.buttons.get(key.lower()) or self.dropdowns.get(key.lower())
        if isinstance(btn, tuple):      # dropdowns store (menu_button, menu)
            btn = btn[0]
        return btn['state'] == 'normal' if btn else None

    #---------------------------------------------------------------------------
    def reset_all_buttons(self, enabled = True):
        """Enable or disable all buttons (except Quit)."""
        for key in {**self.buttons, **self.dropdowns}:
            if key != 'q':  # Keep Quit button always enabled
                self.set_button_state(key, enabled)

#-------------------------------------------------------------------------------
class AppMainFrame(tk.Frame):
    """Main GUI frame managing plots, buttons, and serial thread control."""
    def __init__(self, master, cmd_handler, con_handler, path_handler):
        super().__init__(master)

        self.root_window = master
        self.cmd_handler = cmd_handler
        self.con_handler = con_handler
        self.path_handler= path_handler

        self.toolbar = CustomToolbar_tk(self.root_window)
        self.status_handler = StatusBarHandler(self, style_dict = STATUS_LABEL_STYLE)
        
        self.log_manager = LogManager(
            parent_frame = self,         # this frame (AppMainFrame)
            path_handler = self.path_handler,
        )

        self.buttons = ButtonManager(
            parent_frame = self,         # this frame (AppMainFrame)
            root_window  = self.root_window,
            toolbar      = self.toolbar,
            cmd_handler  = self.cmd_handler, 
            con_handler  = self.con_handler,
            log_handler  = self.log_manager,
            path_handler = self.path_handler,
        )
