#-------------------------------------------------------------------------------
import os
import sys

#-------------------------------------------------------------------------------
if __name__ == '__main__':
    #---------------------------------------------------------------------------
    # These lines must be at top to make, default cannot be get loaded
    import matplotlib
    matplotlib.use("TkAgg", force = True)  # Force before pyplot import

    #---------------------------------------------------------------------------
    # Add root path dynamically (1-liner version)
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Adds 'project_root'
    
#-------------------------------------------------------------------------------
# Transmissibility
import numpy as np
import matplotlib.pyplot as plt

#-------------------------------------------------------------------------------
from matplotlib.image import imread
from datetime import datetime, timedelta
from datetime import time as dt_time  # Avoid conflict
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

#-------------------------------------------------------------------------------
from common.core.parameters    import PlotParams, TFParams
from common.core.product_meta  import UserMeta, ProductMeta
from common.core.sys_config    import sys_config_init, get_sys_value

from common.utils.status_bar    import update_status_bar
from common.utils.plot_helpers  import set_clean_axis_ticks_labels
from common.utils.utils_helpers import (
    write_table_block, write_metadata_header, write_channel_metadata_block,
    format_filter_description,
)

#-------------------------------------------------------------------------------
class TFProcessor:
    def __init__(self, system = None, excitation = None, display_config = None):
        self.data_path       = get_sys_value('data_path')
        self.config_path     = get_sys_value('config_path')
        
        self.use_db          = get_sys_value('use_yscale_db')
        self.sample_rate     = get_sys_value('adc_srate')
        self.analysis_type   = get_sys_value('analysis_type')
        self.analysis_method = get_sys_value('analysis_method')
        self.display_config  = display_config

        self.sys = system
        self.exc = excitation
        self.input_signals  = []
        self.output_signals = []
        self.filename_npz = None

        if get_sys_value('simulation_mode'):
            if self.exc is None or self.sys is None:
                raise ValueError("system and excitation parameters are required in simulation mode.")

            duration_sec = int(self.exc.duration)
            hours, rem = divmod(duration_sec, 3600)
            minutes, seconds = divmod(rem, 60)

            # Get base datetime once
            start_dt = datetime.now()
            stop_dt  = start_dt + timedelta(seconds = self.exc.duration)

            self.start_date  = start_dt.strftime("%d %b %Y")
            self.start_time  = start_dt.strftime("%H:%M:%S")
            self.stop_date   = stop_dt.strftime("%d %b %Y")
            self.stop_time   = stop_dt.strftime("%H:%M:%S")
            self.duration    = dt_time(hour = hours, minute = minutes, second = seconds).strftime("%H:%M:%S")

        else:
            self.start_date = None
            self.start_time = None
            self.stop_date  = None
            self.stop_time  = None
            self.duration   = None

#-------------------------------------------------------------------------------
    def extract_signals(self, file_path_txt):
        with open(file_path_txt, "r") as f:
            lines = f.readlines()

        start_date, start_time, stop_date, stop_time = None, None, None, None
        data_start_idx = None
        data_lines = []

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Basic time metadata
            if line.startswith("Start Date"):
                start_date = line.split(":", 1)[1].strip()
            elif line.startswith("Start Time"):
                start_time = line.split(":", 1)[1].strip()
            elif line.startswith("Stop Date"):
                stop_date = line.split(":", 1)[1].strip()
            elif line.startswith("Stop Time"):
                stop_time = line.split(":", 1)[1].strip()

            # Data start line
            elif line.startswith("Chn("):
                data_start_idx = idx + 1
                break

        # Parse timestamp
        try:
            dt_start = datetime.strptime(f"{start_date} {start_time}", "%d %b %Y %H:%M:%S")
            dt_stop  = datetime.strptime(f"{stop_date} {stop_time}", "%d %b %Y %H:%M:%S")
            duration_sec = int((dt_stop - dt_start).total_seconds())
            # duration_sec = int(self.exc.duration)
            hours, rem = divmod(duration_sec, 3600)
            minutes, seconds = divmod(rem, 60)
            duration_hms = dt_time(hour = hours, minute = minutes, second = seconds).strftime("%H:%M:%S")
        except Exception as e:
            raise ValueError(f"[ERROR] Could not parse duration from header: {e}")

        self.duration   = duration_hms    
        self.start_date = start_date
        self.start_time = start_time
        self.stop_date  = stop_date
        self.stop_time  = stop_time
        
        # Parse data section
        for line in lines[data_start_idx:]:
            line = line.strip()
            if line:
                values = [int(v.strip()) for v in line.split(",")]
                data_lines.append(values)

        # Full array: shape = (n_samples, n_channels)
        full_data = np.array(data_lines, dtype = np.int16)

        # Extract input/output
        self.input_signals = full_data[:, 0]                     # 1D array: (n_samples,)
        self.output_signals = full_data[:, 1:].T                 # 2D array: (n_channels - 1, n_samples)

        timestamp = dt_start.strftime("%y%m%d_%H%M%S")
        filename_npz = os.path.join(self.data_path, f"tf_{timestamp}.npz")
            
        self.save_signal_to_npz(filename_npz, timestamp)
        self.process_npz_data()
    
#-------------------------------------------------------------------------------
    def save_signal_to_npz(self, filename_npz, timestamp):
        # Prepare metadata
        user_meta           = UserMeta(self.config_path)
        user_info_block     = user_meta.get_user_info_block()
        data_info_block     = self.get_data_info_block()
        input_info_block    = self.get_input_info_block()
        tf_info_block       = self.get_tf_info_block()
        process_info_block  = self.process_info_block()
        analysis_info_block = self.analysis_info_block()
    
        # Save binary .npz
        np.savez_compressed(filename_npz,
            timestamp           = timestamp,
            user_info_block     = user_info_block,
            data_info_block     = data_info_block,
            input_info_block    = input_info_block,
            tf_info_block       = tf_info_block,
            process_info_block  = process_info_block,
            analysis_info_block = analysis_info_block,
            input_signals       = self.input_signals,
            output_signals      = self.output_signals,
        )
        
        self.filename_npz = filename_npz
        print(f"[INFO] Saved npz file: {os.path.basename(filename_npz)}")

#-------------------------------------------------------------------------------
    def process_npz_data(self, filename = None, export = False):
        if filename is None:
            filename_npz = self.filename_npz
        else:
            filename_npz = filename
            
        # Read the NPZ file to process
        data = np.load(filename_npz, allow_pickle = True)

        timestamp = data.get('timestamp')
        user_info_block = data.get('user_info_block', "User Information: N/A").item()
        data_info_block = data['data_info_block'].item()
        input_info_block= data['input_info_block'].item()
        tf_info_block   = data['tf_info_block'].item()
        process_info_block = data['process_info_block'].item()

        # Update post info
        process_info_block['Processed On'] = datetime.now().strftime("%d %b %Y, %H:%M:%S") 
        process_info_block['Input File']   = os.path.basename(filename_npz)

        analysis_info_block = data['analysis_info_block'].item()
        
        freq_start   = analysis_info_block['freq_start']
        freq_stop    = analysis_info_block['freq_stop']
        sample_rate  = analysis_info_block['sample_rate']
        natural_freq = analysis_info_block['natural_freq']
        analysis_type   = analysis_info_block['analysis_type']
        analysis_method = analysis_info_block['analysis_method']

        input  = data['input_signals']
        output = data['output_signals']

        # Full FFT
        n_fft  = len(input)
        fft_input  = np.fft.rfft(input,  n = n_fft)
        fft_output = np.fft.rfft(output, n = n_fft, axis = 1)

        # Identify index range for [f_start, f_stop]
        freqs     = np.fft.rfftfreq(n_fft, d = 1/sample_rate)
        idx_start = np.searchsorted(freqs, freq_start)
        idx_stop  = np.searchsorted(freqs, freq_stop)

        # Slice only useful region
        tf_freqs = []
        tf_vals  = []
        tf_table = []

        tf_freqs   = freqs[idx_start:idx_stop]
        amp_input  = np.abs(fft_input[idx_start:idx_stop])      # shape (N,)
        amp_output = np.abs(fft_output[:, idx_start:idx_stop])  # shape (n_channels, N)

        tf_vals = amp_output / np.maximum(amp_input[None, :], 1e-12)   # shape (n_channels, N)

        tf_freqs = np.array(tf_freqs)
        tf_vals  = np.array(tf_vals)
        tf_table = np.array(tf_table)
        
        # Assemble columns
        cols = [tf_freqs, amp_input]
        for i in range(amp_output.shape[0]):
            cols.append(amp_output[i])
        for i in range(tf_vals.shape[0]):
            cols.append(tf_vals[i])

        # Transpose and zip to row-wise structure
        tf_table = list(zip(*cols))  # Each row: [Freq, Ch1, Ch2, ..., TF(2/1), TF(3/1), ...]
        
        # Save data in text or csv format
        if export:
            txt_name = os.path.join(self.data_path, f"tf_{timestamp}.txt")
            csv_name = os.path.join(self.data_path, f"tf_{timestamp}.csv")
            self.save_to_text_csv(txt_name, user_info_block, data_info_block,
                                    input_info_block, tf_info_block, process_info_block, 
                                    tf_table, csv_mode = False)

            self.save_to_text_csv(csv_name, user_info_block, data_info_block,
                                    input_info_block, tf_info_block, process_info_block, 
                                    tf_table, csv_mode = True)
            print(f"[INFO] Processed file: {os.path.basename(filename_npz)} for CSV and Text mode")
            return
        
        pdf_name = os.path.join(self.data_path, f"tf_{timestamp}.pdf")
        self.save_to_pdf_sceen(pdf_name, data_info_block, input_info_block, tf_info_block,
                             process_info_block, tf_freqs, tf_vals, analysis_type)

        print(f"[INFO] Processed file: {os.path.basename(filename_npz)}")

#-------------------------------------------------------------------------------
    def save_to_text_csv(self, file_name, user_info_block, data_info_block, 
                                input_info_block, tf_info_block, process_info_block, 
                                tf_table, csv_mode = False):
        data_info_block = self.format_data_info_metadata(data_info_block)                                
        # based on csv_mode, it will save in text mode or csv mode
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write(user_info_block + "\n")
            write_metadata_header(f, "Data Capture Information", data_info_block)
            write_metadata_header(f, "Input Signal Information", input_info_block)
            write_metadata_header(f, "System Model Information", tf_info_block)
            write_metadata_header(f, "Processing Information",   process_info_block)
            write_channel_metadata_block(f, csv_mode)
            
            n_cols = len(tf_table[0])      # Total columns: 1 freq + 1 input + M outputs + M TFs
            m = (n_cols - 2) // 2          # Number of receiver channels
            headers = ["Freq", "Chn(1)"]                    # Reference channel
            headers += [f"Chn({i+2})" for i in range(m)]    # Receiver channels (Ch2, Ch3, ...)
            headers += [f"Ch{i+2}/Ch1" for i in range(m)]   # TF columns (TF(Ch2/Ch1), ...)

            write_table_block(f, tf_table, headers, csv_mode)

        print(f"[INFO] Saved txt file: {os.path.basename(file_name)}")

#-------------------------------------------------------------------------------
    def save_to_pdf_sceen(self, file_name, data_block, input_block, tf_block, 
                            process_block, tf_freqs, tf_vals, analysis_type):

        xlabel = 'Frequency (Hz)'
        ylabel = TFParams.get_y_axis_label(analysis_type, self.use_db)
        if self.use_db:
            tf_vals = 20 * np.log10(tf_vals + 1e-12)  # Avoid log(0)

        # ProductMeta.configure('VibMScope')  # or 'VibrationAnalyser', 'VibMScope', 'VibMTool'
        product_name = ProductMeta.get_title()

        # screen should be before pdf, otherwise, pdf property are distrubing the screen
        self.plot_tf_screen(product_name, tf_freqs, tf_vals, xlabel, ylabel, analysis_type)

        self.save_tf_pdf(file_name, product_name, data_block, input_block, tf_block, process_block, 
                        tf_freqs, tf_vals, xlabel, ylabel, analysis_type)
        
#-------------------------------------------------------------------------------
    def save_tf_pdf(self, file_name, product_name, data_info_block, input_info_block, tf_info_block, process_info_block, 
                    tf_freqs, tf_vals, xlabel, ylabel, analysis_type):

        os.makedirs(os.path.dirname(file_name), exist_ok = True)

        fig_pdf, (ax_logo, ax_plot, ax_text) = plt.subplots(nrows = 3, ncols = 1,
            figsize = (8.27, 11.69),        # A4 Paper Size
            height_ratios = [0.25, 3.25, 2.5],  # vertical division of space in three plots
            gridspec_kw = {
                'top':    0.97,
                'bottom': 0.05,
                'left':   0.13,
                'right':  0.92,
                'hspace': 0.15,             # vertical spacing between plots
            }
        )

        # Logo Area block
        self.insert_product_logo(ax_logo, product_name)

        # Plot Area block
        self.insert_plot_ax_pdf(ax_plot, tf_freqs, tf_vals, xlabel, ylabel, analysis_type)

        # Metadata block
        ax_text.axis("off")  # Remove all ticks and lines
        
        data_info_block = self.format_data_info_metadata(data_info_block)
        
        y_cursor = 0.98 # y axis start point
        line_spacing = 0.030
        for label, meta in [("Data Capture Information", data_info_block),
                            ("System Model Information", input_info_block),
                            ("Input Signal Information", tf_info_block),
                            ("Processing Information", process_info_block)]:
            ax_text.text(0.0, y_cursor, "-" * 80, fontsize=8, family='monospace', transform=ax_text.transAxes)
            y_cursor -= line_spacing
            ax_text.text(0.0, y_cursor, label, fontsize=10, fontweight="bold", transform=ax_text.transAxes)
            y_cursor -= line_spacing
            ax_text.text(0.0, y_cursor, "-" * 80, fontsize=8, family='monospace', transform=ax_text.transAxes)
            y_cursor -= line_spacing
            for key, val in meta.items():
                ax_text.text(0.01, y_cursor, f"{key:<18}: {val}", fontsize=9, family='monospace', transform=ax_text.transAxes)
                y_cursor -= line_spacing
            y_cursor -= 0.00 # keep placeholder for adjustment

        fig_pdf.set_snap(True)
        fig_pdf.savefig(file_name, dpi = 150)
        plt.close(fig_pdf)
        print(f"[INFO] Saved pdf file: {os.path.basename(file_name)}")

#-------------------------------------------------------------------------------
    def plot_tf_screen(self, product_name, tf_freqs, tf_vals, xlabel, ylabel, analysis_type):
        from matplotlib.figure import Figure
        width  = self.display_config['width_in']
        height = self.display_config['height_in']
        dpi = self.display_config.get('dpi', 144)

        fig_screen, ax_plot = plt.subplots(nrows = 1, ncols = 1, dpi = dpi,
            figsize = (width, height), # Screen Size
            gridspec_kw={
                'top':    0.90,
                'bottom': 0.10,
                'left':   0.08,
                'right':  0.92,
            }        
        )

        product_icon = ProductMeta.get_icon()
        fig_screen.canvas.manager.set_window_title(product_name)
        fig_screen.canvas.manager.window.iconbitmap(product_icon)
        self.insert_plot_ax_screen(ax_plot, tf_freqs, tf_vals, xlabel, ylabel, analysis_type)
        fig_screen.canvas.manager.window.state('zoomed')
        fig_screen.set_snap(True)

        if len(plt.get_fignums()) == 1:
            plt.show()  # Only one figure: safe to block
        else:
            fig_screen.canvas.mpl_connect('close_event', self.on_tf_close)
            fig_screen.show()  # Direct non-blocking show on the figure object

#-------------------------------------------------------------------------------
    def on_tf_close(self, event):
        update_status_bar("TF", remove = True)
    
#-------------------------------------------------------------------------------
    def insert_plot_ax_pdf(self, ax_plot, tf_freqs, tf_vals, xlabel, ylabel, analysis_type):

        legend_map = {}
        linestyles = ['-', '--', '-.', ':', (0, (3, 1, 1, 1)), (0, (5, 2, 2, 2)), (0, (1, 1)), (0, (2, 1))]  # Extended to support 8

        for i in range(tf_vals.shape[0]):
            ch_id = i + 2  # Receiver channel index
            linestyle = linestyles[i % len(linestyles)]
            line, = ax_plot.plot(tf_freqs, tf_vals[i], linestyle = linestyle, linewidth = 1.0, label = f"TF(Ch{ch_id}/Ch1)")
            legend_map[i] = line.get_color()

        ax_plot.tick_params(axis='both', which='major', labelsize = 10)
        ax_plot.tick_params(axis='both', which='minor', labelsize = 6)
        ax_plot.grid(which='major', linestyle = '-',  linewidth = 0.7, alpha = 0.9, color = 'black')
        ax_plot.grid(which='minor', linestyle = '--', linewidth = 0.4, alpha = 0.5, color = 'gray')
        set_clean_axis_ticks_labels(ax_plot, (np.min(tf_freqs), np.max(tf_freqs)), axis = 'x', num_ticks = 5,  step_hint = 20, num_minor = 4)
        set_clean_axis_ticks_labels(ax_plot, (np.min(tf_vals),  np.max(tf_vals)),  axis = 'y', num_ticks = 10)
        
        # Labels & Title
        plot_title = TFParams.get_plot_title(analysis_type)
        ax_plot.set_xlabel(xlabel, fontsize = 11, fontweight = "bold", family = 'Segoe UI')
        ax_plot.set_ylabel(ylabel, fontsize = 11, fontweight = "bold", family = 'Segoe UI')
        ax_plot.set_title(plot_title, fontsize = 13, fontweight = "bold", family = 'Segoe UI')
        
        # Info box
        metrics_list = self.compute_summary_metrics(tf_freqs, tf_vals)

        y_cursor = 0.99
        text_color_info = 'black'  # default text color
        linestyles_map = ['-', '--', '-.', ':', 'dashdot', 'loosely dashdotted', 'densely dotted', 'loosely dotted']
        for i, (f_resonant, t_rmax, f_iso, f_natural, t_nvalue, damping_ratio, order) in enumerate(metrics_list):
            ch_id = i + 2
            color = legend_map[i]
            linestyle_desc = linestyles_map[i % len(linestyles_map)]

            iso_text     = f'{f_iso:5.2f} Hz'      if f_iso is not None else '--'
            order_text   = f'{order:5.2f}'         if order is not None else '--'
            damping_text = f'{damping_ratio:5.2f}' if damping_ratio is not None else '--'
            natural_text = f'{f_natural:5.2f} Hz'  if f_natural is not None else '--'
            nvalue_text  = f'{t_nvalue:5.2f}'      if t_nvalue is not None else '--'
            expanded_style = self.style_preview(linestyle_desc)

            lines = [
                f"{' Transmissibility :':<20}{f'Ch{ch_id}/Ch1':<9}",
                f"{' System Order     :':<20}{order_text:<9}",
                f"{' Damping Ratio    :':<20}{damping_text:<9}",
                f"{' Natural Freq     :':<20}{natural_text:<9}",
                f"{' Peak at Natural  :':<20}{nvalue_text:<9}",
                f"{' Resonant Freq    :':<20}{f'{f_resonant:5.2f} Hz':<9}",
                f"{' Peak at Resonant :':<20}{f'{t_rmax:5.2f}':<9}",
                f"{' Isolation Begins :':<20}{iso_text:<9}",
                f"{' Line Style       :':<20}{expanded_style:<9}",
            ]

            block = "\n".join(lines)

            ax_plot.text(
                0.99, y_cursor, block,
                transform = ax_plot.transAxes,
                verticalalignment = 'top', horizontalalignment = 'right',
                bbox = dict(
                    edgecolor = color,          # plot-matching boundary
                    facecolor = 'white',
                    boxstyle  = 'round, pad = 0.2',
                ),
                fontsize = 6, family = 'DejaVu Sans Mono',
                color = text_color_info         # default text color
            )
            y_cursor -= 0.18
                     
#-------------------------------------------------------------------------------
    def insert_plot_ax_screen(self, ax_plot, tf_freqs, tf_vals, xlabel, ylabel, analysis_type):
        title_size = 12
        label_size = 10
        major_tick_size = 8
        minor_tick_size = 6
        text_font_size  = 6

        linestyles = ['-', '--', '-.', ':', (0, (3, 1, 1, 1)), (0, (5, 2, 2, 2)), (0, (1, 1)), (0, (2, 1))]  # Extended to support 8

        # Plot each TF curve with auto line style
        for i in range(tf_vals.shape[0]):
            ch_id = i + 2
            linestyle = linestyles[i % len(linestyles)]
            ax_plot.plot(tf_freqs, tf_vals[i], linestyle = linestyle, linewidth = 1.0, label = f"TF(Ch{ch_id}/Ch1)")

        # Axis settings
        ax_plot.tick_params(axis='both', which='major', labelsize=major_tick_size)
        ax_plot.tick_params(axis='both', which='minor', labelsize=minor_tick_size)
        ax_plot.grid(which='major', linestyle='-',  linewidth=0.7, alpha=0.9, color='black')
        ax_plot.grid(which='minor', linestyle='--', linewidth=0.4, alpha=0.5, color='gray')

        set_clean_axis_ticks_labels(ax_plot, (np.min(tf_freqs), np.max(tf_freqs)), axis='x', num_ticks=5, step_hint=20, num_minor=4)
        set_clean_axis_ticks_labels(ax_plot, (np.min(tf_vals),  np.max(tf_vals)),  axis='y', num_ticks=10)

        # Labels and title
        plot_title = TFParams.get_plot_title(analysis_type)
        ax_plot.set_xlabel(xlabel, fontsize=label_size, fontweight="bold", family='Segoe UI')
        ax_plot.set_ylabel(ylabel, fontsize=label_size, fontweight="bold", family='Segoe UI')
        ax_plot.set_title(plot_title, fontsize=title_size, fontweight="bold", family='Segoe UI')

        # Metrics summary box (single combined block)
        metrics_list = self.compute_summary_metrics(tf_freqs, tf_vals)
        # dpi    = self.display_config["dpi"]
        # height = self.display_config["height_in"]

        # Build full summary text block
        text_blocks = []
        linestyles_map = ['-', '--', '-.', ':', 'dashdot', 'loosely dashdotted', 'densely dotted', 'loosely dotted']

        for i, (f_resonant, t_rmax, f_iso, f_natural, t_nvalue, damping_ratio, order) in enumerate(metrics_list):
            ch_id = i + 2
            linestyle_desc = linestyles_map[i % len(linestyles_map)]

            iso_text     = f'{f_iso:5.2f} Hz'      if f_iso is not None else '--'
            order_text   = f'{order:5.2f}'         if order is not None else '--'
            damping_text = f'{damping_ratio:5.2f}' if damping_ratio is not None else '--'
            natural_text = f'{f_natural:5.2f} Hz'  if f_natural is not None else '--'
            nvalue_text  = f'{t_nvalue:5.2f}'      if t_nvalue is not None else '--'
            expanded_style = self.style_preview(linestyle_desc)

            lines = [
                f"{' Transmissibility :':<20}{f'Ch{ch_id}/Ch1':<9}",
                f"{' System Order     :':<20}{order_text:<9}",
                f"{' Damping Ratio    :':<20}{damping_text:<9}",
                f"{' Natural Freq     :':<20}{natural_text:<9}",
                f"{' Peak at Natural  :':<20}{nvalue_text:<9}",
                f"{' Resonant Freq    :':<20}{f'{f_resonant:5.2f} Hz':<9}",
                f"{' Peak at Resonant :':<20}{f'{t_rmax:5.2f}':<9}",
                f"{' Isolation Begins :':<20}{iso_text:<9}",
                f"{' Line Style       :':<20}{expanded_style:<9}",
                ""
            ]
            text_blocks.extend(lines)

        summary_block = "\n".join(text_blocks).rstrip("\n")

        # Draw single combined box
        ax_plot.text(
            0.995, 0.99, summary_block,
            transform = ax_plot.transAxes,
            verticalalignment = 'top', horizontalalignment = 'right',
            bbox=dict(
                edgecolor = 'red',
                facecolor = 'white',
                boxstyle  = 'round, pad = 0.2',
                linewidth = 0.8,    # Border thickness (default is 1.0)
            ),
            color = 'black',
            fontsize = text_font_size, family='DejaVu Sans Mono'
        )

#-------------------------------------------------------------------------------
    def style_preview(self, style):
        style_map = {
            '-':  '────────',
            '--': '--------',
            '-.': '-.-.-.-.',
            ':':  '········'
        }
        return style_map.get(style, str(style) * 4)  # fallback if not found

#-------------------------------------------------------------------------------
    def estimate_system_order(self, tf_freqs, tf_vals,
                              min_prominence   = 0.1,
                              min_height_ratio = 1.2,
                              min_peak_distance= 5):
        """
        Estimate system order from TF data using peak-counting.

        Parameters:
            tf_freqs          : 1D array of frequency values
            tf_vals           : 1D array of TF magnitudes (linear or dB)
            min_prominence    : Minimum peak prominence
            min_height_ratio  : Minimum peak height / median
            min_peak_distance : Minimum spacing between peaks (in index)

        Returns:
            estimated_order (int) = 2 × number of valid peaks (minimum 1)
        """
        from scipy.signal import find_peaks
        # Convert to linear scale if needed
        values = tf_vals if not self.use_db else 10 ** (tf_vals / 20)

        # Height threshold to avoid noise floor peaks
        threshold = np.median(values) * min_height_ratio

        # Auto-set prominence if None
        if min_prominence is None:
            noise_floor = np.percentile(values, 20)
            signal_peak = np.max(values)
            min_prominence = max((signal_peak - noise_floor) * 0.2, 1e-6)

        # Find valid peaks
        peaks, _ = find_peaks(values,
                              height = threshold,
                              prominence = min_prominence,
                              distance = min_peak_distance)

        num_resonances = len(peaks)
        return max(2 * num_resonances, 1)  # Ensure minimum order = 1

#-------------------------------------------------------------------------------
    def second_order_mag(self, f, omega_n, zeta):
        """Magnitude response of second-order system |H(jω)|"""
        omega = 2 * np.pi * f  # Convert Hz to rad/s
        num = omega_n**2
        den = np.sqrt((omega_n**2 - omega**2)**2 + (2*zeta*omega_n*omega)**2)
        return num / den

#-------------------------------------------------------------------------------
    def find_sys_parameters(self, freqs, tf_mag, initial_guess = (10.0, 0.2)):
        """
        Fit a 2nd-order transfer function magnitude model to TF data.

        Parameters:
            freqs      : 1D array of frequency (Hz)
            tf_mag     : 1D array of TF magnitude (linear, not dB)
            initial_guess : (omega_n, zeta) initial values for fitting

        Returns:
            zeta         : Estimated damping ratio
            omega_n_hz   : Estimated natural frequency in Hz
            fit_curve    : TF curve from fitted model (for plotting)
        """
        from scipy.optimize import curve_fit
        
        if self.use_db:
            tf_mag = 10 ** (tf_mag / 20)

        try:
            order = self.estimate_system_order(freqs, tf_mag)
            
            popt, _ = curve_fit(self.second_order_mag, freqs, tf_mag, p0 = initial_guess, maxfev = 5000)

            omega_n, zeta = popt
            # fit_curve = self.second_order_mag(freqs, omega_n, zeta)
            f_natural = omega_n / (2 * np.pi)
            t_nvalue = 1 / (2 * zeta)            
            return zeta, f_natural, t_nvalue, order

        except Exception as e:
            print(f"[fit_2nd_order_tf] Fit failed: {e}")
            return None, None, None, None

#-------------------------------------------------------------------------------
    def compute_summary_metrics(self, tf_freqs, tf_vals):
        """
        Compute per-receiver summary metrics from TF curves.
        Supports tf_vals shape: (n_receivers, n_freqs)
        and natural_freqs: List[float] with len == n_receivers
        """
        results = []

        for i in range(tf_vals.shape[0]):
            tf = tf_vals[i]

            # Peak (resonance)
            idx_max    = np.argmax(tf)
            f_resonant = tf_freqs[idx_max]
            t_rmax     = tf[idx_max]

            # Isolation start frequency (sub-resonant cutoff)
            if self.use_db:
                idx_iso = np.where(tf < 0)[0]
            else:
                idx_iso = np.where(tf < 1.0)[0]

            f_iso = tf_freqs[idx_iso[0]] if idx_iso.size > 0 else None

            # Value at natural frequency
            if get_sys_value('simulation_mode'):
                f_natural = self.sys.natural_freq[i]
                idx       = np.argmin(np.abs(tf_freqs - f_natural))
                t_nvalue  = tf[idx]
                damping_ratio = self.sys.damping_ratio[i]
                order     = self.sys.order[i]
                
            else:
                damping_ratio, f_natural, t_nvalue, order = self.find_sys_parameters(tf_freqs, tf, initial_guess = (15, 0.2))

                self.sys.order[i] = order               
                self.sys.natural_freq[i] = f_natural
                self.sys.damping_ratio[i] = damping_ratio
                             
            # Store all relevant values (double () are needed here)
            results.append((f_resonant, t_rmax, f_iso, f_natural, t_nvalue, damping_ratio, order))

        return results  # List of tuples

#-------------------------------------------------------------------------------
    def insert_product_logo(self, ax_logo, product_name):
        # Metadata logo block ( GeoSystem V1.0)
        ax_logo.axis("off")  # Remove all ticks and lines
        product_logo = ProductMeta.get_icon()
        logo_img = imread(product_logo)  # Must be PNG or JPG
        # -- Create image box with fixed zoom
        imagebox = OffsetImage(logo_img, zoom = 0.50)  # Tune zoom to match text height
        ab = AnnotationBbox(imagebox, (0.0, 1.0),
                            xybox=(0, 0),  # Offset in pixels
                            xycoords ='axes fraction',
                            boxcoords ="offset points",
                            frameon = False,
                            box_alignment =(0, 1))  # Top-left
        ax_logo.add_artist(ab)
        # -- Add product text at top-right
        ax_logo.text(1.0, 1.0, f"{product_name}", weight='bold',
                    fontsize=16, va='top', ha='right', transform=ax_logo.transAxes)

        # -- Add second line below
        ax_logo.text(1.0, 0.30, "MAPS Technologies",
                    fontsize=12, va='top', ha='right', transform=ax_logo.transAxes)        

#-------------------------------------------------------------------------------
    def format_data_info_metadata(self, meta):
        formatted = {}

        # Step 1: Pre-merged passthrough keys (appear first)
        pre_keys = [
            "Serial Number",
            "No of Channels",
            "Sampling Rate"
        ]

        # Step 2: Merged entries
        merged_entries = {
            "Notch Filter/Freq": f"{meta['Notch Filter']} @ {meta['Notch Freq']}",
            "Start Date/Time":   f"{meta['Start Date']} {meta['Start Time']}",
            "Stop Date/Time":    f"{meta['Stop Date']} {meta['Stop Time']}",
        }

        # Step 3: Post-merged passthrough keys (appear after)
        post_keys = [
            "Captured Duration",
            "Ref Channel"
        ]

        # Add pre keys
        for key in pre_keys:
            if key in meta:
                formatted[key] = meta[key]

        # Add merged keys
        formatted.update(merged_entries)

        # Add post keys
        for key in post_keys:
            if key in meta:
                formatted[key] = meta[key]

        return formatted

#-------------------------------------------------------------------------------
    def get_data_info_block(self) -> dict:
        # Merge and return
        # return {**system_info, **tf_info}
        
        if get_sys_value('notch_enable'):
            notch = 'Enabled'
            notch_freq = 50.0
        else:
            notch = 'Disabled'
            notch_freq = 'N/A'

        return {
            "Serial Number":  get_sys_value("sys_ser_no"),
            "No of Channels": get_sys_value('adc_channels'),
            "Sampling Rate":  get_sys_value('adc_srate'),
            "Notch Filter":   notch,
            "Notch Freq":     notch_freq,
            "Start Date":     self.start_date,
            "Start Time":     self.start_time,
            "Stop Date":      self.stop_date,
            "Stop Time":      self.stop_time,
            "Duration":       self.duration,
            "Ref Channel":    "Channel 1",       
        }

#-------------------------------------------------------------------------------
    def get_input_info_block(self) -> dict:
        if get_sys_value('simulation_mode'):
            signal_info = {
                'Signal Source':"Simulation",
                'Signal Type':  f"{self.exc.type}",
                'Freq Start':   f"{self.exc.freq_start} Hz",
                'Freq Stop':    f"{self.exc.freq_stop} Hz",
            }
        else:
            signal_info = {
                'Signal Source':"Live Acquisition",
                'Signal Type':  "N/A",
                'Freq Start':   "User-Defined",
                'Freq Stop':    "User-Defined",
            }

        return signal_info

#-------------------------------------------------------------------------------
    def get_tf_info_block(self) -> dict:
        if get_sys_value('simulation_mode'):
            system_info = {
                'System Order': f"{self.sys.order}",
                'Damping Ratio':f"{self.sys.damping_ratio}",
                'Natural Freq': f"{self.sys.natural_freq} Hz",
            }
        else:
            system_info = {
                'System Order': f"{self.sys.order} (Estimated)",
                'Damping Ratio':f"{self.sys.damping_ratio} (Estimated)",
                'Natural Freq': f"{self.sys.natural_freq} Hz (Estimated)",
            }
    
        return system_info

#-------------------------------------------------------------------------------
    def process_info_block(self) -> dict:
        raw_len = len(self.input_signals)
        n_fft   = 2 ** int(np.floor(np.log2(raw_len)))

        start = self.exc.freq_start
        end   = self.exc.freq_stop

        process_info_block = {
            "Processed On": "",
            "Input File":   "",

            "FFT Config": f"{get_sys_value('window')}, {n_fft} samples",
            "Digital Filter": format_filter_description(),
            "Analysis Freq":  f"{start:.1f} Hz - {end:.1f} Hz",

            "Analysis": f"{TFParams.get_analysis_type_desc(self.analysis_type)} "
                        f"({TFParams.get_analysis_method_desc(self.analysis_method)})",

            "Tool Version": ProductMeta.get_version()
        }
        return process_info_block

#-------------------------------------------------------------------------------
    def analysis_info_block(self) -> dict:
        if get_sys_value('simulation_mode'):
            analysis_info_block = {
                'freq_start':       self.exc.freq_start,
                'freq_stop':        self.exc.freq_stop,
                'sample_rate':      self.sample_rate,
                'natural_freq':     self.sys.natural_freq,
                'analysis_type':    self.analysis_type,
                'analysis_method':  self.analysis_method,                
            }
        else:
            analysis_info_block = {
                'freq_start':   PlotParams.fftXParams['min_hz'],
                'freq_stop':    PlotParams.fftXParams['max_hz'],
                'sample_rate':  self.sample_rate,
                'natural_freq': "N/A",
                'analysis_type':    self.analysis_type,
                'analysis_method':  self.analysis_method,                
            }

        return analysis_info_block 

#-------------------------------------------------------------------------------
# Class definitions: ExcitationParams, SystemParams, etc.
#-------------------------------------------------------------------------------
def create_tf_parameters(simulation: bool, n_receivers: int = 1):
    # Helper function for unified TF parameter setup
    if simulation:
        excitation = ExcitationParams(
            type = 'Chirp', freq_start = 1.0, freq_stop = 100.0,
            duration = 32.0, amplitude = 1.0, noise_stddev = 0.0
        )

        base_freq    = 10.0  # Hz
        base_damping = 0.37

        # Introduce small variations
        freq_list = [base_freq +    ((i - n_receivers // 2) * 2.0) for i in range(n_receivers)]
        damp_list = [base_damping + ((i - n_receivers // 2) * 0.015) for i in range(n_receivers)]

        # Clamp damping to 0.2 – 0.6 range if needed
        damp_list = [min(max(d, 0.2), 0.8) for d in damp_list]

        system = SystemParams(
            order = [2] * n_receivers,
            natural_freq = freq_list,
            damping_ratio = damp_list,
            n_receivers = n_receivers
        )

    else:
        excitation = ExcitationParams()
        system     = SystemParams(n_receivers = n_receivers)

    return system, excitation

#-------------------------------------------------------------------------------
class SystemParams:
    def __init__(self, order = 2, natural_freq = 16.0, damping_ratio = 0.4, n_receivers = 1):
        # Handle scalar or per-receiver order
        if isinstance(order, (int, float)):
            self.order = [int(order)] * n_receivers
        else:
            self.order = [int(o) for o in order]

        # Handle natural frequency
        if isinstance(natural_freq, (int, float)):
            self.natural_freq = [natural_freq] * n_receivers
        else:
            self.natural_freq = list(natural_freq)

        # Handle damping ratio
        if isinstance(damping_ratio, (int, float)):
            self.damping_ratio = [damping_ratio] * n_receivers
        else:
            self.damping_ratio = list(damping_ratio)

        # Validation
        if not all(len(lst) == n_receivers for lst in [self.order, self.natural_freq, self.damping_ratio]):
            raise ValueError("All system parameter lists must match n_receivers.")

#-------------------------------------------------------------------------------
class ExcitationParams:
    def __init__(self, type = 'Chirp', freq_start = 1.0, freq_stop = 100.0,
                 duration = 60.0, amplitude = 1.0, noise_stddev = 0.0):
        self.type = type
        self.freq_start = freq_start
        self.freq_stop  = freq_stop
        self.duration   = duration
        self.amplitude  = amplitude
        self.noise_stddev = noise_stddev

#-------------------------------------------------------------------------------
class SimulatorTF:
    def __init__(self, system = None, excitation = None, tf = None):
        self.sys = system
        self.exc = excitation
        
        self.order = self.sys.order
        
        self.sample_rate   = get_sys_value('adc_srate')
        self.analysis_type = get_sys_value('analysis_type')
        self.tf_handler = tf
        
#-------------------------------------------------------------------------------
    def compute_tf(self, freq, order, f_n, zeta):
        """Calculate transmissibility of system at frequency freq."""
        r = freq / f_n
        if order == 2:
            if self.analysis_type == 'DT':      # displacement transmissibility
                return 1 / np.sqrt((1 - r**2)**2 + (2 * zeta * r)**2) # amplitude
            elif self.analysis_type == 'FT':    # force transmissibility
                #Frequency Response of Mass-Damper-Spring Systems
                num = 1 + (2 * zeta * r)**2
                den = (1 - r**2)**2 + (2 * zeta * r)**2
                return np.sqrt(num / den)
            else:
                raise ValueError(f"Invalid analysis_type: {self.analysis_type}")

        elif order == 1:
            return 1 / np.sqrt(1 + (r / zeta)**2)

        raise ValueError(f"Unsupported system order: {order}")

#-------------------------------------------------------------------------------
    def simulate_time_data(self):
        f_start  = self.exc.freq_start
        f_stop   = self.exc.freq_stop
        duration = self.exc.duration
        stddev   = self.exc.noise_stddev
        noise_enabled = self.exc.noise_stddev > 0

        t = np.linspace(0, duration, int(self.sample_rate * duration), endpoint = False)
        
        # Generate linear chirp as input (uncontrolled sweep)
        from scipy.signal import chirp
        input_signal = chirp(t, f0 = f_start, f1 = f_stop, t1 = duration, method = 'linear')

        # Trim to power-of-2 for fast FFT
        n_fft = 2 ** int(np.floor(np.log2(len(input_signal))))
        self.tf_handler.input_signals = np.array(input_signal[:n_fft])

        # Create one output per receiver
        n_receivers = len(self.sys.natural_freq)
        output_signals = []

        for i in range(n_receivers):
            order_i = self.sys.order[i]
            f_n_i = self.sys.natural_freq[i]
            zeta_i = self.sys.damping_ratio[i]

            tf_vector = []
            for f in np.linspace(f_start, f_stop, n_fft):
                tf = self.compute_tf(f, order_i, f_n_i, zeta_i)
                tf_vector.append(tf)

            tf_vector = np.array(tf_vector)

            output = input_signal * tf_vector
            if noise_enabled:
                output += np.random.normal(0, stddev, size = output.shape)

            output_signals.append(output)

        self.tf_handler.output_signals = np.array(output_signals)  # shape: (n_receivers, n_fft)

        print("[INFO] Sweep completed. Length of Sweep:", n_fft)

#-------------------------------------------------------------------------------
if __name__ == '__main__':
    from common.utils.display_helpers import get_display_context
    from common.core.path_manager import PathManager
    from common.core.sys_config   import sys_config_init
    # Define project-relative folders to be added to sys.path
    USEFUL_FOLDERS = [
        'common/core',
        'common/utils',
        'common/modules',
        # Add more here as needed
    ]

    path_mgr = PathManager(__file__, USEFUL_FOLDERS)
    sys_config_init(path_mgr)
    
    ProductMeta.configure('VibMScope')  # or 'VibrationAnalyser', 'VibMScope', 'VibMTool'
    display_config = get_display_context()

    # sys_config_init() # init global variables
    
    n_receivers = get_sys_value('adc_channels') - 1 # for transfer funciton
    sys, exc = create_tf_parameters(simulation = get_sys_value("simulation_mode"), n_receivers = n_receivers)

    tf  = TFProcessor(system = sys, excitation = exc, display_config = display_config)
    sim = SimulatorTF(system = sys, excitation = exc, tf = tf)

    sim.simulate_time_data()    # Generate input and output signals for TF
    
    timestamp    = datetime.now().strftime("%y%m%d_%H%M%S")
    filename_npz = os.path.join(tf.data_path, f"tf_{timestamp}.npz")
    tf.save_signal_to_npz(filename_npz, timestamp)
    tf.process_npz_data()

