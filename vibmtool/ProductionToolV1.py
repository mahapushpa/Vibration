#-------------------------------------------------------------------------------
# These lines must be at top to make, default cannot be get loaded
import matplotlib
matplotlib.use("TkAgg", force = True)  # Force before pyplot import

#-------------------------------------------------------------------------------
# Add root path dynamically (1-liner version)
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project_root

if getattr(sys, 'frozen', False):
    CURRENT_DIR = os.path.dirname(sys.executable)
else:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

COMMON_DIR = os.path.abspath(os.path.join(CURRENT_DIR, 'common'))
if COMMON_DIR not in sys.path:
    sys.path.insert(0, COMMON_DIR)

#-------------------------------------------------------------------------------
import  signal
import  logging
import  tkinter as tk

#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Define project-relative folders to be added to sys.path
USEFUL_FOLDERS = [
    'common/core',
    'common/utils',
    'common/modules',
    # Add more here as needed
]

#-------------------------------------------------------------------------------
class MainApp:
    def __init__(self, path_mgr = None):
        from common.core.sys_config     import get_sys_value
        from common.core.common         import get_session_flag
        from common.core.serial_comm    import SerialPort
        from common.modules.cmd_remote  import CommandHandler
        from common.utils.gui_utils     import set_widget_style
        from productiontool.prd_gui_main    import AppMainFrame

        self.path_handler = path_mgr

        self.root = tk.Tk()
        set_widget_style()
        self.root.iconify()   # Start with the window minimized
        self.running = True   # Flag to track application state

        # initialization available connecction
        if get_sys_value('simulation_mode'):
            from vibmscope.simulator import Simulator
            self.connection_handler = Simulator()

        else:
            baudrate = get_sys_value('sys_serial_baudrate')
            self.connection_handler = SerialPort(baudrate)

        connection_type = get_session_flag('connection')
        
        print(f"[INFO] Connected to -> {connection_type}")
        logging.info(f"Connected to -> {connection_type}")

        self.cmd_handler = CommandHandler(self.connection_handler)
        
        # draw tkinter screen with logo and title
        self.display_config = self.draw_tk_screen()

        self.main_frame  = AppMainFrame(
            master       = self.root,
            cmd_handler  = self.cmd_handler,
            con_handler  = self.connection_handler,
            path_handler = self.path_handler,
        )

        self.main_frame.pack(fill = tk.BOTH, expand = True, padx = 0, pady = 0)

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT,  self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        # Ensure proper cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.stop)

        # Bind Ctrl+C/c in GUI to close the window
        # self.root.bind_all("<Control-c>", lambda e: self.stop())
        # self.root.bind_all("<Control-C>", lambda e: self.stop())

        self.root.deiconify()  # Show the window after initialization

#-------------------------------------------------------------------------------
    def draw_tk_screen(self):
        # Set once before GUI initialization
        from common.core.product_meta       import ProductMeta
        from common.utils.display_helpers   import get_display_context
        ctx = get_display_context(root = self.root)
        ProductMeta.configure('VibMTool')  # or 'VibrationAnalyser', 'VibMScope', 'VibMTool'        
        ProductMeta.set_icon(self.root)
        ProductMeta.set_title(self.root)
        self.root.update_idletasks()
        self.root.state('zoomed')
        self.root.update()
        return ctx

#-------------------------------------------------------------------------------
    def run(self):
        """Start the application and initialize config, profile, and GUI."""
        try:
            logging.info("Application started...")
            self.root.mainloop()
        except KeyboardInterrupt:
            logging.info("(Ctrl+C) Detected. Exiting...")
            self.stop()

#-------------------------------------------------------------------------------
    def stop(self, *args):
        """Gracefully exit the application."""
        self.running = False

        # Just quit, don't destroy or sys.exit()
        print("Application closed successfully.")
        logging.info("Application closed successfully.")
        self.root.quit()  # Quit Tkinter's main loop and exit naturally

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    from common.core.path_manager import PathManager
    from common.core.sys_config   import sys_config_init

    path_mgr = PathManager(__file__, USEFUL_FOLDERS)

    sys_config_init(path_mgr)
    app = MainApp(path_mgr)
    app.run()

#-------------------------------------------------------------------------------
