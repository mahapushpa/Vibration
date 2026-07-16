import  re
import  sys
import  math
import  logging
import  traceback
import  numpy as np
from    datetime import datetime

#-------------------------------------------------------------------------------
from vibmshared.core.common import channel_to_sensor, sensor_to_unit

#-------------------------------------------------------------------------------
class LogWrapper:
    def __init__(self, log_handler=None):
        """
        Wrapper to bridge GUI and standard logging.
        Args:
            log_handler: Optional GUI log handler with .log(msg, tag) method.
        """
        
        self.log_handler = log_handler

    def log(self, message, tag="info"):
        if self.log_handler:
            self.log_handler.log(message, tag=tag)
        else:
            if tag == "info":
                logging.info(message)
            elif tag == "warning":
                logging.warning(message)
            elif tag == "error":
                logging.error(message)
            elif tag == "critical":
                logging.critical(message)
            elif tag == "debug":
                logging.debug(message)                
            else:
                print(message)

#-------------------------------------------------------------------------------
def safe_log(log_handler, message: str, tag: str = "info", do_print = False):
    """Logs a message using either the GUI log handler or standard logging."""
    # If a valid GUI log_handler is passed, use it
    if log_handler:
        log_handler.log(message, tag = tag)

    if do_print:
        print(message)
        
    if tag == "debug":
        logging.debug(message)
    elif tag == "warning":
        play_audio('warning')
        logging.warning(message)
    elif tag == "error":
        play_audio('error')
        logging.error(message)
    elif tag == "critical":
        play_audio('error')
        logging.critical(message)
    else:
        logging.info(message)
                
#-------------------------------------------------------------------------------
def log_info_msg(msg, do_print = False):
    """Do print, log.
    Args:
        msg (str): Error message.
        do_print (bool): Whether to also print to console.
    Returns:
        None
    """
    from vibmshared.core.sys_config import get_sys_value
    logging.info(msg)
    if do_print:
        print(msg)
     
#-------------------------------------------------------------------------------
def report_key_error(msg, result = False, do_print = True):
    """Report a key/value error: raises KeyError in debug mode, logs and
    returns `result` otherwise.
    Args:
        msg (str): Error message.
        result: Value to return when not raising (production mode).
        do_print (bool): Whether to also print to console.
    Returns:
        `result` in production mode; raises KeyError in debug mode (no return).
    """
    from vibmshared.core.sys_config import get_sys_value

    logging.error(f"{msg}")

    if do_print:
        print(f"[ERROR] {msg}, skipping")

    if get_sys_value('debug_mode'):
        logging.debug(traceback.format_exc())
        raise KeyError(f"[ERROR] {msg}")
    else:
        return result

#-------------------------------------------------------------------------------
def validate_param_value(module, param, value_raw):
    """
    Unified validator and normalizer for remote command keys.
    Args:
        module - e.g., 'ADC'
        param - e.g., 'SRATE'
        value_raw - input value from user or widget (string, int, etc.)
    Returns:
        (success: bool, value: normalized on success, original value_raw on failure)
    """

    from vibmshared.modules.cmd_remote import CMD_TABLE

    param_info    = CMD_TABLE[module][param]
    expected_type = param_info.get("type", "string")

    try:
        # Step 1: Clean string inputs (if string-like)
        if isinstance(value_raw, str):
            cleaned = value_raw.strip()
        else:
            cleaned = value_raw  # native types

        # Step 2: Convert based on expected type
        if expected_type.startswith("int") or expected_type.startswith("uint"):
            value = int(cleaned)
            if "range" in param_info:
                lo, hi = param_info["range"]
                if not (lo <= value <= hi):
                    report_key_error(f"{value} out of range [{lo}-{hi}] for {module}:{param}")
                    return False, value_raw
            if "allowed" in param_info and value not in param_info["allowed"]:
                report_key_error(f"{value} not allowed for {module}:{param}")
                return False, value_raw

        elif expected_type == "float":
            value = float(cleaned)
            if "range" in param_info:
                lo, hi = param_info["range"]
                if not (lo <= value <= hi):
                    report_key_error(f"{value} out of range [{lo}-{hi}] for {module}:{param}")
                    return False, value_raw

        elif expected_type == "string":
            value = str(cleaned)
            if "pattern" in param_info and not re.fullmatch(param_info["pattern"], value):
                report_key_error(f"{value} does not match pattern for {module}:{param}")
                return False, value_raw
            if "size" in param_info and len(value) > param_info["size"]:
                report_key_error(f"{value} too long (max {param_info['size']}) for {module}:{param}")
                return False, value_raw
            if "allowed" in param_info and value not in param_info["allowed"]:
                report_key_error(f"{value} not allowed for {module}:{param}")
                return False, value_raw

        elif expected_type == "bytes":
            if not isinstance(cleaned, (bytes, bytearray)):
                report_key_error(f"Expected bytes for {module}:{param}, got {type(cleaned).__name__}")
                return False, value_raw
            if "size" in param_info and len(cleaned) > param_info["size"]:
                report_key_error(f"{len(cleaned)} bytes too long (max {param_info['size']})")
                return False, value_raw

            value = cleaned  # no conversion

        else:
            report_key_error(f"Unsupported type '{expected_type}' for {module}:{param}")
            return False, value_raw

    except Exception as e:
        report_key_error(f"Validation failed for {module}:{param} - {e}")
        return False, value_raw

    logging.debug(f"Validated {module}.{param} -> {value} (type={expected_type})")
    return True, value
  
#-------------------------------------------------------------------------------
def validate_module_param(key, module, param, description = "Validate Module and Parameter"):
    """
    Unified validator for remote command keys.
    Args:
        key (str): user-facing config key (e.g., 'adc_srate')
        module, param (str): (e.g., SYS, FW_VER)
        description (str): optional logging/debug description
    Returns:
        success success (bool) (True or False)
    """
    from vibmshared.modules.cmd_remote    import CMD_TABLE

    # Validate module and parameter in CMD_TABLE
    if module not in CMD_TABLE or param not in CMD_TABLE[module]:
        return report_key_error(f"[CMD_TABLE] Invalid module/param: {module}.{param} of {key}")

    return True

#-------------------------------------------------------------------------------
def get_sensor_unit_factor(unit = None):
    """Convert ADC counts to physical units based on sensor specs."""

    from vibmshared.core.sys_config import get_sys_value
    
    gravity     = 9.8          # m/s²
    sensitivity = 28.8          # V/m/s (velocity sensitivity of geophone)
    adc_lsb_uv  = 152.59        # ADC step size in microvolts
    frequency   = get_sys_value('brd_geo_nat_freq', default = 10)  # Hz

    # Precompute useful constants
    adc_lsb_v = adc_lsb_uv / 1_000_000   # Convert to Volts
    adc_mV_in_bit  = adc_lsb_uv / 1000   # microvolts -> millivolts
    adc_vel_in_bit = adc_lsb_v / sensitivity  # Volts -> (V/m/s) -> (m/s)
    adc_acc_in_bit = adc_vel_in_bit * (2 * math.pi * frequency)  # a = v * omega

    if unit == 'MV':
        factor = adc_mV_in_bit
    elif unit == 'VEL':
        factor = adc_vel_in_bit
    elif unit == 'ACC':
        factor = adc_acc_in_bit
    elif unit == 'CNT':
        factor = 1
    else:
        safe_log(None, f"Unknown sensor unit requested: {unit}", tag = "error", do_print = True)
        raise ValueError(f"Unknown unit type '{unit}'. Valid: 'MV', 'VEL', 'ACC', 'CNT'. ")

    safe_log(None, f"Input Signal unit : {unit}", do_print = True)
    return factor
    
#-------------------------------------------------------------------------------
def get_sensor_unit(sensor_name: str) -> str:
    """Returns unit label for the given sensor name."""
    return sensor_to_unit.get(sensor_name, 'unit?')

# ------------------------------------------------------------------------------
def get_channel_sensor_unit(channel_no: int) -> str:
    """Returns the unit label for a specific channel."""
    sensor_name = channel_to_sensor.get(channel_no, {}).get('name', 'unknown')
    return get_sensor_unit(sensor_name)

#-------------------------------------------------------------------------------
def format_filter_description():
    """
    Return a description string for all selected filters.
    """
    from vibmshared.core.parameters import FilterParams

    selected = FilterParams.get_selected()
    parts = []

    for name in selected:
        params = FilterParams.filters.get(name)
        if not params:
            continue  # skip unknown or removed filter types

        if name == 'highpass':
            parts.append(f"HPF @ {params['cutoff_frequency']} Hz, Order = {params['order']}")
        elif name == 'lowpass':
            parts.append(f"LPF @ {params['cutoff_frequency']} Hz, Order = {params['order']}")
        elif name == 'notch':
            parts.append(f"Notch @ {params['frequency']} Hz, (Q={params['quality_factor']})")
        else:
            parts.append(f"{name} filter")

    return ", ".join(parts) if parts else "None"

#-------------------------------------------------------------------------------
def get_analysis_summary(metadata):
    """Extract summary block from metadata for GUI/report use."""
    keys = ["Analysis Type", "Analysis Method", "Analysis Freq", "Isolation Frequency", "Tool Version"]
    return {k: metadata.get(k, "N/A") for k in keys}

def extract_metadata_summary(metadata_blocks, keys = None, label_map = None, as_string = False, sep = " | "):
    """
         summary_line = extract_metadata_summary(
            metadata_blocks = [data_block, process_block],
            keys = ["Analysis Type", "Analysis Freq", "Tool Version"],
            label_map = {"Analysis Type": "Type", "Analysis Freq": "Range"},
            as_string = True
        )
    -> "Type: Displacement Transmissibility | Range: 1.0 Hz – 100.0 Hz | Tool Version: TF Toolkit v1.2"
    combined all the data
    summary = extract_metadata_summary(
        [data_block, input_block, process_block],
        as_string = True
    )
    """    
    if not isinstance(metadata_blocks, list):
        metadata_blocks = [metadata_blocks]

    # Combine all metadata dicts into one (last one wins)
    combined = {}
    for block in metadata_blocks:
        combined.update(block)

    # If keys not given, use all available from the first block
    if keys is None:
        keys = list(combined.keys())

    # Extract selected and rename if needed
    summary = {}
    for key in keys:
        display_key = label_map.get(key, key) if label_map else key
        summary[display_key] = combined.get(key, "N/A")

    if as_string:
        return sep.join(f"{k}: {v}" for k, v in summary.items())
    return summary

#-------------------------------------------------------------------------------
def format_metadata_block(title, meta_dict):
    lines = [
        "-" * 80,
        f" {title}",
        "-" * 80
    ]
    for key, val in meta_dict.items():
        lines.append(f" {key:<16}: {val}")
    return lines

#-------------------------------------------------------------------------------
def write_metadata_header(f, title, meta_dict):
    lines = format_metadata_block(title, meta_dict)
    f.write('\n'.join(lines) + '\n')

#-------------------------------------------------------------------------------
def write_channel_metadata_block(f, csv_mode: bool):
    """
    Write detailed sensor/channel metadata to the given file handle.

    Args:
        f (file): File handle (opened in write mode).
        n_channels (int): Number of channels.
        csv_mode (bool): True for CSV format, False for aligned TXT format.
    """
    from vibmshared.core.sys_config import get_sys_value
    
    f.write("-" * 80 + "\n")
    f.write(" Channel Information\n")
    f.write("-" * 80 + "\n")
    
    n_channels = get_sys_value('adc_channels')

    if csv_mode:
        f.write(" Channel No, Sensor Name, Unit, Description\n")
        for ch in range(n_channels):
            info = channel_to_sensor.get(ch, {})
            sensor_name = info.get('name', 'unknown')
            unit = get_sensor_unit(sensor_name)
            desc = info.get('description', 'N/A')
            line = f" Channel {ch+1}, {sensor_name}, {unit}, {desc}"
            f.write(line + "\n")
    else:
        f.write(f" Channel No -> {'Sensor Name':<15} -> {'Unit':<8} -> Description\n")
        for ch in range(n_channels):
            info = channel_to_sensor.get(ch, {})
            sensor_name = info.get('name', 'unknown')
            unit = get_sensor_unit(sensor_name)
            desc = info.get('description', 'N/A')
            line = f" Channel {ch+1:<2} -> {sensor_name:<15} -> {unit:<8} -> {desc}"
            f.write(line + "\n")

    f.write("-" * 80 + "\n")

#-------------------------------------------------------------------------------
def write_table_block(f, rows, headers, csv_mode = False, precision = 3):
    if csv_mode:
        f.write(",".join(headers) + "\n")
        f.write("-" * 80 + "\n")
        for row in rows:
            f.write(",".join(f"{val:.{precision}f}" if isinstance(val, float) else str(val) for val in row) + "\n")
    else:
        n_cols = len(rows[0])      # Total columns: 1 freq + 1 input + M outputs + M TFs
        r = (n_cols - 2) // 2      # Number of receiver channels
        t = r + 2                  # 2 -> input + freq

        col_widths = [10] * t + [10] * r
        
        f.write("".join(f"{h:^{w}}" for h, w in zip(headers, col_widths)) + "\n")
        f.write("-" * 80 + "\n")
        for row in rows:
            formatted = [
                f"{val:^{w}.{precision}f}" if isinstance(val, float) else f"{val:^{w}}"
                for val, w in zip(row, col_widths)
            ]
            f.write("".join(formatted) + "\n")

#-------------------------------------------------------------------------------
def generate_filename(prefix = 'tf', timestamp = None, ext = None):
    """
    Generate a timestamped filename.

    Parameters:
        prefix (str): File prefix like 'tf', 'event', etc.
        timestamp (datetime|str|None): datetime object or '%y%m%d_%H%M%S' string.
                                       If None, uses current time.
        ext (str|None): Optional extension (without dot). If provided, adds '.ext'

    Returns:
        str: Filename like 'tf_250514_121530.txt'
    """
    from datetime import datetime

    if timestamp is None:
        timestamp = datetime.now()
    elif isinstance(timestamp, str):
        # Assume it's already in '%y%m%d_%H%M%S' format
        return f"{prefix}_{timestamp}.{ext}" if ext else f"{prefix}_{timestamp}"
    elif isinstance(timestamp, datetime):
        timestamp = timestamp
    else:
        raise ValueError("timestamp must be None, datetime, or formatted str")

    name = f"{prefix}_{timestamp.strftime('%y%m%d_%H%M%S')}"
    return f"{name}.{ext}" if ext else name

#-------------------------------------------------------------------------------
def validate_sample_rate(srate):
    power_of_two = is_power_of_two(srate)
    corrected = srate
    if not power_of_two:   # correct to nearest lower
        corrected = nearest_power_of_two(srate)
        # srate = lower_nearest_power_of_two(srate)
    return power_of_two, corrected
    
#-------------------------------------------------------------------------------
def nearest_power_of_two(n):
    """Return the power of 2 closest to n (break ties toward higher)."""
    if n < 2:
        return 2
    lower = 1 << (n.bit_length() - 1)
    upper = 1 << n.bit_length()
    return lower if n - lower < upper - n else upper

#-------------------------------------------------------------------------------
def is_power_of_two(n):
    return n and (n & (n - 1) == 0)

#-------------------------------------------------------------------------------
def lower_nearest_power_of_two(n):
    # Nearest lower power of 2
    return (1 << (n.bit_length() - 1))

def upper_nearest_power_of_two(n):
    # Nearest upper power of 2
    return 1 << (n - 1).bit_length()

#-------------------------------------------------------------------------------
def get_single_label_from_valid(settings, key_or_index):
    """
    Get a single label from a settings list or dict.
    
    - If settings is a dict: key_or_index must be a key -> returns value
    - If settings is a list/tuple: key_or_index must be an index -> returns item
    label = get_single_label_from_valid(WindowParams.settings, 2)
    print(label)  # ➔ 'blackman'
    label = get_single_label_from_valid(TransformParams.settings, 'SFFT')
    print(label) # ➔ 'Short-Time Fourier Transform'
    """
    if isinstance(settings, dict):
        if key_or_index not in settings:
            raise KeyError(f"Key '{key_or_index}' not found in settings dictionary.")
        return settings[key_or_index]
    
    elif isinstance(settings, (list, tuple)):
        if not (0 <= key_or_index < len(settings)):
            raise IndexError(f"Index {key_or_index} out of range for settings list.")
        return settings[key_or_index]
    
    else:
        raise TypeError("settings must be a list, tuple, or dict")

#-------------------------------------------------------------------------------
def get_all_labels_from_valid(settings):
    """
    Get user-facing labels from a settings list or dict.
    
    - If input is a list: returns the list itself
    - If input is a dict: returns the dict.values() (pretty names)
    labels = get_labels_from_valid(WindowParams.settings)
    print(labels)
    # ➔ ['hann', 'hamming', 'blackman', 'bartlett', 'None']
    labels = get_labels_from_valid(TransformParams.settings)
    print(labels)
    # ➔ ['Fast Fourier Transform', 'Short-Time Fourier Transform']
    
    """
    if isinstance(settings, dict):
        return list(settings.values())
    elif isinstance(settings, (list, tuple)):
        return list(settings)
    else:
        raise TypeError("settings must be a list, tuple, or dict")

#-------------------------------------------------------------------------------
def is_true(value):
    return str(value).strip().lower() in ['1', 'true', 'yes', 'on']
    
#-------------------------------------------------------------------------------
def is_false(value):
    return str(value).strip().lower() in ['0', 'false', 'no', 'off']

#-------------------------------------------------------------------------------
def format_value(value):                   
    return "YES" if int(value) else "NO"

# ------------------------------------------------------------------------------
# Audio Feedback
def play_audio(kind = 'gui'):
    from vibmshared.core.sys_config import get_sys_value
    if not get_sys_value("audio_feedback"):
        return

    if sys.platform.startswith('win'):
        import winsound
        freq = {'gui': 1000, 'warning': 1500, 'error': 2000}.get(kind, 1000)
        winsound.Beep(freq, 100)
    else:
        print('\a', end = '', flush = True)

# ------------------------------------------------------------------------------
def safe_run(label, func):
    try:
        func()
    except Exception as e:
        logging.error(f"{label} failed: {e}")
        logging.debug(traceback.format_exc())
        print(f"[EXCEPTION] {label} failed: {e}")

# ------------------------------------------------------------------------------
def guard_gui(flag_name = 'gui_busy'):
    def decorator(method):
        def wrapper(self, *args, **kwargs):
            if getattr(self, flag_name, False):
                return
            setattr(self, flag_name, True)
            try:
                return method(self, *args, **kwargs)
            except Exception as e:
                logging.error(f"[{flag_name}] Exception in {method.__name__}: {e}")
                logging.debug(traceback.format_exc())
            finally:
                setattr(self, flag_name, False)
        return wrapper
    return decorator

# ------------------------------------------------------------------------------
if __name__ == '__main__':
    from vibmshared.core.sys_config import sys_config_init
    from vibmshared.core.path_manager   import PathManager, USEFUL_FOLDERS
    
    path_mgr = PathManager(__file__, USEFUL_FOLDERS)
    
    print("[TEST] Testing utilty_helpers.py")
    for ch in range(4):
        unit = get_channel_sensor_unit(ch)
        print(f"Channel {ch}: unit = {unit}")
    