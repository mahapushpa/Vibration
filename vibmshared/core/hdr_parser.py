import time
import logging
import numpy as np
from   datetime import datetime, timedelta

#-------------------------------------------------------------------------------
from vibmshared.core.parameters import DataHdrParams
from vibmshared.core.common     import dt_sample_hdr, dt_sample
from vibmshared.core.sys_config import get_sys_value, sys_config_init

#-------------------------------------------------------------------------------
    
#-------------------------------------------------------------------------------
class HeaderProcessor:
    """
    HeaderProcessor:
        Parses a 10-byte (5 x int16) fragment header received from remote.
    Fields decoded:
        - fragment_id
        - channel_no
        - fragment_no
        - fragment_type: 0x00 (normal), 0x01 (event), 0x02 (saturation)
        - serial_number: 16-bit unsigned
        - system_time: seconds since 2024-01-01
    """
    
    FRAGMENT_TYPES = {
        DataHdrParams.DATA_NORMAL : "normal", 
        DataHdrParams.DATA_EVENT  : "event", 
        DataHdrParams.DATA_SAT    : "saturation"
    }  # Data type mapping

#-------------------------------------------------------------------------------
    def __init__(self):
        self.fragment_id   = np.uint8(0)
        self.channel_no    = np.uint8(0)
        self.fragment_no   = np.uint8(0)
        self.fragment_type = None
        self.serial_number = np.uint16(0)
        self.system_time   = np.uint32(0)
        self.timestamp     = None
        self.data_words    = 0
        
#-------------------------------------------------------------------------------
    def parse_data_hdr(self, hdr):
        """Parses the received buffer and extracts header fields, handling timestamps properly."""
        # Correct parsing using raw byte layout
        hdr_bytes = hdr.tobytes()
        self.fragment_id    = hdr_bytes[0]   # hdr[0]
        self.channel_no     = hdr_bytes[1]   # hdr[0]
        self.fragment_no    = hdr_bytes[2]   # hdr[1]
        fragment_type_raw   = hdr_bytes[3]   # hdr[1]
        
        self.fragment_type  = self.FRAGMENT_TYPES.get(fragment_type_raw, "unknown")
        self.serial_number  = np.uint16(hdr[2])  # Direct assignment (little-endian already)

        # Extract time from header or use system time
        if get_sys_value('brd_hw_rtc'):
            # Merge two uint16 words into a single uint32 value for system_time
            self.system_time = np.uint32(dt_sample_hdr(hdr[3]) + (dt_sample_hdr(hdr[4]) << 16))
        else:
            # Use local system time, Seconds since 2024-01-01
            self.system_time = int(time.time()) - int(datetime(2024, 1, 1, 0, 0, 0).timestamp())

        # Store formatted timestamp (to be used later)
        self.timestamp = self.get_time_string(self.system_time)
        # print(f"[INFO] Header = 0x{self.fragment_id:02X}, ftype = {self.fragment_type}, chn_no = {self.channel_no}, frg_no = {self.fragment_no}")

#-------------------------------------------------------------------------------
    def get_time_string(self, seconds_since_2024, only_filename = False):
        """Formats the system time into separate date and time strings for file names and headers."""
        
        CUSTOM_EPOCH = datetime(2024, 1, 1, 0, 0, 0)  # Define custom epoch
        timestamp = CUSTOM_EPOCH + timedelta(seconds = int(seconds_since_2024))  # Convert system time

        file_name_str = timestamp.strftime("%y%m%d_%H%M%S")  # Format for file names
        date_str = timestamp.strftime("%d %b %Y")  # e.g. 09 Apr 2025
        # date_str = timestamp.strftime("%y-%m-%d")  # Two-digit year format for header
        time_str = timestamp.strftime("%H:%M:%S")  # Standard time format for header

        if only_filename:
            return file_name_str  # Return only file name when requested
    
        return file_name_str, date_str, time_str  # Returns all three formats

#-------------------------------------------------------------------------------
    def display_header(self, use_log = False):
        """Helper function to log the parsed header values."""
        file_name_str, date_str, time_str = self.get_time_string(self.system_time)
        
        if use_log:
            logging.info(f"Fragment ID       : 0x{self.fragment_id:02X}")  # Always in hex format
            logging.info(f"Channel No        : {self.channel_no}")
            logging.info(f"Fragment No       : {self.fragment_no}")
            logging.info(f"Fragment Type     : {self.fragment_type}")
            logging.info(f"System Serial No  : {self.serial_number}")
            logging.info(f"System Time (sec) : {self.system_time}")  # Correctly merged 32-bit time
            # Log Date and Time separately
            logging.info(f"File Name Format : {file_name_str}")
            logging.info(f"Date             : {date_str}")
            logging.info(f"Time             : {time_str}")

        print(f"Fragment ID       : 0x{self.fragment_id:02X}")  # Always in hex format
        print(f"Channel No        : {self.channel_no}")
        print(f"Fragment No       : {self.fragment_no}")
        print(f"Fragment Type     : {self.fragment_type}")
        print(f"System Serial No  : {self.serial_number}")
        print(f"System Time (sec) : {self.system_time}")  # Correctly merged 32-bit time
        # print Date and Time separately
        print(f"File Name Format : {file_name_str}")
        print(f"Date             : {date_str}")
        print(f"Time             : {time_str}")

#-------------------------------------------------------------------------------
# Example usage
if __name__ == "__main__":
    use_log = False

    if use_log:
        logging.basicConfig(filename = '.\maps_hdr_log.txt',
                            filemode = 'w',
                            format   = '%(asctime)s,%(msecs)03d %(name)s %(levelname)s %(message)s',
                            datefmt  = '%Y-%m-%d %H:%M:%S',
                            level    = logging.DEBUG)
    from vibmshared.core.path_manager   import PathManager, USEFUL_FOLDERS
    
    path_mgr = PathManager(__file__, USEFUL_FOLDERS)
    
    # Given information
    hdr_data_len    = DataHdrParams.DATA_HDR_LEN     # in int16
    hdr_fragment_id = DataHdrParams.DATA_HDR_ID      # Fragment ID (Hex)
    
    channel_no      = 0x01      # Example Channel Number
    fragment_no     = 0x00      # Example Fragment Number
    fragment_type   = 0x01      # type (0x00, 0x01, or 0x02)

    remote_time_in_second = np.uint32(56789)
    
    # Create a buffer (Simulated int16 buffer, 16 bytes)
    dummy_buffer = np.zeros(hdr_data_len, dtype = dt_sample_hdr)  # Ensure proper dtype (uint16)
    
    # Example values to simulate a real scenario
    dummy_buffer[0] = np.uint16((channel_no << 8)    | hdr_fragment_id) # Combines Fragment ID & Type (Big Endian)
    dummy_buffer[1] = np.uint16((fragment_type << 8) | fragment_no)     # Combines Channel No & Fragment No (Big Endian)
    
    dummy_buffer[2] = np.uint16(1234)  # Direct Assignment (Little Endian)
    dummy_buffer[3] = np.uint16(remote_time_in_second & 0xFFFF)            # Low 16 bits
    dummy_buffer[4] = np.uint16((remote_time_in_second >> 16) & 0xFFFF)    # High 16 bits
    hdr_data        = dummy_buffer[0:hdr_data_len]
    hdr_data        = hdr_data.astype(dt_sample)

    hdr_handler = HeaderProcessor()
    hdr_handler.parse_data_hdr(hdr_data)
    
    hdr_handler.display_header(use_log = use_log)

    # Logging statement for Fragment Type
    if use_log:
        if hdr_handler.fragment_type == "normal":
            logging.info("The fragment's type is 'normal'. Special processing not needed.")
        elif hdr_handler.fragment_type == "event":
            logging.warning("The fragment's type is 'event'. Special processing may be needed.")
        elif hdr_handler.fragment_type == "saturation":
            logging.warning("The fragment's type is 'saturation'. Special processing may be needed.")
        else:
            logging.error("The fragment's type is unknown. Check the fragment type definition.")

    if hdr_handler.fragment_type == "normal":
        print("The fragment's type is 'normal'. Special processing not needed.")
    elif hdr_handler.fragment_type == "event":
        print("The fragment's type is 'event'. Special processing may be needed.")
    elif hdr_handler.fragment_type == "saturation":
        print("The fragment's type is 'saturation'. Special processing may be needed.")
    else:
        print("The fragment's type is unknown. Check the fragment type definition.")
       