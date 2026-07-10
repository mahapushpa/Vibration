import os
import time
import logging
import traceback
import numpy as np
import matplotlib.pyplot as plt

from collections    import deque as dq
from numpy.fft      import rfft, rfftfreq
from scipy.signal   import iirnotch, butter, filtfilt, get_window

#-------------------------------------------------------------------------------
# import the user functions and classes
import common.modules.cmd_remote  as cmd_remote
from common.utils.utils_helpers import get_sensor_unit_factor, safe_log
from common.core.sys_config     import sys_config_init, get_sys_value, set_sys_value
from common.core.common         import get_session_flag, set_session_flag, dt_sample
from common.core.parameters     import (
    FilterParams, 
    WindowParams, 
    TransformParams, 
    DataHdrParams, 
    PlotParams,
)

#-------------------------------------------------------------------------------
class Signal:
    """Main handler for signal processing, buffering, event detection, and recording."""
    def __init__(self, tk_root = None, cmd_handler = None, file_handler = None, hdr_handler = None, path_handler = None):
        self.tk_root = tk_root
        self.cmd_handler = cmd_handler
        self.file_handler= file_handler
        self.hdr_handler = hdr_handler
        self.path_handler= path_handler
        self.processor   = SignalProcessor()
        
        # Serial port buffering variables
        self.ser_buffer_bytes  = 0  # Bytes in Persistent buffer
        self.ser_expected_size = get_sys_value("sys_rcv_data_size")
        self.ser_buffer = bytearray(self.ser_expected_size)# Persistent buffer
        
        # File Processing Variables
        self.record_filename = None
        self.record_start_hour = 0
        self.record_second_counter = 0
        
        # Event handling
        self.event_type      = None  # store type of venet - event or saturation
        self.event_counter   = 0     # used for centre detection of event
        self.event_detected  = False # preserve till data are not saved, event status
        self.event_filename  = None  # store the event file name
        self.event_start_time= None  # store the startting time of event data
        
        # Data buffers
        self.all_fragments_rcvd  = False
        self.samples_in_fragment = get_sys_value('adc_fragment')
        self.sensor_factor = get_sensor_unit_factor(get_sys_value('time_yspan'))
       
        self.init_signals_buffers()

    #---------------------------------------------------------------------------
    def insert_new_data(self, new_ydata):
        """Processes and inserts new fragment data for correct channel.
        Waits for all fragments for one second across all channels,
        then moves to the main plot buffer. Handles events and recording."""
        
        if new_ydata.dtype != np.int16:
            safe_log(None, f"[Signal] Unexpected dtype: {new_ydata.dtype}, expected: int16", tag = "warning", do_print = True)

        hdr_size = get_sys_value('sys_data_hdr_size')
        fragment_hdr = new_ydata[:hdr_size]
        ydata        = new_ydata[hdr_size:]
        self.hdr_handler.parse_data_hdr(fragment_hdr)

        ch = self.hdr_handler.channel_no
        frag_no = self.hdr_handler.fragment_no        

        # Validate channel and fragment index
        if not (0 <= ch < self.no_of_channels):
            logging.warning(f"[Signal] Invalid channel number {ch}")
            return False

        if not (0 <= frag_no < self.no_of_fragments):
            logging.warning(f"[Signal] Invalid fragment number {frag_no} for channel {ch}")
            return False
        
        if get_sys_value('time_yspan') != 'CNT':
            ydata = self.ydata_to_unit(ydata)  # Convert to desired format

        # Compute offset in row based on fragment index
        start = frag_no * self.samples_in_fragment
        end   = start + self.samples_in_fragment

        self.fragment_buffer[ch, start:end] = ydata[:self.samples_in_fragment] # avoid extra
        # safe_log(None, f"[Insert] CH = {ch}, FRAG = {frag_no}, start = {start}, end = {end}", tag = "debug", do_print = True)

        self.fragment_received[ch, frag_no] = True

        # logging.debug(f"[Insert] Ch = {ch}, frag No. = {self.hdr_handler.fragment_no}, "
              # f"Fragment type = {self.hdr_handler.fragment_type}, "
              # f"Len of rcvd Data = {len(ydata)}, frag_buf size = {len(self.fragment_buffer[ch])}")
        # print(f"[Insert] Ch = {ch}, frag No. = {self.hdr_handler.fragment_no}, "
              # f"Fragment type = {self.hdr_handler.fragment_type}, "
              # f"Len of rcvd Data = {len(ydata)}")

        # Check if all fragments for all channels have been received
        if np.all(self.fragment_received):
            for ch in range(self.no_of_channels):
                frag_arr = self.fragment_buffer[ch]
                # print(f"[Frag->Main] Channel {ch}: pushing {len(frag_arr)} samples")                
                self.t_ydata[ch].extend(frag_arr)
                
            # print(f"All Fragment are received")
            
            self.all_fragments_rcvd = True
            # self.debug_plot_fragment_buffer()
            self.fragment_received[:, :] = False  # Reset all fragment flags

            #-------------------------------------------------------------------
            # Continuous recording logic
            if get_session_flag('record'):
                self.record_handling()
                
            # If recording is stopped, ensure the last file is closed and partial data saved
            elif get_session_flag('prev_record'):
                set_session_flag('prev_record', False)
                # self.save_partial_window_data()
                self.close_current_file()
            return True
        
        #-----------------------------------------------------------------------
        else:   # still one second is not over
            return False

    #---------------------------------------------------------------------------
    def record_handling(self):
        file_str, date_str, time_str = self.hdr_handler.get_time_string(self.hdr_handler.system_time)
        current_hour = self.extract_hour(time_str)
        if current_hour is None:
            logging.error("[Recording] Invalid time format; aborting file logic.")
            return

        if not get_session_flag('prev_record'):     # firs time
            self.record_second_counter = 1  # First second already captured, initialize to 1 to avoid losing initial data
            set_session_flag('prev_record', True)   # Mark recording as active
            self.open_new_record_file(file_str, date_str, time_str, current_hour)
            
        elif self.record_start_hour != current_hour:  # Hour Rollover
            self.close_current_file()
            self.open_new_record_file(file_str, date_str, time_str, current_hour)
            
        else: # every 5 seconds
            self.save_full_window_data()

    #---------------------------------------------------------------------------
    def init_signals_buffers(self):
        """Set up time and frequency domain data containers based on config."""
        # must be first statement, due to dependancy of it on others
        self.no_of_channels  = get_sys_value('adc_channels')
        self.no_of_fragments = get_sys_value('sys_no_of_fragments')

        srate = get_sys_value('adc_srate')
        samples_in_window = srate * PlotParams.get_time_x_span()
        
        self.dc_value = [0.0] * self.no_of_channels

        # Time domain
        self.t_xdata = np.arange(0, samples_in_window, 1)
        self.t_ydata = [dq(np.zeros(samples_in_window, dtype = dt_sample), maxlen = samples_in_window)
                                    for _ in range(self.no_of_channels)]

        # Frequency domain
        span  = PlotParams.fftXParams['max_hz']
        freqs = rfftfreq(samples_in_window, d = 1/srate)
        freqs = freqs[np.where(freqs <= span)]  # limit FFT bins without breaking resolution
        
        self.f_xdata = np.array(freqs)
        self.f_ydata = np.zeros((self.no_of_channels, len(freqs)), dtype = float)

        # Fragment buffer for one second per channel
        self.fragment_buffer   = np.zeros((self.no_of_channels, srate), dtype = dt_sample)
        self.fragment_received = np.zeros((self.no_of_channels, self.no_of_fragments), dtype = bool)

    #---------------------------------------------------------------------------
    def clear_signal_buffers(self):
        self.init_signals_buffers()

    #---------------------------------------------------------------------------
    def event_centered(self):
        """If an event is centered in window, save and reset its parameters"""
        self.event_counter += 1
        if PlotParams.is_event_centre(self.event_counter):
            self.event_counter = 0
            self.event_detected = False
            self.file_handler.save_event_data(self.event_filename, self.t_ydata,
                                                self.event_start_time, self.event_type)

    #---------------------------------------------------------------------------
    def get_event_file_name(self):
        """Detect the first event fragment in a second (non-zero type marks an event)"""
        if not self.event_detected and self.hdr_handler.fragment_type != "normal":
            self.event_counter  = 0
            self.event_detected = True
            self.event_start_time = self.hdr_handler.system_time - PlotParams.PRE_EVENT_SECOND
            self.event_type = self.hdr_handler.fragment_type # for meta data
            file_str = self.hdr_handler.get_time_string(self.hdr_handler.system_time, only_filename=True)
            self.event_filename = f"{self.event_type}_{file_str}"

    #---------------------------------------------------------------------------
    def open_new_record_file(self, file_str, date_str, time_str, current_hour):
        file_name = f"record_{file_str}"
        self.record_filename = self.file_handler.get_save_path(file_name)
        self.file_handler.write_metadata(self.record_filename, date_str, time_str)
        self.record_start_hour = current_hour
        rel_path = self.path_handler.get_relative_path(self.record_filename)
        logging.info(f"[Recording] New file opened: {rel_path}")

    #---------------------------------------------------------------------------
    def close_current_file(self):
        """Dummy closer now that we use 'with open()' for all writes. It is just message function now"""
        if self.record_filename:
            self.save_partial_window_data()
            self.insert_closing_time() # update metadata for stop date and time
            rel_path = self.path_handler.get_relative_path(self.record_filename)
            print(f"[Recording] Closed file: {rel_path}")
            logging.info(f"[Recording] Closed file: {rel_path}")
            #self.record_filename = None

    #---------------------------------------------------------------------------
    def close_open_files(self):
        """No file handles to close; all file writes are done via 'with open()'."""
        if self.record_filename:
            rel_path = self.path_handler.get_relative_path(self.record_filename)
            print(f"[Recording] Closed file: {rel_path}")
            logging.info(f"[Recording] Closed file: {rel_path}")
            #self.record_filename = None

    #---------------------------------------------------------------------------
    def insert_closing_time(self):
        _, date_str, time_str = self.hdr_handler.get_time_string(self.hdr_handler.system_time)
        # filename = os.path.join(self.data_path, self.record_filename)
        filename = self.record_filename
        token_map = {
            "{ STOP_DATE }\n": f"{date_str}".ljust(len("{ STOP_DATE }")) + "\n",
            "{ STOP_TIME }\n": f"{time_str}".ljust(len("{ STOP_TIME }")) + "\n",
        }
        self.update_metadata_tokens_value(filename, token_map)        
        
    #---------------------------------------------------------------------------
    def update_metadata_tokens_value(self, filename, token_map):
        """
        Firmware-style in-place token replacer. Stops immediately when all tokens are replaced.

        Args:
            filename (str): Path to the target file.
            token_map (dict): {token_string: replacement_string}, with newline at the end.
        """
        total_tokens = len(token_map)
        replaced_tokens = set()

        with open(filename, 'r+', encoding='utf-8') as f:
            while True:
                if len(replaced_tokens) == total_tokens:
                    # print("[INFO] All tokens inserted successfully.")
                    return

                pos = f.tell()
                line = f.readline()
                if not line:
                    print("[WARN] End of file reached before replacing all tokens.")
                    break

                updated_line = line
                for token, value in token_map.items():
                    if token in updated_line and token not in replaced_tokens:
                        replacement = value.ljust(len(token))
                        updated_line = updated_line.replace(token, replacement)
                        replaced_tokens.add(token)

                if updated_line != line:
                    f.seek(pos)
                    f.write(updated_line.ljust(len(line)))

        # Fallback check at the end
        missing = set(token_map.keys()) - replaced_tokens
        if missing:
            print(f"[WARN] Tokens not found in file: {', '.join(missing)}")

    #---------------------------------------------------------------------------
    def get_last_record_file(self):
        return self.record_filename  # or full path if needed
    
    #---------------------------------------------------------------------------
    def save_full_window_data(self):
        # Save data every window x span seconds(one complete screen)
        self.record_second_counter += 1
        if self.record_second_counter >= PlotParams.get_time_x_span():
            self.record_second_counter = 0
            self.file_handler.write_data(self.record_filename, self.t_ydata)
            rel_path = self.path_handler.get_relative_path(self.record_filename)
            logging.info(f"[Recording] Data saved to: {rel_path}")

    #---------------------------------------------------------------------------
    def save_partial_window_data(self):
        if self.record_second_counter > 0:
            partial_samples = get_sys_value('adc_srate') * self.record_second_counter
            # trimmed_data = [list(ch)[-partial_samples:] for ch in self.t_ydata]
            trimmed_data = [np.array(ch)[-partial_samples:] for ch in self.t_ydata] # need to verify
            self.file_handler.write_data(self.record_filename, trimmed_data)
            rel_path = self.path_handler.get_relative_path(self.record_filename)
            logging.info(f"[Recording] Final {self.record_second_counter}s written to {rel_path}")
            self.record_second_counter = 0

    #---------------------------------------------------------------------------
    def extract_hour(self, time_str):
        """Extracts hour as integer from HH:MM:SS time string."""
        try:
            return int(time_str.split(":")[0])
        except Exception as e:
            logging.error(f"Failed to extract hour: {e}")
            return None

    #---------------------------------------------------------------------------
    def ydata_to_unit(self, ydata):
        """ convert the y axis data based on unit selected."""
        unit = get_sys_value('time_yspan')
        return (np.int16(ydata * self.sensor_factor))
            
        # elif unit == 'VEL':   # the display unit is Velocity, convert in adc count to mm/Sec
            # return (ydata * ADCConfig.adc_vel_in_bit)

        # elif unit == 'ACC':   # the display unit is Acceleration, convert in adc count to mm^2/Sec
            # return (ydata * ADCConfig.adc_acc_in_bit)
        # else:
          # return ydata

    #---------------------------------------------------------------------------
    def data_capture(self, serial_port):
        """
        Reads data from the serial port, ensuring alignment and handling errors gracefully.
        Parameters:
            serial_port : Serial port object
        Returns:
            data (converted) if successful, or None if no valid data is available.
        """

        timeout = 2.0 # Timeout value  
        start_time = time.time()  # Ensure start_time is always initialized
        
        # we are assuming adc data is going to capture, take this as expected_reply_size in bytes
        expected_reply_size = self.ser_expected_size

        while True:
            try:
                available_bytes = serial_port.inWaiting()
                if available_bytes:
                    # here we are reading all and which is minimum, so we don't have issue for data or cmd reply
                    read_size = min(expected_reply_size - self.ser_buffer_bytes, available_bytes)
                    self.ser_buffer[self.ser_buffer_bytes : self.ser_buffer_bytes + read_size] = serial_port.read(read_size)
                    self.ser_buffer_bytes += read_size
                    start_time = time.time()  # Reset timeout after receiving data

                    # if first byte of buffer is CMD_HDR_ID and Waiting for command
                    # change the expected_reply_size to reply size to complete the message.
                    frame_id = self.ser_buffer[0]
                    if get_session_flag('cmd_waiting') and frame_id == cmd_remote.CMD_HDR_ID:
                        expected_reply_size = self.cmd_handler.get_expected_response_size()

                    if self.ser_buffer_bytes >= expected_reply_size:
                        if frame_id == DataHdrParams.DATA_HDR_ID:
                            data = self.convert_to_int16(self.ser_buffer[:expected_reply_size])
                            self.ser_buffer_bytes -= expected_reply_size  # reduce buffer counts
                            return data  # Return captured data and process as adc data

                        elif frame_id == cmd_remote.CMD_HDR_ID:
                            response = self.ser_buffer[:expected_reply_size]  # Extract full response
                            self.ser_buffer_bytes -= expected_reply_size
                            set_session_flag('cmd_waiting', False)   # Mark system as waiting of command is over
                            self.cmd_handler.rcv_response(response)  # Process response
                            return None  # Do not process as ADC data

                        else:
                            print(f"[WARNING] Unexpected Frame ID: 0x{frame_id:02X}, Ignoring...")
                            self.ser_buffer_bytes = 0  # Reset buffer to avoid misalignment
                            continue  # Go back to read the next valid frame

                # Prevent excessive blocking - time out or session closed, return from while loop
                if time.time() - start_time > timeout or not get_session_flag('session'):
                # Ensure the buffer contains a multiple of 2 bytes before processing
                    
                    if self.ser_buffer_bytes:
                        data = None
                        aligned_size = self.ser_buffer_bytes - (self.ser_buffer_bytes % 2)  # Ensure even bytes  

                        if aligned_size:
                            data = self.convert_to_int16(self.ser_buffer[:aligned_size])

                        # Handle leftover unaligned byte
                        if self.ser_buffer_bytes % 2 != 0:
                            self.ser_buffer[0] = self.ser_buffer[self.ser_buffer_bytes - 1]  # Shift last byte
                            self.ser_buffer_bytes = 1  # Preserve 1 leftover byte
                        else:
                            self.ser_buffer_bytes = 0  # No leftover bytes  

                        print(f"[WARNING] Timeout reached, returning partial buffer: {len(data) if data else 0} sample words")
                        return data  # Return partial data or None if no aligned bytes available  

                    else:
                        print("[WARNING] Timeout reached, no data to return")
                        logging.warning("Serial read timeout.")
                        return None  # No data available  

            except Exception as e:
                print("[ERROR] Communication Lost from Device - Check Sender!", e)
                logging.error(f"Serial Capture Error: {e}")
                logging.debug(traceback.format_exc())
                return None  # Don't exit, let the caller handle failure

    #---------------------------------------------------------------------------
    def convert_to_int16(self, buffer):
        """
        Function to convert raw byte buffer to signed int16 (little-endian) 
        format using the predefined numpy dtype
        """    
        return (np.frombuffer(buffer, dtype = dt_sample))

#-------------------------------------------------------------------------------
# SignalProcessor Class - Handles Filtering, Windowing and FFT Processing
#-------------------------------------------------------------------------------
class SignalProcessor:
    def __init__(self):
        self.sample_rate = get_sys_value('adc_srate')
        self.filters = FilterParams.filters
        self.selected_filters   = FilterParams.get_selected()
        self.selected_window    = WindowParams.get_selected()
        self.selected_transform = TransformParams.get_selected()
        
    def apply_filters(self, data):
        """
        Applies notch, low-pass, and high-pass filters based on user-selected settings.
        """
     
        if not self.selected_filters:
            logging.debug("[Filter] No filters selected.")
            return data
            
        for f_name in FilterParams.get_selected():
            params = self.filters[f_name]

            if f_name == 'notch':
                b, a = iirnotch(
                    params['frequency'],
                    params['quality_factor'],
                    self.sample_rate
                )
            elif f_name == 'lowpass':
                b, a = butter(
                    params['order'],
                    params['cutoff_frequency'],
                    btype='low',
                    fs=self.sample_rate
                )
            elif f_name == 'highpass':
                b, a = butter(
                    params['order'],
                    params['cutoff_frequency'],
                    btype='high',
                    fs=self.sample_rate
                )
            else:
                logging.warning(f"[Filter] Unsupported filter: {f_name}")
                continue

            data = filtfilt(b, a, data)
            logging.debug(f"[Filter] Applied {f_name}")

        return data

    def preprocessing_signal(self, ydata):
        """
        Applies filtering and windowing but does NOT perform FFT.
        This ensures separation of concerns for different transform methods.
        """
        if self.selected_filters is not None:
            ydata = self.apply_filters(ydata)  # Apply selected filter before windowing
        
        if self.selected_window != 'None':
            window = get_window(self.selected_window, len(ydata))
            ydata = ydata * window
        
        return ydata  # Only return the preprocessed signal

    def compute_transform(self, ydata):
        """
        Performs the selected transformation (FFT, SFFT, etc.).
        """
        if self.selected_transform == 'FFT':  
            fft_data = np.abs(rfft(ydata))  # Compute FFT magnitude
            dc_component = fft_data[0]  # Store DC component separately
            fft_data[0] = 0  # Remove DC component for display

            # Apply dB conversion if required
            if get_sys_value('fft_yspan') == 'dB':
                fft_data = 20 * np.log10(np.maximum(fft_data, 1e-10))  # Convert to dB, avoid log(0)
            return fft_data, dc_component
            
        elif self.selected_transform == 'SFFT':
            fft_data = self.compute_sfft(ydata)  # Placeholder for SFFT (to be implemented)
            dc_component = fft_data[0]  # Store DC component separately
            fft_data[0] = 0  # Remove DC component for display

            # Apply dB conversion if required
            if get_sys_value('fft_yspan') == 'dB':
                fft_data = 20 * np.log10(np.maximum(fft_data, 1e-10))  # Convert to dB, avoid log(0)
            return fft_data, dc_component        

        else:
            print(f"[WARNING] Invalid transform selection: {self.selected_transform}. Defaulting to FFT.")
            fft_data = np.abs(rfft(ydata))
            return np.zeros(1), 0



