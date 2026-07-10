import os
import csv
import time
import logging
import traceback
import numpy as np

#-------------------------------------------------------------------------------
# from common import get_session_flag, set_session_flag
from common.core.product_meta   import UserMeta
from common.utils.utils_helpers import get_sensor_unit 
from common.core.parameters     import PlotParams, DataHdrParams
from common.core.sys_config     import sys_config_init, get_sys_value, set_sys_value
from common.core.common         import set_session_flag, channel_to_sensor, dt_sample, dt_sample_hdr

#-------------------------------------------------------------------------------
class FileSave:
    """
    Handles file I/O for recording and event data.
    Manages file naming, metadata headers, and sample writing.
    """
#-------------------------------------------------------------------------------
    def __init__(self, hdr_handler, path_handler = None):
        self.base_path   = None
        self.hdr_handler = hdr_handler
        self.path_handler= path_handler
        self.data_path   = get_sys_value("data_path")
        self.config_path = get_sys_value("config_path")

#-------------------------------------------------------------------------------
    def set_data_path(self, path):
        """Allows setting data path manually during tests."""
        self.data_path = path

#-------------------------------------------------------------------------------
    def get_save_path(self, filename):
        if get_sys_value('record_csv'):
            return os.path.join(self.data_path, filename + ".csv")
        else:
            return os.path.join(self.data_path, filename + ".txt")

#-------------------------------------------------------------------------------
    def write_file_with_metadata(self, filename, date_str, time_str, data, event_type):
        self.write_metadata(filename, date_str, time_str, event_type)
        self.write_data(filename, data)

#-------------------------------------------------------------------------------
    def write_data(self, filename, data):
        try:
            is_count = get_sys_value('time_yspan') == 'CNT'
            dtype = np.int16 if is_count else np.float32
            fmt   = '%6d' if is_count else '%8.3f'
        
            # Always create 2D array (even for 1 channel)
            stacked = np.column_stack([np.array(ch, dtype = dtype) for ch in data])

            if get_sys_value('record_csv'):
                with open(filename, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(stacked)
                    rel_path = self.path_handler.get_relative_path(filename)
                    logging.info(f"[Data] Written to: {rel_path}")
            else:
                with open(filename, 'a', encoding='utf-8') as f:
                    for row in stacked:
                        f.write(", ".join(fmt % val for val in row) + "\n")
                
                    rel_path = self.path_handler.get_relative_path(filename)
                    logging.info(f"[Data] Written to: {rel_path}")

        except Exception as e:
            logging.error(f"Data write failed: {e}")
            logging.debug(traceback.format_exc())

#-------------------------------------------------------------------------------
    def write_metadata(self, filename, date_str, time_str, event_type = None):
        """Write formatted metadata header and channel information."""
        n_channels  = get_sys_value('adc_channels')
        sample_rate = get_sys_value('adc_srate')
        
        # Build metadata lines
        metadata = [
            '-' * 80,
            f"{'Data Capture Information'}",
            '-' * 80,
            f"{'Serial Number':<16}: {self.hdr_handler.serial_number}",
            f"{'No of Channels':<16}: {n_channels}",
            f"{'Sampling Rate':<16}: {sample_rate}"
        ]
        
        if event_type:
            metadata.append(f"{'Event Type':<16}: {event_type.upper()}")

        metadata.extend([
            f"{'Start Date':<16}: {date_str}",
            f"{'Start Time':<16}: {time_str}",
            f"{'Stop Date':<16}: {{ STOP_DATE }}",
            f"{'Stop Time':<16}: {{ STOP_TIME }}",
        ])
        
        try:
            with open(filename, 'w', encoding = 'utf-8') as f:
                # Insert user metadata block at top
                user_meta = UserMeta(config_path = self.config_path)
                f.write(user_meta.get_user_info_block() + "\n")
            
                for line in metadata:
                    f.write(line + "\n")
                
                f.write("-" * 80 + "\n")
                f.write("Sensor Information" + "\n")
                f.write("-" * 80 + "\n")

                if get_sys_value('record_csv'):
                    # Header for channel metadata
                    f.write("Channel No, Sensor Name, Unit, Description\n")
                    for ch in range(n_channels):
                        info = channel_to_sensor.get(ch, {})
                        sensor_name = info.get('name', 'unknown')
                        unit = get_sensor_unit(sensor_name)
                        desc = info.get('description', 'N/A')
                        line = f"Channel {ch+1}, {sensor_name}, {unit}, {desc}"
                        f.write(line + "\n")

                else:
                    f.write(f"Channel No -> Sensor Name -> Unit   -> Description\n")
                    for ch in range(n_channels):
                        info = channel_to_sensor.get(ch, {})
                        sensor_name = info.get('name', 'unknown')
                        unit = get_sensor_unit(sensor_name)
                        desc = info.get('description', 'N/A')
                        line = f"Channel {ch+1:<2} -> {sensor_name:<11} -> {unit:<6} -> {desc}"
                        f.write(line + "\n")

                f.write("-" * 80 + "\n")
                f.write("Channel Data" + "\n")
                f.write("-" * 80 + "\n")
                header_line = ", ".join([f"Chn({ch+1})" for ch in range(n_channels)])
                f.write(header_line + "\n")

        except Exception as e:
            logging.error(f"Metadata write failed: {e}")
            logging.debug(traceback.format_exc())

#-------------------------------------------------------------------------------
    def save_event_data(self, filename, t_ydata, start_time, event_type):
        """Save centre of time window from t_ydata when an event is detected."""
        try:
            sample_range = PlotParams.get_event_sample_slice()
            data = [list(ch)[sample_range] for ch in t_ydata]
            _, date_str, time_str = self.hdr_handler.get_time_string(start_time)
            filename = self.get_save_path(filename)
            self.write_file_with_metadata(filename, date_str, time_str, data, event_type)
            rel_path = self.path_handler.get_relative_path(filename)
            logging.info(f"[Event] Data saved to {rel_path}")
            print(f"[Event] Data saved to {rel_path}")
            
        except Exception as e:
            logging.error(f"Event save failed: {e}")
            logging.debug(traceback.format_exc())
            
#-------------------------------------------------------------------------------
class SimulatedFileSave:
    def __init__(self, signal_handler, hdr_handler, file_handler):
        self.signal_handler = signal_handler
        self.hdr_handler    = hdr_handler
        self.file_handler   = file_handler
        self.test_event_triggered = False

    def generate_data_hdr(self, fragment_type = 0x00, event_time = None, channel_no = 0, fragment_no = 0):
        """Generate header data with optional event flag and timestamp."""
        hdr_size = get_sys_value('sys_data_hdr_size')
        hdr_data = np.zeros(hdr_size, dtype = dt_sample_hdr)

        remote_time = np.uint32(event_time if get_sys_value('brd_hw_gps') else int(time.time()))

        hdr_data[0] = np.uint16((channel_no << 8)    | DataHdrParams.DATA_HDR_ID) # Combines Fragment ID & Type (Big Endian)
        hdr_data[1] = np.uint16((fragment_type << 8) | fragment_no)     # Combines Channel No & Fragment No (Big Endian)
        hdr_data[2] = np.uint16(get_sys_value('sys_ser_no'))
        hdr_data[3] = np.uint16(remote_time & 0xFFFF)
        hdr_data[4] = np.uint16((remote_time >> 16) & 0xFFFF)

        # self.hdr_handler.parse_data_hdr(hdr_data)
        return hdr_data.astype(dt_sample)

    def generate_test_data(self, channel_no, fragment_no, fragment_type = 0x00, sequence_start = 0):
        """Generate a sequence-based data buffer with a header."""
        time.sleep(0.10)  # Simulate real-time arrival delay
        hdr_data = self.generate_data_hdr(fragment_type, None, channel_no, fragment_no)
        data_part = np.arange(sequence_start, sequence_start + get_sys_value('adc_fragment'), dtype = dt_sample)
        return np.concatenate((hdr_data, data_part))

    def run_test(self):
        log_file = "sim_filesave.txt"
        # Save current handlers (especially the console one)
        logger = logging.getLogger()
        original_handlers = logger.handlers[:]

        # Remove console handlers (usually StreamHandler)
        for h in original_handlers:
            if isinstance(h, logging.StreamHandler):
                logger.removeHandler(h)

        # Setup simulation-only FileHandler
        file_handler = logging.FileHandler(log_file, mode = 'a', encoding = 'utf-8')
        file_handler.setLevel(logging.INFO)

        # Optional: remove formatting to keep logs cleaner in simulation file
        file_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))


        # Attach temporary handler
        logger = logging.getLogger()
        logger.addHandler(file_handler)
        
        try:
            print("Starting data saving test...")
            sequence_start = 1000  # Start sequence from 1000 for easier manual verification

            n_channels = get_sys_value('adc_channels')
            no_of_fragments = get_sys_value('sys_no_of_fragments')
            
            for second in range(1, 11):
                print(f"[Test] Second {second}")
                for ch in range(n_channels):
                # for fragment_no in range(no_of_fragments):
                    # for ch in range(n_channels):
                    for fragment_no in range(no_of_fragments):
                        if second % 4 == 0 and fragment_no == 0 and ch == 0:
                            fragment_type = 0x01 if not self.test_event_triggered else 0x02
                            print(f"[WARNING] Injecting {'EVENT' if fragment_type == 0x01 else 'SATURATION'}...")
                            self.test_event_triggered = not self.test_event_triggered
                        else:
                            fragment_type = 0x00

                        test_data = self.generate_test_data(
                            channel_no  = ch,
                            fragment_no = fragment_no,
                            fragment_type  = fragment_type,
                            sequence_start = sequence_start
                        )
                        print(f" Channel {ch} -> Fragment {fragment_no}")
                        self.signal_handler.insert_new_data(test_data)
                        sequence_start += get_sys_value('adc_fragment')

            print("Test completed! Check the generated files.")

        finally:
            logging.info("Simulation completed...")
            # Remove handler after simulation ends
            logger.removeHandler(file_handler)
            file_handler.close()
			# Restore previous console handlers
            for h in original_handlers:
                logger.addHandler(h)
                
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    tk_root = None  # Dummy root, not needed for test
    from vibmscope.maps_signal      import Signal
    from common.core.hdr_parser     import HeaderProcessor
    from common.modules.cmd_remote  import CommandHandler

    sys_config_init()
    # Configure test parameters for simulation
    set_sys_value('adc_fragment', 32)
    set_sys_value('adc_srate', 128)
    set_sys_value('sys_no_of_fragments', 128//32)

    set_session_flag('record', True)    # Enable recording
    set_session_flag('event', True)     # Enable event detection
    
    if not get_sys_value('adc_channels'):
        set_sys_value('adc_channels', 1)

    set_sys_value('sys_ser_no', 1234)
    set_sys_value('brd_hw_gps', False)
        
    hdr_handler  = HeaderProcessor()
    cmd_handler  = CommandHandler()
    
    file_handler = FileSave(hdr_handler)
    
    data_path = os.path.join('.', 'data')
    file_handler.set_data_path(data_path)
    
    signal_handler = Signal(tk_root, cmd_handler, file_handler, hdr_handler)

    test = SimulatedFileSave(signal_handler, hdr_handler, file_handler)
    test.run_test()
