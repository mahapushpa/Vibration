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
import vibmshared.modules.cmd_remote  as cmd_remote
from vibmshared.utils.utils_helpers import get_sensor_unit_factor, safe_log
from vibmshared.core.sys_config     import get_sys_value, set_sys_value
from vibmshared.core.common         import get_session_flag, set_session_flag, dt_sample
from vibmshared.core.parameters     import (
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
        self.event_type      = None  # store type of event - event or saturation
        self.event_counter   = 0     # used for centre detection of event
        self.event_detected  = False # preserve till data are not saved, event status
        self.event_filename  = None  # store the event file name
        self.event_start_time= None  # store the starting time of event data
        
        # Data buffers
        self.all_fragments_rcvd  = False
        self.samples_in_fragment = get_sys_value('adc_fragment')

        self.clear_signal_buffers()

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

        if get_session_flag('event'):   # event button is active
            self.prepare_event_file_param()  # check for event in fragment

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

        # [F9] Dropped-fragment resync: if this (ch, fragment) slot is already
        # marked received but the second never completed, at least one other
        # fragment was lost upstream (queue-full drop — see the serial_comm
        # WARN added in Phase 0). Discard the stale, incomplete second and
        # start re-assembling from this fragment, instead of silently mixing
        # two different seconds in one plot/record cycle.
        if self.fragment_received[ch, frag_no]:
            safe_log(None, "[Signal] Incomplete second discarded (dropped fragment detected) — resyncing",
                     tag = "warning", do_print = True)
            self.fragment_received[:, :] = False

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

            if get_session_flag('event'): # event button is active
                self.save_centered_event()

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
            # [F8] The just-completed second already sits in t_ydata and
            # belongs to the NEW hour: close the old file EXCLUDING it, then
            # count it as the new file's first second — mirroring the
            # first-time branch above. Previously that second was written
            # into the OLD hour's file while the oldest pending old-hour
            # second fell out of the partial slice (~1 s misfiled per hour).
            self.close_current_file(exclude_latest_second = True)
            self.open_new_record_file(file_str, date_str, time_str, current_hour)
            self.record_second_counter = 1  # current (new-hour) second already captured
            
        else: # every 5 seconds
            self.save_full_window_data()

    #---------------------------------------------------------------------------
    def clear_signal_buffers(self):
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
    def save_centered_event(self):
        """Advance the post-event counter; once the event has scrolled to the
        centre of the display window, write it out and reset event state.

        Returns:
            True  - event was centred and saved successfully.
            False - event was centred but the save failed (already logged).
            None  - nothing to do this call: either no event is active, or the
                    active event has not yet reached the centre of the window.

        Contract notes for the next-stage driver (these funcs are not wired yet):
        - [B] The return is deliberately tri-valued (True / False / None, see
          above), so a caller can already act on all three outcomes. The one
          ambiguity that remains: BOTH "no event active" and "event active but
          not yet centred" collapse to None. That is fine for the intended
          usage — call this once per completed second and simply ignore None —
          because the caller does not need to act differently in those two idle
          states. Only if a future caller must distinguish "idle" from "counting
          toward centre" (e.g. to drive a UI countdown) should this be split
          into two distinct sentinels (e.g. a small status enum) instead of
          overloading None. Decide that when the driver is written; today's
          three values are sufficient.
        - [C] CONFIRMED BEHAVIOUR, not a bug: event_detected/event_counter are
          reset BEFORE the save is attempted on purpose. If the save fails there
          is nothing worth keeping — the rolling buffer has already scrolled past
          this event — so we log the failure (above), drop the event, and let
          detection immediately re-arm for the next one. Do NOT "fix" this by
          deferring the reset until after a successful save.
        """
        # [A] Only advance/save while an event is actually active. Without this
        # guard a stray call still increments the counter and, once it crosses
        # the centre threshold, calls save_event_data() with a stale/None
        # filename (get_save_path(None) -> TypeError).
        if not self.event_detected:
            return

        self.event_counter += 1
        if PlotParams.is_event_centre(self.event_counter):
            self.event_counter = 0
            self.event_detected = False
            if not self.file_handler.save_event_data(self.event_filename, self.t_ydata, self.event_start_time, self.event_type):
                safe_log(None, f"Aborting: Event write failed for {self.event_filename}", tag = "error", do_print = True)
                return False

            return True
            
    #---------------------------------------------------------------------------
    def prepare_event_file_param(self):
        """Detect the first event/saturation fragment of a new event and arm a
        capture: record the event type, start time and output file name so a
        later save_centered_event() call can write the window out.

        No return value — it mutates event state (event_detected, event_type,
        event_start_time, event_filename, event_counter) as a side effect.

        Note on the event timestamp for the next-stage driver:
        - system_time is sourced by HeaderProcessor from the remote GSN node
          (RTC) when available, else the laptop clock — remote takes priority.
        - The file-header "Start Date/Time" is event_start_time =
          system_time - PRE_EVENT_SECOND, and the samples written come from
          PlotParams.get_event_sample_slice() — a symmetric window of
          PRE_EVENT_SECOND before .. after the display-window middle. These line
          up (first written sample time == event_start_time) as long as the
          driver saves while the event sits at that middle second, which is the
          design intent. Keep the two in step if the pre/post seconds or the
          centring rule ever change.
        """
        # [D] Only genuine event/saturation fragments start a capture. The old
        # `!= "normal"` also matched "unknown" (HeaderProcessor's fallback for a
        # corrupted/unrecognised type code), which would spuriously trigger a
        # capture into an "unknown_*.txt" file.
        if not self.event_detected and self.hdr_handler.fragment_type in ("event", "saturation"):
            self.event_counter  = 0
            self.event_detected = True
            # [E] system_time may be np.uint32 (RTC path); cast to int first so
            # a value < PRE_EVENT_SECOND can't underflow-wrap to ~4.29e9.
            self.event_start_time = int(self.hdr_handler.system_time) - PlotParams.PRE_EVENT_SECOND
            self.event_type = self.hdr_handler.fragment_type # for meta data
            file_str = self.hdr_handler.get_time_string(self.hdr_handler.system_time, only_filename=True)
            self.event_filename = f"{self.event_type}_{file_str}"

    #---------------------------------------------------------------------------
    def open_new_record_file(self, file_str, date_str, time_str, current_hour):
        file_name = f"record_{file_str}"
        self.record_start_hour = current_hour
        self.record_filename = self.file_handler.get_save_path(file_name)
        if not self.file_handler.write_metadata(self.record_filename, date_str, time_str):
            safe_log(None, f"Aborting: metadata write failed for {self.record_filename}", tag = "error", do_print = True)
            return False

        rel_path = self.path_handler.get_relative_path(self.record_filename)
        logging.info(f"[Recording] New file opened: {rel_path}")
        return True
        
    #---------------------------------------------------------------------------
    def close_current_file(self, exclude_latest_second = False):
        """Save pending partial data (optionally excluding the newest second —
        hour-rollover path, [F8]), write the STOP tokens, and log the close."""
        if self.record_filename:
            self.save_partial_window_data(exclude_latest_second)
            self.insert_closing_time() # update metadata for stop date and time
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
            if not self.file_handler.write_data(self.record_filename, self.t_ydata):
                safe_log(None, f"Data write failed for {self.record_filename} (metadata was written)", tag = "error", do_print = True)
                return False
                
            rel_path = self.path_handler.get_relative_path(self.record_filename)
            logging.info(f"[Recording] Data saved to: {rel_path}")
            return True
            
    #---------------------------------------------------------------------------
    def save_partial_window_data(self, exclude_latest_second = False):
        if self.record_second_counter > 0:
            srate = get_sys_value('adc_srate')
            partial_samples = srate * self.record_second_counter
            if exclude_latest_second:
                # [F8] hour rollover: the newest second in t_ydata belongs to
                # the NEW hour — write only the pending old-hour seconds
                # (the `counter` seconds immediately BEFORE the newest one).
                trimmed_data = [np.array(ch)[-(partial_samples + srate):-srate] for ch in self.t_ydata]
            else:
                trimmed_data = [np.array(ch)[-partial_samples:] for ch in self.t_ydata]
            if not self.file_handler.write_data(self.record_filename, trimmed_data):
                safe_log(None, f"Data write failed for {self.record_filename} (metadata was written)", tag = "error", do_print = True)
                return False

            rel_path = self.path_handler.get_relative_path(self.record_filename)
            logging.info(f"[Recording] Final {self.record_second_counter}s written to {rel_path}")
            self.record_second_counter = 0
            return True

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
        # Factor recomputed per call (cheap lookup) so a unit changed while
        # the session is OFF takes effect on the next session — the old
        # __init__-cached factor went stale (DECIDED 2026-07-16: unit changes
        # are permitted in session-off only). np.clip saturates instead of
        # letting np.int16 silently wrap for factors > 1.
        factor = get_sensor_unit_factor(get_sys_value('time_yspan'))
        return np.int16(np.clip(ydata * factor, -32768, 32767))
            
        # elif unit == 'VEL':   # the display unit is Velocity, convert in adc count to mm/Sec
            # return (ydata * ADCConfig.adc_vel_in_bit)

        # elif unit == 'ACC':   # the display unit is Acceleration, convert in adc count to mm^2/Sec
            # return (ydata * ADCConfig.adc_acc_in_bit)
        # else:
          # return ydata

    #---------------------------------------------------------------------------
    def shift_leftover(self, consumed):
        """After consuming `consumed` bytes from the front of ser_buffer, shift any
        remaining unconsumed bytes down to index 0 so future reads stay aligned."""
        remaining = self.ser_buffer_bytes - consumed
        if remaining > 0:
            self.ser_buffer[0:remaining] = self.ser_buffer[consumed:consumed + remaining]
        self.ser_buffer_bytes = remaining
        
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

                    # if first byte of buffer is CMD_HDR_ID, resize to the command-reply size
                    frame_id = self.ser_buffer[0]
                    if frame_id == cmd_remote.CMD_HDR_ID:
                        expected_reply_size = self.cmd_handler.get_expected_response_size()

                    if self.ser_buffer_bytes >= expected_reply_size:
                        if frame_id == DataHdrParams.DATA_HDR_ID:
                            data = self.convert_to_int16(self.ser_buffer[:expected_reply_size])
                            self.shift_leftover(expected_reply_size)
                            return data  # Return captured data and process as adc data; any leftover handled next call

                        elif frame_id == cmd_remote.CMD_HDR_ID:
                            response = self.ser_buffer[:expected_reply_size]  # Extract full response
                            self.shift_leftover(expected_reply_size)
                            self.cmd_handler.rcv_response(response)  # Process response
                            return None  # Reply handled; any leftover (next data fragment) handled next call

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

                        print(f"[WARNING] Timeout reached, returning partial buffer: {len(data) if data is not None else 0} sample words")
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
            print(f"[WARNING] Invalid transform selection: {self.selected_transform}. Returning empty spectrum.")
            return np.zeros(1), 0



