import os
import math
import logging
import traceback
import numpy as np
import tkinter as tk
import matplotlib.pyplot as plt
from tkinter import filedialog, messagebox

#-------------------------------------------------------------------------------
from datetime import datetime
from collections import deque as dq
from matplotlib.ticker import FixedLocator, AutoMinorLocator
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

#-------------------------------------------------------------------------------
from vibmscope.vib_features     import IS_ENABLED
from vibmshared.core.parameters     import PlotParams
from vibmshared.core.sys_config     import get_sys_value, INI_FILE
from vibmshared.core.serial_comm    import ConnectionThreadManager
from vibmshared.core.common         import get_session_flag, set_session_flag 
from vibmshared.modules.cmd_helpers import write_single_param_direct
from vibmshared.utils.utils_helpers import safe_log

from vibmshared.utils.gui_utils     import (
    CustomToolbar_tk,
    create_simple_button, bind_shortcut_pair,
    create_dropdown_button, dummy_callback_live, dummy_callback_offline,
)
from vibmshared.utils.status_bar    import (
    update_status_bar, 
    reset_status_bar,
    StatusBarHandler,
)

#-------------------------------------------------------------------------------
class AppMainFrame(tk.Frame):
    """Main GUI frame managing plots, buttons, and serial thread control."""
    def __init__(self, master, display_config, queue_handler, cmd_handler, file_handler, hdr_handler, 
                        signal_handler, con_handler, tf_handler):
        super().__init__(master)

        self.root_window    = master
        self.display_config = display_config
        self.queue_handler  = queue_handler
        self.cmd_handler    = cmd_handler
        self.file_handler   = file_handler
        self.hdr_handler    = hdr_handler
        self.signal_handler = signal_handler
        self.con_handler    = con_handler
        self.tf_handler     = tf_handler

        self.status_handler = StatusBarHandler(self)

        self.conn_thread_mgr = ConnectionThreadManager(
            self.queue_handler, 
            self.signal_handler, 
            self.con_handler,
        )

        self.plot_manager  = PlotManager(
            parent_frame   = self,            # this frame (AppMainFrame)
            display_config = self.display_config,
            signal_handler = self.signal_handler, 
            tf_handler     = self.tf_handler,
            hdr_handler    = self.hdr_handler,
        )
        
        self.buttons = ButtonManager(
            parent_frame    = self,            # this frame (AppMainFrame)
            root_window     = self.root_window,
            toolbar         = self.plot_manager.toolbar,
            cmd_handler     = self.cmd_handler, 
            conn_thread_mgr = self.conn_thread_mgr,
            signal_handler  = self.signal_handler,
            con_handler     = self.con_handler,
            tf_handler      = self.tf_handler,
        )

#-------------------------------------------------------------------------------
class PlotManager:
    """Manages all plot axes, styling, and update logic."""
    def __init__(self, parent_frame, display_config, signal_handler, tf_handler, hdr_handler):
        self.parent_frame = parent_frame
        self.display_config = display_config
        self.signal_handler = signal_handler
        self.tf_handler   = tf_handler
        self.hdr_handler = hdr_handler
        self.time_xtick_label = None 
        self.init_plots()

    #---------------------------------------------------------------------------
    def init_plots(self):
        from matplotlib.figure import Figure
        width  = self.display_config['width_in']
        height = self.display_config['height_in']
        dpi = self.display_config.get('dpi', 144)
        self.figure = Figure(figsize=(width, height), dpi = dpi)
        gs = self.figure.add_gridspec(nrows=2, ncols=1, height_ratios=[1, 1],
                                    top=0.96, bottom=0.08, left=0.06, right=0.95, hspace=0.25)

        self.aTime = self.figure.add_subplot(gs[0])
        self.aFFT  = self.figure.add_subplot(gs[1])

        # Create the canvas and toolbar
        self.toolbar = CustomToolbar_tk(self.parent_frame)
        self.canvas  = FigureCanvasTkAgg(self.figure, self.parent_frame)
        self.canvas.get_tk_widget().pack(side = tk.TOP, fill = tk.BOTH, expand = True, padx = 0, pady = 0)
        # self.toolbar.update()

        plotLineWidth = 0.6

        # Time domain setup
        self.draw_axes(self.aTime, 'Time Domain', PlotParams.get_time_x_label(), PlotParams.get_time_y_label())
        ydata = np.array([np.array(ch) for ch in self.signal_handler.t_ydata])  # shape: (no_of_channels, n_samples)
        ydata = ydata.T  # shape: (n_samples, no_of_channels)
        self.signal_handler.time_channels = self.aTime.plot(self.signal_handler.t_xdata, ydata,
                                        linewidth = plotLineWidth)
        # Frequency domain setup
        self.draw_axes(self.aFFT, 'Frequency Domain', PlotParams.get_fft_x_label(), PlotParams.get_fft_y_label())
        fdata = np.array([np.array(ch) for ch in self.signal_handler.f_ydata])  # shape: (no_of_channels, n_samples)
        fdata = fdata.T  # shape: (n_samples, no_of_channels)
        self.signal_handler.freq_channels = self.aFFT.plot(self.signal_handler.f_xdata, fdata, 
                                          linewidth = plotLineWidth)
        self.add_styled_channel_labels(self.aTime)
        self.add_styled_channel_labels(self.aFFT)
        self.canvas.draw_idle()

    #---------------------------------------------------------------------------
    def update_plots_axes(self):
        try:
            self.insert_xtick_time_string()
            self.update_time_axes()
            self.update_frequency_axes()
        except Exception as e:
            print(f"[EXCEPTION] Plot update failed: {e}")
            logging.error(f"Plot update failed: {e}")
            logging.debug(traceback.format_exc())

    #---------------------------------------------------------------------------
    def update_time_axes(self):
        ydata = self.signal_handler.t_ydata
        for i in range(self.signal_handler.no_of_channels):
            self.signal_handler.time_channels[i].set_ydata(ydata[i])

        # print("Shape of ydata:", np.shape(ydata))
        # print("Type:", type(ydata))

        # Compute Y-limits dynamically with new data
        yTmin = min(np.min(np.asarray(y)) for y in ydata)
        yTmax = max(np.max(np.asarray(y)) for y in ydata)
        
        max_abs = np.max([abs(yTmin), abs(yTmax)])
        

        # Get appropriate ceil value based on selected unit
        yTceil = PlotParams.get_time_axis_value('ceil')

        # Get appropriate maximum value based on selected unit
        yTmaxLim = PlotParams.get_time_axis_value('max')

        # Minimum y-range for readability and Check are signal is within a ceil value range
        is_within_ceil = max_abs < yTceil
        if is_within_ceil: # Within ceil
            yTmin, yTmax = -yTceil, yTceil # Force symmetrical limits

        else:
            # Ensure symmetric scaling with `ceil()`
            yTmax = math.ceil(max_abs / yTceil) * yTceil  	# Round up to nearest unit-based value
            yTmin = -yTmax # Force symmetry

            # If max_abs and new limit are equal after ceil operation, it will touch the boundary
            if yTmax == max_abs and yTmax < yTmaxLim:
                yTmax += yTceil  # Move to the next ceil step
                yTmin = -yTmax   # Maintain symmetry

        # Skip `set_ylim()` if limits are unchanged, else Apply new limits to Y-axis
        if self.aTime.get_ylim() != (yTmin, yTmax):
            self.aTime.set_ylim(yTmin, yTmax)
            Division = PlotParams.get_axis_division_value('timeYMjrDiv')
            self.aTime.yaxis.set_major_locator(FixedLocator(np.linspace(yTmin, yTmax, Division + 1)))

    #---------------------------------------------------------------------------
    def update_frequency_axes(self):
        # Convert Time y-axis data to array for signal and file handling from deque becuase
        # arrays are more efficient for signal processing and file operations
        """Update frequency domain plot based on latest signal data."""
        f_data = []
        for ch in range(self.signal_handler.no_of_channels):
            y_arr = np.asarray(self.signal_handler.t_ydata[ch], dtype = np.float32)
            processed = self.signal_handler.processor.preprocessing_signal(y_arr)
            fft_out, dc_val = self.signal_handler.processor.compute_transform(processed)
            self.signal_handler.dc_value[ch] = dc_val
            f_data.append(fft_out[:len(self.signal_handler.f_xdata)])

        # Store as NumPy array: shape = (n_channels, n_samples)
        self.signal_handler.f_ydata = np.array(f_data)        

        # Update the plot
        for ch in range(self.signal_handler.no_of_channels):
            self.signal_handler.freq_channels[ch].set_ydata(self.signal_handler.f_ydata[ch])

        # Compute Y-limits dynamically for FFT Plot
        yFmax = max(np.max(np.asarray(y)) for y in self.signal_handler.f_ydata)
        yFmin, yFmax = 0, np.max([abs(yFmax)])

        # Dynamically adjust ceiling step based on max amplitude
        yFceil = max(PlotParams.get_fft_axis_value('ceil'), math.ceil(yFmax * 0.2))  
        yFmaxLim = PlotParams.get_fft_axis_value('max')

        # Ensure symmetric scaling with `ceil()`
        yFmax = math.ceil(yFmax / yFceil) * yFceil  # Round up to nearest unit-based value

        # If yFmax equals to new limit after ceil operation, it will touch the boundary
        if yFmax == np.max(self.signal_handler.f_ydata) and yFmax < yFmaxLim:
            yFmax += yFceil  # Add one ceil step to create a gap from the boundary

        # Apply updated limits to FFT Y-axis only if changed
        if self.aFFT.get_ylim() != (yFmin, yFmax):
            self.aFFT.set_ylim(yFmin, yFmax)
            Division = PlotParams.get_axis_division_value('freqYMjrDiv')
            self.aFFT.yaxis.set_major_locator(FixedLocator(np.linspace(yFmin, yFmax, Division + 1)))

    #---------------------------------------------------------------------------
    def insert_xtick_time_string(self):
        # Use the data's own time base: hdr_handler.system_time is sourced
        # from the remote GSN RTC when available (else the laptop clock,
        # upstream in HeaderProcessor) — tick labels now match the recorded
        # timestamps. datetime.now() only before any header has been parsed
        # (system_time still 0). (DECIDED 2026-07-16.)
        system_time = int(getattr(self.hdr_handler, 'system_time', 0) or 0)
        if system_time > 0:
            _, _, time_str = self.hdr_handler.get_time_string(system_time)
        else:
            time_str = datetime.now().strftime('%H:%M:%S')
        self.time_xtick_label.extend([time_str])
        self.aTime.set_xticklabels(self.time_xtick_label)
        
    #---------------------------------------------------------------------------
    def draw_idle(self):
        self.canvas.draw_idle()
        self.canvas.flush_events()
    
    #---------------------------------------------------------------------------
    def add_styled_channel_labels(self, ax, repeat_count = 8):
        """
        Adds styled, right-aligned labels in the top-right corner of a given Axes.
        Each label mimics the line's linestyle and color.
        Auto-generates label text as 'Channel N' for each visible line.
        """
        if hasattr(ax, '_channel_labels'):
            return  # Skip if already added

        ax._channel_labels = []
        lines = ax.get_lines()

        for idx, line in enumerate(lines):
            if not line.get_visible():
                continue

            color = line.get_color()
            linestyle = line.get_linestyle()

            # Line style pattern
            if isinstance(linestyle, tuple):
                pattern = '-'
            else:
                pattern = linestyle or ''

            # Generate the prefix visually mimicking line style
            prefix = pattern * repeat_count

            # Dynamic channel label
            label_text = f"Channel {idx + 1}"
            full_text = f"{prefix}   {label_text}"  # 3 spaces gap for clarity

            y_offset = 0.99 - idx * 0.05  # Vertical stacking

            text_obj = ax.text(
                0.995, y_offset,          # Top-right in axes coordinates
                full_text,
                color = color,
                ha = 'right', va = 'top',  # Text anchored to top-right
                fontsize = 'medium',       # Auto-adapted font size
                transform = ax.transAxes,
                zorder = 5,
                clip_on = False            # Always visible, even if zoomed
            )

            ax._channel_labels.append(text_obj)

    #---------------------------------------------------------------------------
    def draw_axes(self, ax, title, xlabel, ylabel):
        title_size = 10
        label_size = 9
        major_tick_size = 8
        minor_tick_size = 6
        
        font = 'Segoe UI'
        
        ax.set_title(title, fontname = font, fontsize = title_size,
                            fontweight = "bold", color = 'black')

        ax.xaxis.label.set_color('black')
        ax.tick_params(axis = 'x', colors = 'black')

        ax.yaxis.label.set_color('blue')
        ax.tick_params(axis = 'y', colors = 'blue')

        sample_rate = get_sys_value('adc_srate')
        seconds_in_window = PlotParams.get_time_x_span()
        samples_in_window = seconds_in_window * sample_rate
        
        if (title == 'Time Domain'):  # Time plot
            ticks = np.arange(0, samples_in_window + 1, sample_rate)  # Major ticks @second
            ax.margins(x = 0)  # Fix: Ensure data fits edge-to-edge
            ax.set_xlim(min(ticks), max(ticks))  # Fix: Remove left/right gap
            ax.xaxis.set_major_locator(FixedLocator(ticks))  
            ax.xaxis.set_minor_locator(AutoMinorLocator(PlotParams.get_axis_division_value('timeXMnrDiv'))) # minor ticks
            self.time_xtick_label = dq([f"00:00:0{t}" for t in range(seconds_in_window + 1)], 
                                                maxlen = seconds_in_window + 1)
            ax.set_xticklabels(self.time_xtick_label)        

            y_span = PlotParams.get_time_axis_value('max')
            tick_count = PlotParams.get_axis_division_value('timeYMjrDiv') + 1  # Major ticks
            tick_positions = np.linspace(-y_span, y_span, tick_count)
            
            ax.margins(y = 0)  # Fix: Ensure data fits edge-to-edge
            ax.set_ylim(-y_span, y_span)
            ax.yaxis.set_major_locator(FixedLocator(tick_positions))    # Major ticks
            ax.yaxis.set_minor_locator(AutoMinorLocator(PlotParams.get_axis_division_value('timeYMnrDiv')))  # Minor ticks
            
            # NOTE: Using deque for ticklabels because standard set_yticklabels()
            # gets reset on set_ylim(). This approach preserves labels without re-applying.
            ax.set_yticklabels(dq(np.linspace(-y_span, y_span, num = tick_count, dtype = np.int16)))

        elif (title == 'Frequency Domain'):  
            ticks = np.arange(0, PlotParams.fftXParams['max_hz'] + 1, PlotParams.get_axis_division_value('freqXMjrDiv'))   # Major ticks every 100 Hz
            ax.margins(x = 0)  # Fix: Ensure data fits edge-to-edge
            ax.set_xlim(min(ticks), max(ticks))  # Fix: Remove left/right gap
            ax.xaxis.set_major_locator(FixedLocator(ticks)) # Fix tick positions
            ax.xaxis.set_minor_locator(AutoMinorLocator(PlotParams.get_axis_division_value('freqXMnrDiv')))  # 5 minor ticks per major tick
            ax.set_xticklabels([f"{t}" for t in ticks])   # Generate frequency labels

            y_span = PlotParams.get_fft_axis_value('max')
            tick_count = PlotParams.get_axis_division_value('freqYMjrDiv') + 1  # Major ticks
            tick_positions = np.linspace(0, y_span, tick_count)

            ax.margins(y = 0)  # Fix: Ensure data fits edge-to-edge
            ax.set_ylim(0, y_span)
            ax.yaxis.set_major_locator(FixedLocator(tick_positions))  # Y-axis ticks: 0, 0.1, 0.2, 0.3,...,1
            ax.yaxis.set_minor_locator(AutoMinorLocator(PlotParams.get_axis_division_value('freqYMnrDiv')))  # minor ticks
            ax.set_yticklabels(dq(np.linspace(0, y_span, num = tick_count, dtype = np.int16)))
            
        else:          
            print("Plot title is not defined")

        ax.set_xlabel(xlabel, fontsize = label_size, fontweight= "bold")
        ax.set_ylabel(ylabel, fontsize = label_size, fontweight= "bold")

        # Specify different settings for major and minor grids, transparency
        # Major grid lines (Darker, thicker)
        ax.grid(axis = 'both', which = 'major', linestyle = '-', linewidth = 0.6, alpha = 0.9, color = 'black')
        # Minor grid lines (Lighter, thinner)
        ax.grid(axis = 'both', which = 'minor', linestyle = '-', linewidth = 0.4, alpha = 0.5, color = 'gray')

        # Specify tick label size, to suppress tick labelsize to zero
        ax.tick_params(axis = 'both', which = 'major', direction = 'out', labelsize = major_tick_size, top = False, right = False)
        ax.tick_params(axis = 'both', which = 'minor', direction = 'out', labelsize = minor_tick_size, top = False, right = False)
        
        ax.format_coord = lambda x, y: ''   # switch off the x,y co-ordinates in screen

#-------------------------------------------------------------------------------
class ButtonManager:
    def __init__(self, parent_frame, root_window, toolbar,
                 cmd_handler, conn_thread_mgr,
                 signal_handler, con_handler, tf_handler):

        self.parent_frame = parent_frame
        self.root_window  = root_window
        self.toolbar      = toolbar
        self.cmd_handler  = cmd_handler
        self.start_cb     = conn_thread_mgr.start
        self.stop_cb      = conn_thread_mgr.stop
        self.signal_handler = signal_handler
        self.con_handler    = con_handler
        self.tf_handler     = tf_handler

        # Button reference dictionary
        self.buttons   = {}
        self.dropdowns = {}
		        
        self.create_simple_buttons()
        # self.create_dropdown_buttons()
        self.bind_all()

    #---------------------------------------------------------------------------
    def create_simple_buttons(self):
        self.button_definitions = [
		       # label,        u_idx, function,     shortcut, align_right
            ("Session On",       0, self.session_button, 's', False),  # Ctrl+s
            ("Recording On",     0, self.record_button,  'r', False),  # Ctrl+r
            ("Transmissibility", 0, self.tf_button,      't', False),  # Ctrl+t
            ("Export Data",      0, self.export_button,  'e', False),  # Ctrl+e
            ("Clear Setting",    1, self.reset_button,   'l', False),  # Ctrl+L ('c' freed — was double-bound with app quit [F5])
            ("Quit System",      0, self.quit_button,    'q', True),   # Ctrl+Q
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
        create_dropdown_button(
            parent=self.toolbar,
            label="Mode",
            underline_idx=0,
            key='m', # Ctrl+m
            item_list=[
                ("Live Mode",    0, dummy_callback_live, 'l'),
                ("Offline Mode", 0, dummy_callback_offline, 'o'),
            ],
            tooltip_msg="Ctrl+M – Select mode"
        )

    #---------------------------------------------------------------------------
    def bind_all(self):
        for _, _, action, key, _ in self.button_definitions:
            bind_shortcut_pair(self.root_window, key, action)

        bind_shortcut_pair(self.root_window, 'm', dummy_callback_live)
        self.root_window.focus_set()

    #---------------------------------------------------------------------------
    def send_session_cmd(self, value = None):
        """
        Sends the 'Session On' command and waits for an acknowledgment.
        Returns:
            True if acknowledgment received, False otherwise.
        """
        
        if value not in (0, 1):
            raise ValueError("Invalid session value, expected 0 or 1")
    
        try:
            success = write_single_param_direct(self.cmd_handler, None, 'SYS', 'SESSION', value)

        except (ValueError, TypeError) as e:
            # Return False rather than raise: callers only check truthiness
            # (`if self.send_session_cmd(...): ... else: ...`) and don't catch
            # exceptions from this call, so raising here bypassed their intended
            # error-handling branch entirely (P2.2 Finding 4).
            logging.error("[CMD] Invalid or short response while setting Session On/Off: %s", e)
            return False

        if not success:
            # `success` is a plain bool here (write_single_param_direct's return
            # type), not a status code — formatting it as hex always printed a
            # meaningless "0x0" and told the caller nothing (P2.2 Finding 4).
            logging.error("[CMD] Failed to send Session %s command (no ACK).", "On" if value else "Off")
            return False
        else:
            logging.info("[CMD] Send Session %s command.", "On" if value else "Off")
            return True

#-------------------------------------------------------------------------------
    def session_button(self):
        # Manages session start/stop based on port availability.
        connection = get_session_flag('connection')

        if connection == None:
            print("[Warning] Serial/Simulator Port is not open.")
            return False

        if get_session_flag('session'):
            # Stop Recording if Active
            if get_session_flag('record'):
                self.record_button()  # ensure record stops
                set_session_flag('record', False)
                set_session_flag('prev_record', False)
                # [F2] close_current_file(): saves the pending partial window
                # and writes the STOP_DATE/STOP_TIME tokens (DECIDED
                # 2026-07-16: captured data may be unrepeatable — never
                # discard on stop). The old close_open_files() saved nothing
                # and left literal "{ STOP_DATE }" placeholders, which then
                # crashed parse_txt_export() on this file. Same sequence
                # tf_button Case 1 already uses.
                self.signal_handler.close_current_file()

            set_session_flag('session', False)      # Keep before send_session_off to make composite call

            # Stop the background SerialReader thread FIRST, before issuing the
            # synchronous stop-session command below. send_session_cmd() blocks on
            # a direct serial_port.read() (up to CMD_TIMEOUT_SEC) from this (main)
            # thread; if the background thread were still alive it would be
            # concurrently calling serial_port.inWaiting()/read() on the same
            # pyserial.Serial object, corrupting both threads' framing state
            # (P2.2 Finding 2 — cross-thread serial read race on session stop).
            self.stop_cb()

            # NOTE: cmd_waiting is NOT set manually here. send_command() (called
            # via send_session_cmd() below) already owns cmd_waiting's full
            # lifecycle — setting it here too made this code a second, competing
            # owner of the same global lock. If this instance's cmd_sent_time was
            # recent from an unrelated prior command, that double-locking could
            # cause send_command() to reject this very stop command as "BUSY"
            # (P2.2 Finding 4).
            if connection == 'serial_port':
                if self.send_session_cmd(value = 0):
                    safe_log(None, "Session stopped.", do_print = True)
                else:
                    safe_log(None, "Session stop ACK not received.", tag = "error", do_print = True)

            self.buttons['s'].config(text = "Session On", relief = "raised")

            reset_status_bar()
        
        else:
            if connection == 'serial_port':
                if self.send_session_cmd(value = 1):  # here session flag is false, composite call
                    safe_log(None, "Session started.", do_print = True)
                else:
                    safe_log(None, "Session start ACK not received.", tag = "error", do_print = True)

            self.buttons['s'].config(text = "Session Off", relief = "sunken")
            set_session_flag('session', True)
            self.start_cb()
            
            update_status_bar("Session", "ON", tone = 'gui')
            update_status_bar("Serial", connection)
            
#-------------------------------------------------------------------------------
    def record_button(self):
        """Toggles recording state and updates button label/state."""
        if not get_session_flag('session'):
            print("[INFO] Session is not running.")
            return False

        toggle = not get_session_flag('record')

        set_session_flag('record', toggle)
        
        if toggle:
            update_status_bar("Record", "ON", tone = 'gui')
            self.buttons['r'].config(text = "Recording Off", relief = "sunken")
        else:
            update_status_bar("Record", remove = True)
            self.buttons['r'].config(text = "Recording On", relief = "raised")
            
        print(f"Data Recording : {'Started' if toggle else 'Stopped'}")

#-------------------------------------------------------------------------------
    def tf_button(self):
        """
        Transfer Function button handler:
        1) If session is ON: process the ongoing TXT recording via extract_signals().
        2) If session is OFF and user picks an NPZ: process_npz_data().
        3) NEW: If session is OFF and user picks a TXT: run extract_signals() just like case 1.
        """        
         # Case 1: Session ON — use the active record file (TXT)
        if get_session_flag('record'):     # True when session = on
            self.record_button()           # stops recording
            set_session_flag('prev_record', False)
            self.signal_handler.close_current_file() # close current open file
            self.tf_handler.extract_signals(self.signal_handler.record_filename)
            update_status_bar("TF", remove = True)
            update_status_bar("TF", "Processed")
            return
        
        # Case 2 + 3: Session OFF — let the user choose either .npz or .txt
        filename = filedialog.askopenfilename(
            title="Select TF Data File (.npz or .txt)",
            # Let one filter show both; also list each explicitly for convenience
            filetypes=[
                ("TF data files", ("*.npz", "*.txt")),
                ("NPZ files", "*.npz"),
                ("Text files", "*.txt"),
            ],
            initialdir=self.tf_handler.data_path,
        )
        if not filename:
            return

        ext = os.path.splitext(filename)[1].lower()
        base = os.path.splitext(os.path.basename(filename))[0]
        dir_ = os.path.dirname(filename)
        txt_file = os.path.join(dir_, f"{base}.txt")
        pdf_file = os.path.join(dir_, f"{base}.pdf")
        csv_file = os.path.join(dir_, f"{base}.csv")

        # If all final artifacts already exist, warn and skip
        if all(os.path.exists(p) for p in (txt_file, pdf_file, csv_file)):
            messagebox.showwarning("TF Output Exists", "TF output files already exist.\nNo processing done.")
            return

        if ext == ".npz":
            # Case 2 (unchanged): process existing NPZ
            self.tf_handler.process_npz_data(filename=filename)
            update_status_bar("TF", remove = True)
            update_status_bar("TF", "Processed")
            return

        if ext == ".txt":
            # Case 3 (NEW): treat like Case 1 — reuse the same path you trust for TXT
            self.tf_handler.extract_signals(filename)
            update_status_bar("TF", remove = True)
            update_status_bar("TF", "Processed")            
            return

        messagebox.showerror("Unsupported File", f"Unsupported file selected:\n{filename}")
        
#-------------------------------------------------------------------------------
    def export_button(self):
        if get_session_flag('session'):
            print("[INFO] Session Running, Need to stop.")
            return False
        
        filename = filedialog.askopenfilename(
            title = "Select TF NPZ File",
            filetypes = [("NPZ files", "*.npz")],
            initialdir = self.tf_handler.data_path,
        )
        if not filename:
            return

        base = os.path.splitext(os.path.basename(filename))[0]
        dir_ = os.path.dirname(filename)
        txt_file = os.path.join(dir_, f"{base}.txt")
        csv_file = os.path.join(dir_, f"{base}.csv")

        if all(os.path.exists(p) for p in (txt_file, csv_file)):
            messagebox.showwarning("TF Output Exists", "TF output files already exist.\nNo processing done.")
            return

        self.tf_handler.process_npz_data(filename = filename, export = True)

        update_status_bar("Export", remove = True)
        update_status_bar("Export", "Processed")

#-------------------------------------------------------------------------------
    def quit_button(self):
        """
        Gracefully stops the session and closes the application.
        Handles application exit, ensuring proper cleanup of the serial connection
        and stopping the serial thread before exiting.
        """
        
        reset_status_bar()
        connection = get_session_flag('connection')
        ser_port   = getattr(self.con_handler, 'serial_port', None)

        # Step 0: Stop recording first (if active) and close the file WITH
        # pending partial data + STOP tokens ([F2], DECIDED 2026-07-16).
        # Previously quit never stopped recording at all and Step 4's
        # close_open_files() saved nothing.
        if get_session_flag('record'):
            self.record_button()
            set_session_flag('record', False)
            set_session_flag('prev_record', False)
            self.signal_handler.close_current_file()

        # Step 1: Stop Session First, if it is on
        if get_session_flag('session'):
            set_session_flag('session', False) # have this before session_off command to make composite call

            # Stop the background SerialReader thread FIRST, before issuing the
            # synchronous stop-session command below, for the same reason as in
            # session_button(): send_session_cmd() blocks on a direct
            # serial_port.read() from this thread, and the background thread
            # must not still be concurrently reading the same port
            # (P2.2 Finding 2 — cross-thread serial read race on session stop).
            self.stop_cb()

            # NOTE: cmd_waiting is NOT set manually here — see the matching
            # note in session_button() (P2.2 Finding 4: double-locking).
            if connection == 'serial_port':
                if self.send_session_cmd(value = 0):
                    safe_log(None, "Session stopped.", do_print = True)
                else:
                    safe_log(None, "Session Off ACK not received.", tag = "warning", do_print = True)

        # Step 2: Stop the serial thread before GUI actions (no-op if already
        # stopped above; still needed here for the case session wasn't running)
        self.stop_cb()

        # Step 3: Close Serial Port Properly, need after thread close
        if connection == 'serial_port' and ser_port:
            try:
                if ser_port.isOpen():
                    ser_port.close()
                    safe_log(None, "Serial port closed.")
            except Exception as e:
                safe_log(None, f"Serial port close error: {e}", tag = "error", do_print = True)

        # Step 4: (removed) file closing now happens in Step 0 via
        # close_current_file() — the old close_open_files() call here wrote
        # nothing and only printed a duplicate "Closed file" message ([F2]).

        # Step 5: Quit the Tkinter mainloop (without destroying Tk explicitly)
        self.parent_frame.quit()
        safe_log(None, "Application Closed.", do_print = True)

#-------------------------------------------------------------------------------
    def reset_button(self):
        if get_session_flag("session"):
            messagebox.showwarning("Reset Blocked", "Please stop the session before resetting system parameters.")
            return

        ini_file = os.path.join(self.tf_handler.config_path, INI_FILE)

        if not os.path.exists(ini_file):
            messagebox.showinfo("No Action Needed", "System is already at default settings.")
            return

        confirm = messagebox.askyesno(
            "Confirm Reset",
            f"This will delete '{INI_FILE}'.\n"
            "Default parameters will be restored on next launch.\n\n"
            "Do you want to continue?"
        )
        if not confirm:
            return

        try:
            os.remove(ini_file)
            logging.info(f"[SYSTEM] {INI_FILE} deleted — system will reset to defaults on next launch.")
            update_status_bar("System", "Reset requested — restart required", tone="gui")
            messagebox.showinfo("Reset Complete", "System reset to defaults.\nApplication will now exit.")
            # Close port/thread and quit the mainloop properly — os._exit()
            # skipped serial-port cleanup (minor, 2026-07-16). Session is
            # guaranteed off here (guard above), so quit_button's Step 0/1
            # are no-ops and it just closes the port and quits.
            self.quit_button()
            self.root_window.destroy()  # clean Tk exit

            # messagebox.showinfo("Reset Complete", "System reset to defaults.\nPlease restart the application.")
        except Exception as e:
            logging.error(f"[SYSTEM] Failed to delete {INI_FILE}: %s", e)
            messagebox.showerror("Reset Failed", f"Could not delete {INI_FILE}:\n{e}")

#-------------------------------------------------------------------------------
# Optional Self-Test Block
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    # NOTE (2026-07-16): stale self-test — AppMainFrame now takes 9 args and
    # Signal() needs initialized handlers/config; this block TypeErrors if
    # run. Kept as a placeholder; rework or delete when a real harness exists.
    raise SystemExit("maps_class.py has no standalone self-test; run vibmscope.py")

