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
import  queue
import  signal
import  logging
import  tkinter as tk

#-------------------------------------------------------------------------------
from common.utils.utils_helpers     import guard_gui, safe_log

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
        from common.core.hdr_parser     import HeaderProcessor
        from common.core.file_save      import FileSave
        from common.utils.gui_utils     import set_widget_style
        from vibmscope.maps_class       import AppMainFrame # GUI and button controls
        from vibmscope.maps_signal      import Signal # Signal processing functions
        from vibmscope.maps_transfer    import TFProcessor, create_tf_parameters, SimulatorTF

        self.path_handler = path_mgr

        self.root = tk.Tk()
        set_widget_style()
        self.root.iconify()   # Start with the window minimized
        self.running = True   # Flag to track application state
        self.gui_busy = False # for race condition avoidance
        
        # initialization available connecction
        if get_sys_value('simulation_mode'):
            from vibmscope.simulator import Simulator
            self.connection_handler = Simulator()
        else:
            baudrate = get_sys_value('sys_serial_baudrate')
            self.connection_handler = SerialPort(baudrate)

        connection_type = get_session_flag('connection')
        safe_log(None, f"Connected to -> {connection_type}", do_print = True)

        # cmd_handler is needed before serial/simulation communication
        self.cmd_handler = CommandHandler(self.connection_handler)
        
        if connection_type == 'serial_port':
            from vibmscope.sync_remote   import sync_to_remote
            # initialization all system variales
            if not sync_to_remote(self.cmd_handler):
                safe_log(None, "Remote not responded. Exiting...", tag = "critical", do_print = True)
                sys.exit(0)        
            
        # draw tkinter screen with logo and title
        self.display_config = self.draw_tk_screen()

        # Initialize all necessary components and handlers
        self.hdr_handler   = HeaderProcessor()
        self.queue_handler = queue.Queue(maxsize = 8)
        self.file_handler  = FileSave(self.hdr_handler, path_handler = self.path_handler)

        n_receivers = get_sys_value('adc_channels') - 1 # for transfer funciton
        sys, exc = create_tf_parameters(simulation = get_sys_value("simulation_mode"), n_receivers = n_receivers)
        self.tf_handler = TFProcessor(system = sys, excitation = exc, display_config = self.display_config)

        if get_sys_value('simulation_mode'):
            sim = SimulatorTF(system = sys, excitation = exc, tf = self.tf_handler)
            sim.simulate_time_data()

        self.signal_handler = Signal(
            tk_root      = self.root,
            cmd_handler  = self.cmd_handler,
            file_handler = self.file_handler,
            hdr_handler  = self.hdr_handler,
            path_handler = self.path_handler
        )

        self.main_frame    = AppMainFrame(
            master         = self.root,
            display_config = self.display_config,
            queue_handler  = self.queue_handler,
            cmd_handler    = self.cmd_handler,
            file_handler   = self.file_handler,
            hdr_handler    = self.hdr_handler,
            signal_handler = self.signal_handler,
            con_handler    = self.connection_handler,
            tf_handler     = self.tf_handler,
        )
        
        self.main_frame.pack(fill = tk.BOTH, expand = True, padx = 0, pady = 0)

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT,  self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        # Ensure proper cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.stop)

        # Bind Ctrl+C/c in GUI to close the window
        self.root.bind_all("<Control-c>", lambda e: self.stop())
        self.root.bind_all("<Control-C>", lambda e: self.stop())

        self.root.deiconify()  # Show the window after initialization

        # Schedule GUI updates
        self.root.after(100, self.update_gui)

#-------------------------------------------------------------------------------
    def draw_tk_screen(self):
        # Set once before GUI initialization
        from common.core.product_meta       import ProductMeta
        from common.utils.display_helpers   import get_display_context
        ctx = get_display_context(root = self.root)
        ProductMeta.configure('VibMScope')  # or 'VibrationAnalyser', 'VibMTool'        
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

        # Step 1: Stop Session First, if it is on
        self.main_frame.buttons.quit_button()

        # Step 2: Cancel any scheduled GUI updates
        if hasattr(self, "update_gui"):
            try:
                self.root.after_cancel(self.update_gui)
                safe_log(None, "GUI update task canceled.", do_print = True)
            except Exception as e:
                safe_log(None, f"GUI update cancel failed: {e}", do_print = True)
				
        # Step 3: Just quit, don't destroy or sys.exit()
        self.root.quit()  # Quit Tkinter's main loop and exit naturally

#-------------------------------------------------------------------------------
    @guard_gui(flag_name = 'gui_busy')
    def update_gui(self):
        """Scheduled function to fetch data from the queue and update the GUI."""
        from common.core.common         import get_session_flag
        if get_session_flag('session') and not self.queue_handler.empty():
            max_process = min(4, self.queue_handler.qsize())  # safer throttle
            for _ in range(max_process):
                if not self.queue_handler.empty():
                    data = self.queue_handler.get()
                    if self.signal_handler.insert_new_data(data):
                        if self.signal_handler.all_fragments_rcvd:
                            # All fragments for one second received
                            self.signal_handler.all_fragments_rcvd = False
                            self.main_frame.plot_manager.update_plots_axes()
                            self.main_frame.plot_manager.draw_idle()

        if self.running:
            self.root.after(100, self.update_gui)

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    from common.core.path_manager import PathManager
    from common.core.sys_config   import sys_config_init

    path_mgr = PathManager(__file__, USEFUL_FOLDERS)
    sys_config_init(path_mgr)
    
    app = MainApp(path_mgr)
    app.run()

#-------------------------------------------------------------------------------
