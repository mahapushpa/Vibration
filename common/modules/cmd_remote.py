import re
import struct
import logging
import traceback
from datetime  import datetime
from typing import Dict, Any

#-------------------------------------------------------------------------------
# External dependencies
from common.core.crc_ccitt  import CRC_CCITT
from common.core.common     import get_session_flag, set_session_flag

from common.utils.utils_helpers import (
    validate_param_value, 
    raise_key_error_msg,
    log_info_msg,
)
#-------------------------------------------------------------------------------
# Constants and indices
CMD_HDR_ID   = 0x14  # Command Frame Header ID
CMD_HDR_LEN  = 8     # Frame header size in bytes/ 4 words
CMD_CRC_SIZE = 2     # CRC size in bytes

# Array indexes in send/receive buffers for different fields (bytewise)
CMD_TYPE_IDX = 1
CMD_CRC_IDX  = 6
CMD_DATA_IDX = 8

REPLY_TYPES  = {
    'CMD_ACK': 0x00,
    'CMD_NAK': 0x01,
}

RESPONSE_IDX = {
    'RESP_RES':    0x00,
    'RESP_MODULE': 0x01,
    'RESP_PARAM':  0x02,
    'RESP_VALUE':  0x03,
}

#-------------------------------------------------------------------------------
# Dictionaries for sending commands and expected replies
CMD_SEND_LOOKUP = {
    'CMD_SET': 0x03,
    'CMD_GET': 0x04,
}

# ---------------------------------------------------------------------------
# Optional alias for displaying module headers in production tool gui
# ---------------------------------------------------------------------------
MODULE_ALIASES = {
    "BRD": "Hardware Info",
    "ADC": "Analog Info",
    "SYS": "System Info",
}

# ---------------------------------------------------------------------------
# Final CMD_TABLE with GUI info and flat_key for all INI-compatible entries
# ---------------------------------------------------------------------------
# - flat_key: used for INI save/load
# - name: internal variable name
# - gui: defines the GUI widget and label
# - type: defines the data type for validation and encoding
CMD_TABLE: Dict[str, Dict[str, Dict[str, Any]]] = {
    "SYS": {
        "SER_NO":   {"flat_key": "sys_ser_no",   "size": 2,  "type": "uint16", "range": (0, 9999),
                      "gui": {"label": "Serial No", "widget": "entry", "default": "0000",
                              "tooltip": "Serial Number of Device"}},

        "FW_VER":   {"flat_key": "sys_fw_ver",   "size": 20, "type": "string", "writable": False,
                      "gui": {"label": "FW Ver", "widget": "entry", "default": "FWVR",
                              "tooltip": "Firmware version used"}},
        "HW_VER":   {"flat_key": "sys_hw_ver",   "size": 4,  "type": "string",
                      "gui": {"label": "HW Ver", "widget": "entry", "default": "HWVR",
                              "tooltip": "Hardware version used"}},
        "MFG_DATE": {"flat_key": "sys_mfg_date", "size": 6,  "type": "string", "pattern": r"\d{6}",
                      "gui": {"label": "MFG Date", "widget": "entry", "default": "250715",
                              "tooltip": "Manufacturing date"}},

        "SYS_NAME": {"flat_key": "sys_sys_name", "size": 8,  "type": "string", "default": ["MAPS_JPR"],
                      "gui": None}, 
        "SYS_LOC":  {"flat_key": "sys_sys_loc",  "size": 8, "type": "string", 
                      "default": [chr(26)+chr(55)+chr(11)+'N'+chr(75)+chr(47)+chr(16)+'E'],
                      "gui": None},
        "SYS_LIFE": {"flat_key": "sys_sys_life", "size": 4,  "type": "uint32", "range": (0, 157680000), "writable": False,
                      "gui": None},

        "SYS_AUTO": {"flat_key": "sys_sys_auto", "size": 1,  "type": "uint8",  "allowed": [0, 1],
                      "gui": None},
        "SESSION":  {"flat_key": "sys_session",  "size": 1,  "type": "uint8",  "allowed": [0, 1],
                      "gui": None},
        "SYS_COM":  {"flat_key": "sys_sys_com",  "size": 1,  "type": "string", "allowed": ["R", "U"],
                      "gui": None},

        "TIME":     {"flat_key": "sys_time",     "size": 6,  "type": "string", "pattern": r"\d{6}",
                      "gui": None},
        "DATE":     {"flat_key": "sys_date",     "size": 6,  "type": "string", "pattern": r"\d{6}",
                      "gui": None},
        "PSRC":     {"flat_key": "sys_psrc",     "size": 1,  "type": "string", "allowed": ["B", "S", "M"], "writable": False,
                      "gui": None},
        "VOLT":     {"flat_key": "sys_volt",     "size": 2,  "type": "uint16", "range": (0, 10000), "writable": False,
                      "gui": None},
        "DEFAULT":  {"flat_key": "sys_default",  "size": 1,  "type": "uint8",  "allowed": [0, 1],
                      "gui": None},
    },

    "BRD": {
        "BAT": {"flat_key": "brd_hw_bat", "size": 1, "type": "uint8",  "allowed": [0, 1],
                 "gui": {"label": "BAT", "widget": "check", "default": 0,
                         "tooltip": "Battery is mounted?"}},
                 
        "GPS": {"flat_key": "brd_hw_gps", "size": 1, "type": "uint8",  "allowed": [0, 1],
                 "gui": {"label": "GPS", "widget": "check", "default": 0,
                         "tooltip": "GPS is mounted?"}},

        "USD": {"flat_key": "brd_hw_usd", "size": 1, "type": "uint8",  "allowed": [0, 1],
                 "gui": {"label": "SD Card", "widget": "check", "default": 0,
                         "tooltip": "SD Card is mounted?"}},

        "RTC": {"flat_key": "brd_hw_rtc", "size": 1, "type": "uint8",  "allowed": [0, 1],
                 "gui": {"label": "RTC", "widget": "check", "default": 0,
                         "tooltip": "Real Time Clock is mounted?"}},

        "COM": {"flat_key": "brd_hw_com_module", "size": 1, "type": "string", "allowed": ["-", "G", "W", "L", "I"],
                 "gui": {"label": "Com Module", "widget": "dropdown", "default": " ",
                         "options": {"No" : "-", "GPRS": "G", "WIFI": "W", "LORA": "L", "ISM": "I"},
                         "tooltip": "Which Communication module mounted?"}},

        "POL": {"flat_key": "brd_adc_pol", "size": 1, "type": "string", "allowed": ["B", "U"],
                 "gui": {"label": "ADC Input", "widget": "dropdown", "default": "Bipolar",
                         "options": {"Bipolar": "B", "Unipolar": "U"},
                         "tooltip": "ADC Input type"}},
        # SPN allowed values are multiplied by 10, remote divide rcvd values and send multiplied values
        "SPN": {"flat_key": "brd_adc_span", "size": 1, "type": "uint8", "allowed": [25, 50, 100],
                 "gui": {"label": "ADC Span (V)", "widget": "dropdown", "default": "5.0",
                         "options": {"2.5": 25, "5.0": 50, "10.0": 100},
                         "tooltip": "ADC Input Span?"}},
                          
        "BIT": {"flat_key": "brd_adc_bits", "size": 1, "type": "uint8", "allowed": [16, 18, 20],
                 "gui": {"label": "ADC Bits", "widget": "dropdown", "default": "16",
                         "options": {"16" : 16, "18" : 18, "20" : 20},
                         "tooltip": "No. of Bits of ADC"}},
                          
        "NOT_FRQ": {"flat_key": "brd_notch_freq", "size": 1, "type": "uint8", "allowed": [0, 50, 60],
                 "gui": {"label": "Notch Frq (Hz)", "widget": "dropdown", "default": "50",
                         "options": {"50" : 50, "60" : 60},
                         "tooltip": "Notch Filter Frequency?"}},

        "EXT": {"flat_key": "brd_geo_range_ext", "size": 1, "type": "uint8", "allowed": [0, 1],
                 "gui": {"label": "Grange Ext", "widget": "check", "default": 1,
                         "tooltip": "Natural Frequency Extend Circuit?"}},
                 
        "EXT_FRQ": {"flat_key": "brd_geo_ext_freq", "size": 1, "type": "uint8", "range": (1, 10),
                 "gui": {"label": "Gext Frq (Hz)", "widget": "entry", "default": 1,
                         "tooltip": "What is Extended Frequency?"}},
                 
        "NAT_FRQ": {"flat_key": "brd_geo_nat_freq", "size": 1, "type": "uint8", "range": (1, 32),
                 "gui": {"label": "Gnat Frq (Hz)", "widget": "entry", "default": 10,
                         "tooltip": "Natural Frequency of Geophone?"}},
    },

    "ADC": {
        "CALIB":    {"flat_key": "adc_calib",   "size": 1,  "type": "uint8",  "allowed": [0, 1],
                      "gui": {"label": "Calibrate?", "widget": "check", "default": 0,
                              "tooltip": "System is calibrated?"}},
        "CAL_STS":  {"flat_key": "adc_cal_sts", "size": 1,  "type": "uint8",  "allowed": [0, 1], "writable": False,
                      "gui": {"label": "Cal Status", "widget": "check", "default": 0,
                              "tooltip": "Status of Calibration"}},
        "SRATE":    {"flat_key": "adc_srate",   "size": 2,  "type": "uint16", "range":   (1024, 8192),
                      "gui": {"label": "Samples", "widget": "entry", "default": 1024,
                              "tooltip": "ADC Sampling Rate"}},
        "MSRATE":   {"flat_key": "adc_msrate",  "size": 2,  "type": "uint16", "range":   (1024, 16384), "writable": False,
                      "gui": None},
        "FRAGMENT": {"flat_key": "adc_fragment","size": 2,  "type": "uint16", "range":   (1024, 16384), "writable": False,
                      "gui": None},
        "CHANNEL":  {"flat_key": "adc_channels","size": 1,  "type": "uint8",  "range":   (1, 8),
                      "gui": {"label": "Channels", "widget": "entry", "default": 1,
                              "tooltip": "No of Geophone Channels"}},
        "NOTCH":    {"flat_key": "adc_notch",   "size": 1,  "type": "uint8",  "allowed": [0, 1],
                      "gui": None},
        "E_LEVEL":  {"flat_key": "adc_e_level", "size": 2,  "type": "uint16", "range":   (128, 32767),
                      "gui": {"label": "E_level(Cnt)", "widget": "entry", "default": 1024,
                              "tooltip": "Event Detection Threshold in ADC value (128 .. 32768)"}},
    },
    "FFS": {
        "STATUS": {"flat_key": "ffs_status", "size": 1,  "type": "uint8", "allowed": [0, 1],
                    "gui": None},
        "RD_FILE": {"flat_key": "ffs_rd_file", "size": 12,  "type": "string",
                      "gui": None},
        "RD_ALL": {"flat_key": "ffs_rd_all", "size": 1,  "type": "uint8", "allowed": [0, 1],
                      "gui": None},
        "CPYS2U": {"flat_key": "ffs_cpy_sd_to_usb", "size": 12,  "type": "string",
                      "gui": None},
        "CPYU2S": {"flat_key": "ffs_cpy_usb_to_sd", "size": 12,  "type": "string",
                      "gui": None},
        "DIR":    {"flat_key": "ffs_dir", "size": 1,  "type": "uint8", "allowed": [0, 1],
                      "gui": None},
        "SIZE":    {"flat_key": "ffs_size", "size": 1,  "type": "uint8", "allowed": [0, 1],
                      "gui": None},
        "DEL_FILE": {"flat_key": "ffs_del_file", "size": 12,  "type": "string",
                      "gui": None},
        "DEL_ALL": {"flat_key": "ffs_del_all", "size": 1,  "type": "uint8", "allowed": [0, 1],
                      "gui": None},
        "FORMAT": {"flat_key": "ffs_format", "size": 1,  "type": "uint8", "allowed": [0, 1],
                      "gui": None},
    },
}

#-------------------------------------------------------------------------------
class CommandHandler:
    def __init__(self, con_handler = None):
        self.con_handler = con_handler
        self.crc_handler = CRC_CCITT()

        connection_type = get_session_flag('connection')
        if connection_type == 'serial_port':
            self.serial_port = self.con_handler.serial_port
        else:
            self.serial_port  = connection_type
            self.rply_handler = CmdRplySimulation(self.serial_port)
        
        self.header_byte = CMD_HDR_ID

        # They are set when sending a command and then used to validate responses.
        self.module_name = None
        self.param_name  = None
        self.cmd_type    = None

        # Parameter details (set in send_command)
        self.param_size = 0
        self.param_type = None

        # Expected response length (set in send_command)
        self.response_expected_len = 0

    #-----------------------------------------------------------------------
    # check the group name and param keys are within limits
        if not self.check_cmd_lookup_key_lengths(CMD_TABLE):
            raise SystemExit("[FATAL] CMD_TABLE contains invalid key names. Fix and restart.")

#-------------------------------------------------------------------------------
# Simplified Remote SET helper
#-------------------------------------------------------------------------------
    def set_remote_value(self, key, module, param, value, description = "set parameter command"):
        try:
            reply = self.send_command(module, param, "CMD_SET", value)
            if not reply or len(reply) < 4:
                raise ValueError(f"Invalid or short response while setting {description}.")

            resp_code, _, _, _ = reply
            if resp_code != 0x00:  # CMD_ACK
                print(f"[SET_CMD] CMD_NAK received for {description} ({key})")
                logging.error(f"[SET_CMD] CMD_NAK received for {description} ({key})")
                raise ValueError(f"CMD_NAK received for {description} ({key})")

            return resp_code

        except Exception as e:
            print(f"[EXCEPTION] Failed to set remote {description} ({key}): {e}")
            logging.error(f"[SET_CMD] Exception during remote set of {description} ({param}): {e}")
            logging.debug(traceback.format_exc())
            return None

#-------------------------------------------------------------------------------
# Simplified Remote GET helper
#-------------------------------------------------------------------------------
    def get_remote_value(self, key, module, param, description = "get parameter"):
        try:
            reply = self.send_command(module, param, "CMD_GET")
            if not reply or len(reply) < 4:
                raise_key_error_msg(f"Invalid get reply of {key}->{module}->{param}")
                return None 

            resp_code, _, _, value = reply
            if resp_code != 0x00:
                raise_key_error_msg(f"Invalid response of {key} -> {reply}")
                return None 
                
            return value
            
        except Exception as e:
            raise_key_error_msg(f"[GET_CMD] Exception during get of {key}->{module}->{param}: {e}")
            return None 

#-------------------------------------------------------------------------------
    def send_command(self, module = None, param = None, cmd_type = None, value = None, simulation_mode = None):
        """
        Prepare and send a command frame.
        Args:
            module: Module name as string.
            param: Parameter name as string.
            cmd_type: Command type, one of CMD_SEND_LOOKUP keys ('CMD_SET' or 'CMD_GET').
            value: Value to set (required for CMD_SET).
            simulation_mode: If True, the command frame is returned without sending.
        Returns:
            In simulation_mode: the command frame bytes.
            Otherwise, the reply from maps_com.receive_rply() or parsed response.
        Raises:
            ValueError: On invalid module/parameter or missing value.
        """
        
        from common.core.sys_config import get_sys_value
        
        self.module_name = module
        self.param_name  = param
        serial_number    = get_sys_value("sys_ser_no")

        param_info      = CMD_TABLE[self.module_name][self.param_name]
        self.param_size = param_info["size"]
        self.param_type = param_info["type"]
        self.cmd_type   = cmd_type

        if self.cmd_type == "CMD_SET" and value is None:
            raise ValueError("SET command requires a value")

        # Calculate data length: module name + parameter name + parameter_size + (+ value bytes for SET)
        # parameter_size is added due to variable length of parameter name, at remote compare was failing
        # it will be one byte only to cover 255 bytes for  parameter name which is too much
        data_length = len(module.encode()) + 1 + len(param.encode())
        
        if self.cmd_type == "CMD_SET":
            data_length += self.param_size
            # # Validate value if CMD_SET or in CMD_GET response later
            # self.validate_data_frame(module, param, value)

        # Pack header: <BBHH: header byte, command type, data_length, serial_number
        frame = struct.pack("<BBHH", self.header_byte, CMD_SEND_LOOKUP.get(self.cmd_type), data_length, serial_number)

        # Compute CRC on header bytes and append it
        crc = self.crc_handler.compute_crc(frame, len(frame))
        frame += crc.to_bytes(CMD_CRC_SIZE, 'little')

        # Append module, parameter key(name) length and parameter (encoded as ASCII)
        frame += module.encode() + bytes([len(param)]) + param.encode()

        # Set expected response length based on command type
        self.response_expected_len = len(frame)
        
        if self.cmd_type == "CMD_GET":
            self.response_expected_len += self.param_size

        # Append value if CMD_SET
        if self.cmd_type == "CMD_SET":
            frame += self.encode_value(value)

        logging.info(f"Command Sent   : {frame.hex().upper()}")

        # In simulation mode, simply return the frame for inspection.
        if get_session_flag('connection') == 'simulation_port':
            response = self.rply_handler.generate_reply(serial_number, module, param, cmd_type, 'CMD_ACK', sent_value = value)
            return self.rcv_response(response)            
            # return frame

        # Otherwise, send the command and wait for a response.
        if self.con_handler.send_data(frame) is not None:
            # if session is on, different logic else old
            if get_session_flag('session'): 
                set_session_flag('cmd_waiting', True)  # Mark system as waiting for a command reply
                print("[INFO] Command sent successfully, waiting for response...")
                return True  # Command sent, response will be captured separately
                
            else:
                response = self.con_handler.receive_data(self.response_expected_len)
                return self.rcv_response(response)

        else:
            raise_key_error_msg("Failed to send command because serial_port is not available")
            return None

#-------------------------------------------------------------------------------
    def rcv_response(self, response):
        """
        Receives and validates response.
        Args:
            response: Received bytes from the remote system.
        Returns:
            For CMD_GET: a tuple (CMD_ACK, module, param, value) if successful.
            For CMD_SET: returns CMD_ACK for acknowledgment.
            On errors or CMD_NAK, returns None or the error response.
        """
        # first byte of response is Response Header ID
        if not response or response[0] != CMD_HDR_ID:  # 0x14:
            raise_key_error_msg("[RECV] Unexpected header id 0x{response[0]:02X} in resposne : {response.hex().upper()}")
            return None  # Ignore any non-command data
            
        logging.info(f"Reply Received : {response.hex().upper()}")

        # Check if response is complete
        if len(response) < self.response_expected_len:
            raise_key_error_msg(f"Incomplete response: Expected {self.response_expected_len}, got {len(response)}")
            return None

        try:
            # Verify CRC: compute on header portion and compare with received CRC
            received_crc   = response[CMD_CRC_IDX : (CMD_CRC_IDX + CMD_CRC_SIZE)]
            calculated_crc = self.crc_handler.compute_crc(response[0:CMD_CRC_IDX], CMD_CRC_IDX).to_bytes(CMD_CRC_SIZE, 'little')
            
            if received_crc != calculated_crc:
                raise_key_error_msg(f"CRC mismatch. Expected {calculated_crc.hex().upper()}, got {received_crc.hex().upper()}")
                return None

            # Check reply type in response header
            if response[CMD_TYPE_IDX]   == REPLY_TYPES['CMD_NAK']:
                logging.error("CMD_NAK received. Command is not decodable by remote.")
                return response

            elif response[CMD_TYPE_IDX] == REPLY_TYPES['CMD_ACK']:
                logging.info("CMD_ACK received. Command executed successfully")
                
                if self.cmd_type == "CMD_SET":
                    # For SET command, no further data to parse.
                    return (REPLY_TYPES.get('CMD_ACK'), self.module_name, self.param_name, None)
                else:
                    # For GET command, extract the value from response data.
                    return self.parse_response(response[CMD_DATA_IDX:])

        except Exception as e:
            raise_key_error_msg(f"CommandHandler.rcv_response failed: {e}")
            return None
        
#-------------------------------------------------------------------------------
    def parse_response(self, data: bytes):
        """
        Extracts module, parameter, and value from the received data.
        Args:
            data: Raw bytes from the response (after header and CRC).
        Returns:
            Tuple (CMD_ACK, module, param, decoded_value).
        """
        mod_len = len(self.module_name.encode())
        par_len = len(self.param_name.encode())
        response_module = data[0 : mod_len].decode() # name
        
        # Sliced by 1+mod_len, because between module name and parameter name, 
        # one byte is parameter name legth and need to strip for processing data
        data = data[(mod_len + 1) :] # move to param starting
        
        response_param = data[0 : par_len].decode() # name
        value_bytes    = data[par_len : par_len + self.param_size]
        
        # crc_bytes = None
        # if response_param in ("FW_VER",):     # tuple allows easy extension
            # crc_bytes   = value_bytes[-2: ]   # pass this to validator, keep this order
            # value_bytes = value_bytes[ :-2]   # skip CRC

        if value_bytes is not None and len(value_bytes):
            decoded_value = self.decode_value(value_bytes)

            # Validate the response module and parameter match what was sent.
            self.validate_rcv_data_frame(response_module, response_param, decoded_value)

            return (REPLY_TYPES.get('CMD_ACK'), response_module, response_param, decoded_value)
            
        else:
            raise_key_error_msg("value_bytes is None or length is zero")
            return None

#-------------------------------------------------------------------------------
    def get_expected_response_size(self) -> int:
        return self.response_expected_len

#-------------------------------------------------------------------------------
    def encode_value(self, value: int | float | str) -> bytes:
        """
        Encodes the value based on parameter type.
        Args:
            value: Value to encode.
        Returns:
            Encoded bytes.
        """
        if self.param_type in ["int8", "int16", "int32","uint8", "uint16", "uint32"]:
            return value.to_bytes(self.param_size, byteorder = "little")
        elif self.param_type in ["ascii", "string"]:
            encoded = value.encode('ascii')
            if len(encoded) > self.param_size:
                # Truncate but log warning
                print(f"[WARN] String '{value}' too long for {self.param_size} bytes. Truncating.")
                logging.warning(f"[WARN] String '{value}' too long for {self.param_size} bytes. Truncating.")
                encoded = encoded[:self.param_size]
            return encoded.ljust(self.param_size, b'\x00')

        elif self.param_type == "float":
            return struct.pack("<f", value)
        else:
            raise_key_error_msg(f"Unsupported param_type: {self.param_type}")

#-------------------------------------------------------------------------------
    # def decode_value(self, value: bytes):
    def decode_value(self, value: bytes) -> int | float | str:
        """
        Decodes a byte sequence based on the parameter type.

        Args:
            value: Byte sequence to decode.
        Returns:
            Decoded value.
        """
        dtype = self.param_type
        if dtype.startswith("int") or dtype.startswith("uint"):
            return int.from_bytes(value, byteorder = "little")
        if dtype in ["ascii", "string"]:
            return value.decode('ascii').rstrip('\x00')
        if self.param_type == "float":
            return struct.unpack("<f", value)[0]
        if dtype == "bytes":
            return value
        
        raise_key_error_msg(f"Unsupported param_type: {self.param_type}")
        return None

#-------------------------------------------------------------------------------
    def validate_rcv_data_frame(self, module, param, value):
        """
        Validates module, parameter, and value against CMD_TABLE.
        Used for receiving data only.
        Args:
            module: Module name.
            param: Parameter name.
            value: Value to validate (if applicable).
        Raises:
            ValueError if validation fails.
        """
        
        # Validate incoming response
        if module != self.module_name or param != self.param_name:
            raise_key_error_msg(f"Mismatch: expected {self.module_name}.{self.param_name}, got {module}.{param}")
            return None
            
        if module not in CMD_TABLE or param not in CMD_TABLE[module]:
            raise_key_error_msg(f"[CMD_TABLE] Invalid module/param: {module}.{param}")
            return None
            
        result = validate_param_value(module, param, value)
        
        return result
        
#-------------------------------------------------------------------------------
    # Get module name from param (used for GET/SET helpers)
#-------------------------------------------------------------------------------
    @staticmethod
    def get_module_from_param(param):
        for module, params in CMD_TABLE.items():
            if param.upper() in params:
                return module
        raise ValueError(f"Module not found for parameter '{param}'")

#-------------------------------------------------------------------------------
    # Normalize user-entered value (YES/NO, True/False, "1"/"0")
#-------------------------------------------------------------------------------
    @staticmethod
    def normalize_value1(param, value):
        """
        Normalize mixed user-entered or file-loaded values:
        - Supports boolean aliases (YES/NO, TRUE/FALSE)
        - Integer and float parsing
        - Raw string passthrough (e.g., for version info)
        - Preserves case for strings (e.g., 'V1.2')
        - Accepts bytes directly
        """
        if isinstance(value, bytes):
            return value  # e.g., b'V12A'

        if isinstance(value, str):
            stripped = value.strip()
            lowered = stripped.lower()

            # --- Boolean normalization ---
            if lowered in ['yes', 'true', '1']:
                return 1
            elif lowered in ['no', 'false', '0']:
                return 0

            # --- Integer check ---
            if stripped.isdigit():
                return stripped

            # --- Default fallback: treat as text (preserve case) ---
            return stripped

        if isinstance(value, bool):
            return int(value)

        if isinstance(value, int) or isinstance(value, float):
            return value

        # --- Add other types (e.g., list, dict) as needed ---
        raise ValueError(f"[NORMALIZE] Unrecognized value type for param '{param}': {type(value).__name__}")

#-------------------------------------------------------------------------------
    # Validate value against allowed list or range from CMD_TABLE
#-------------------------------------------------------------------------------
    def validate_or_adjust_value(self, param, value, strict = True):
        """Validate or adjust value based on CMD_TABLE rules.
        Returns validated or adjusted value.
        Raises ValueError only if strict = True and unrecoverable.
        """
        def fail(msg, fallback = None):
            print(f"[VALIDATE] {msg}")
            logging.warning(msg)
            if strict:
                raise ValueError(msg)
            return fallback

        # Locate param spec
        spec = None
        for module_spec in CMD_TABLE.values():
            if param in module_spec:
                spec = module_spec[param]
                break

        if not spec:
            return value  # Unknown param, accept as-is

        # Normalize
        try:
            value = self.normalize_value(param, value)
        except Exception as e:
            return fail(f"{param} value normalization failed: {e}", fallback=None)

        expected_type = spec.get("type", "string")

        # ---- STRING ----
        if expected_type == "string":
            if not isinstance(value, str):
                return fail(f"{param} expects string, got {type(value).__name__}", fallback=None)

            if "pattern" in spec:
                if not re.fullmatch(spec["pattern"], value):
                    return fail(f"{param} value '{value}' does not match pattern {spec['pattern']}", fallback=None)

            if "allowed" in spec:
                if value in spec["allowed"]:
                    return value
                adjusted = spec["allowed"][0]
                return fail(f"{param} = {value} not allowed, using {adjusted}", fallback=adjusted)

            return value

        # ---- FLOAT ----
        elif expected_type == "float":
            if not isinstance(value, float):
                return fail(f"{param} expects float, got {type(value).__name__}", fallback=None)
            if "range" in spec:
                low, high = spec["range"]
                if low <= value <= high:
                    return value
                return fail(f"{param} = {value} out of range [{low}-{high}], using {low}", fallback=low)
            return value

        # ---- INTEGER TYPES (signed/unsigned) ----
        elif expected_type.startswith("int") or expected_type.startswith("uint"):
            if not isinstance(value, int):
                return fail(f"{param} expects int, got {type(value).__name__}", fallback = None)

            if "allowed" in spec:
                if value in spec["allowed"]:
                    return value
                adjusted = min(spec["allowed"])
                return fail(f"{param} = {value} not allowed, using {adjusted}", fallback=adjusted)

            if "range" in spec:
                low, high = spec["range"]
                if low <= value <= high:
                    return value
                return fail(f"{param} = {value} out of range [{low}-{high}], using {low}", fallback=low)

            return value

        # ---- BYTES ----
        elif expected_type == "bytes":
            if not isinstance(value, (bytes, bytearray)):
                return fail(f"{param} expects byte string, got {type(value).__name__}", fallback=None)
            expected_size = spec.get("size", None)
            if expected_size and len(value) != expected_size:
                return fail(f"{param} expects {expected_size} bytes, got {len(value)}", fallback=None)
            return value

        else:
            return fail(f"{param} has unknown type '{expected_type}'", fallback = None)

#-------------------------------------------------------------------------------
    def check_cmd_lookup_key_lengths(self, cmd_lookup: dict) -> bool:
        """
        Ensures CMD_TABLE keys conform to firmware limits:
        - Group keys: ≤ 3 alphanumeric chars
        - Param keys: ≤ 9 alphanumeric chars
        """
        all_ok = True
        for group, params in cmd_lookup.items():
            if not re.fullmatch(r"[A-Za-z0-9]{1,3}", group):
                raise_key_error_msg(f"[ERROR] Group key '{group}' invalid - must be = 3 alphanumeric chars (no underscore).")
                all_ok = False

            for param in params:
                if not re.fullmatch(r"[A-Za-z0-9_]{1,9}", param):
                    raise_key_error_msg(f"[ERROR] Param key '{param}' in group '{group}' invalid - must be = 9 chars (alnum or underscore).")
                    all_ok = False

        if all_ok:
            log_info_msg("CMD_TABLE key validation passed.", do_print = False)
            
        return all_ok

#-------------------------------------------------------------------------------
    def is_param_writable(self, param_name):
        """Check if a remote parameter is writable, default is True."""
        for module_spec in CMD_TABLE.values():
            if param_name in module_spec:
                return module_spec[param_name].get("writable", True)
        return True  # Default if not explicitly marked

#-------------------------------------------------------------------------------
class CmdRplySimulation:
    def __init__(self, cmd_handler):
        """
        Initialize CmdRplySimulation with a CRC handler and a CommandHandler.
        """
        logging.basicConfig(level = logging.INFO)
        self.crc_handler = CRC_CCITT()
        self.cmd_handler = cmd_handler
        self.header_byte = CMD_HDR_ID
        self.output_file = "simulated_commands.txt"
        self.init_output_file()

    def init_output_file(self):
        try:
            with open(self.output_file, "w") as f:
                f.write("Simulation Started...\n\n")
        except Exception as e:
            logging.error(f"Failed to initialize simulation output file: {e}")
            
    def save_simulation_entry(self, cmd_desc, response_frame):
        try:
            with open(self.output_file, "a") as f:
                f.write(cmd_desc + "\n")
                # f.write(f"Command Sent   : {cmd_frame.hex().upper()}\n")
                # f.write(f"Expected Reply : {expected_reply.hex().upper()}\n")

                if isinstance(response_frame, bytes):
                    f.write(f"INFO: Received Frame -> {response_frame.hex().upper()}\n")
                else:
                    f.write(f"INFO: Received Frame -> {str(response_frame)}\n")

                f.write("\n")
        except Exception as e:
            logging.error(f"Failed to save simulation entry: {e}")

    def save_simulation_multiple_entry(self, cmd_desc, cmd_frame, expected_reply, response_frame):
        try:
            with open(self.output_file, "a") as f:
                f.write(cmd_desc + "\n")
                f.write(f"Command Sent   : {cmd_frame.hex().upper()}\n")
                f.write(f"Expected Reply : {expected_reply.hex().upper()}\n")

                if isinstance(response_frame, bytes):
                    f.write(f"Received Frame : {response_frame.hex().upper()}\n")
                else:
                    f.write(f"Received Frame : {str(response_frame)}\n")

                f.write("\n")
        except Exception as e:
            logging.error(f"Failed to save simulation entry: {e}")

    def save_simulation_entry_unicode(self, cmd_desc, cmd_frame, expected_reply, response_frame):
        try:
            with open("simulated_commands.txt", "a", encoding="utf-8") as f:
                f.write("-" * 70 + "\n")

                # Force string and escape encoding issues
                f.write(f"Command Type   : {str(cmd_desc)}\n")

                # Handle binary command frame
                if isinstance(cmd_frame, bytes):
                    f.write(f"Command Sent   : {cmd_frame.hex().upper()}\n")
                else:
                    f.write(f"Command Sent   : {str(cmd_frame)}\n")

                # Handle expected reply
                if isinstance(expected_reply, bytes):
                    f.write(f"Expected Reply : {expected_reply.hex().upper()}\n")
                else:
                    f.write(f"Expected Reply : {str(expected_reply)}\n")

                # Handle actual response (can be tuple or bytes)
                if isinstance(response_frame, bytes):
                    f.write(f"Received Frame : {response_frame.hex().upper()}\n")
                else:
                    f.write(f"Received Frame : {str(response_frame)}\n")

                f.write("\n")

        except Exception as e:
            logging.error(f"Simulation save error: {e}")

    def get_valid_test_value(self, module, param):
        info = CMD_TABLE[module][param]
        if "range" in info:
            return info["range"][0]
        elif "allowed" in info and info["allowed"]:
            return info["allowed"][0]
        return None
        
    def generate_reply(self, serial_number, module, param, cmd_type, reply_type, sent_value = None):
        """
        Generates a simulated reply for a given command.
        Args:
            serial_number: Serial number.
            module: Module name.
            param: Parameter name.
            cmd_type: Command type ('CMD_SET' or 'CMD_GET').
            reply_type: Reply type (e.g., 'CMD_ACK' or 'CMD_NAK').
            sent_value: Value sent in CMD_SET (optional).
        Returns:
            Simulated reply frame as bytes.
        """
        if module not in CMD_TABLE or param not in CMD_TABLE[module]:
            return None

        param_info = CMD_TABLE[module][param]
        param_size = param_info["size"]

        # Calculate data length: module name + byte to store length of parameter name + parameter name (+ value for GET)
        data_length = len(module.encode()) + 1 + len(param.encode())
        
        if cmd_type == 'CMD_GET':
            if sent_value is not None:
                # For a GET command, if a value is provided, use it.
                param_bytes = sent_value.to_bytes(param_size, 'little')
            elif "range" in param_info:
                # Otherwise, use midpoint of the range.
                param_value = (param_info["range"][0] + param_info["range"][1]) // 2
                param_bytes = param_value.to_bytes(param_size, 'little')
            elif "allowed" in param_info:
                # param_bytes = param_info["allowed"][0].to_bytes(param_size, 'little')
                first_allowed = param_info["allowed"][0]
                if isinstance(first_allowed, str):
                    str_bytes = first_allowed.encode("utf-8")
                    param_bytes = str_bytes.ljust(param_size, b'\x00')[:param_size]
                else:
                    param_bytes = first_allowed.to_bytes(param_size, 'little')                

            elif "pattern" in param_info:
                # Generate a 6-digit numeric string (e.g., today's date as YYMMDD)
                date_str = datetime.now().strftime('%y%m%d')  # 6 digits
                param_bytes = date_str.encode("utf-8")

                # Ensure it's padded or truncated to param_size
                if len(param_bytes) < param_size:
                    param_bytes = param_bytes.ljust(param_size, b'\x00')
                else:
                    param_bytes = param_bytes[:param_size]
            else:
                param_bytes = b"\x00" * param_size

            data_length += param_size

        # Pack header for the reply
        header = struct.pack("<BBHH", self.header_byte, REPLY_TYPES[reply_type], data_length, serial_number)
        crc = self.crc_handler.compute_crc(header, len(header))
        header += crc.to_bytes(CMD_CRC_SIZE, 'little')

        # Build reply frame: header + module + size of number of chars in parameter + parameter
        key_len = len(param)
        reply_frame = header + module.encode() + bytes([key_len]) + param.encode()
        
        if cmd_type == 'CMD_GET':
            reply_frame += param_bytes

        return reply_frame

    def simulate_all_commands(self, serial_port, serial_number):
        """
        Iterates through all commands defined in CMD_TABLE, sends them via CommandHandler,
        and simulates replies.
        Args:
            serial_port: Serial port object to be passed to CommandHandler.
            serial_number: Serial number for the commands.
        """
        
        log_file = "simulated_commands.txt"
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
            for reply_key in REPLY_TYPES:
                for module, params in CMD_TABLE.items():
                    for param, param_info in params.items():
                        for cmd_type in CMD_SEND_LOOKUP:
                            sent_value = self.get_valid_test_value(module, param)
                            if cmd_type == "CMD_SET" and sent_value is None:
                                logging.info(f"[CMD_SET] {module}->{param}, Value -> {sent_value}")
                                continue  # Skip if no valid test value

                            # Generate simulated reply
                            try:
                                expected_reply = self.generate_reply(serial_number, module, param, cmd_type, reply_key,
                                                                   sent_value if cmd_type == "CMD_SET" else None)
                            except Exception as e:
                                logging.error(f"Failed to generate reply for {module}->{param}: {e}")
                                continue
                                
                            cmd_desc = (f"INFO: {cmd_type} -> module -> {module}, Parameter -> {param}")
                            # Send command in simulation mode (returns the command frame)
                            command_frame = self.cmd_handler.send_command(serial_port, serial_number, module, param, cmd_type,
                                                                          sent_value, simulation_mode = True)
                            # Directly simulate receiving the expected reply.
                            response_frame = self.cmd_handler.rcv_response(expected_reply)

                            # self.save_simulation_entry(cmd_desc, response_frame)

                            # Log details
                            # if command_frame:
                                # logging.info(f"[SIM_CMD] {cmd_type} {module}->{param} = {command_frame.hex().upper()}")
                            # else:
                                # logging.error(f"Failed to send {cmd_type} for {module}->{param}")

                            if response_frame:
                                # For GET, response_frame includes the parsed value in tupple;
                                # for SET, it's an acknowledgment tuple.
                                if isinstance(response_frame, tuple):
                                    # INFO: Received reply for CMD_SET->ADC->SRATE->CMD_ACK: (0, 'ADC', 'SRATE', None)
                                    logging.info(f"Reply Received : {cmd_type}->{module}->{param}->{reply_key}: {response_frame}\n")

                                    # logging.info(f"Simulated reply for {module}->{param} ({reply_key}): {response_frame}")
                                else:
                                    logging.info(f"Reply Received : {cmd_type}->{module}->{param}->{reply_key}: {response_frame.hex().upper()}\n")
                                    # logging.info(f"Simulated reply for {module}->{param} ({reply_key}): {response_frame.hex().upper()}")
                            else:
                                logging.error(f"Failed to receive reply for {cmd_type} on {module}->{param}")

        finally:
            logging.info("Simulation completed...")
            # Remove handler after simulation ends
            logger.removeHandler(file_handler)
            file_handler.close()
			# Restore previous console handlers
            for h in original_handlers:
                logger.addHandler(h)
                
#-------------------------------------------------------------------------------
# Example Usage
if __name__ == "__main__":
    # Example serial port, replace with an actual serial port instance in real use.
    # For simulation, you can use a dummy object or mock.
    class DummySerial:
        pass

    dummy_serial = DummySerial()
    sys_ser_no = 1234    # Example Serial Number, 0x04D2

    set_session_flag('connection', 'simulation_port')
    cmd_handler = CommandHandler(dummy_serial)
    sim_handler = CmdRplySimulation(cmd_handler)

    # Set simulation mode: simulate all commands.
    print("Simulation Started...")
    sim_handler.simulate_all_commands(dummy_serial, sys_ser_no)
    print("Simulation completed...")
