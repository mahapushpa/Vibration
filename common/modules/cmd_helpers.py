"""cmd_helper.py
=================================
Unified structure using CMD_TABLE as the single source of truth.
"""
#-------------------------------------------------------------------------------
import  sys
import  logging
from    datetime import datetime

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
    from modules.cmd_remote import CMD_TABLE

#-------------------------------------------------------------------------------
from common.utils.gui_utils     import *
from common.modules.cmd_remote  import CMD_TABLE
from common.utils.utils_helpers import validate_param_value, safe_log

# ------------------------------------------------------------------------------
def pack_gps_dms(lat_deg, lat_min, lat_sec, lat_dir,
                 lon_deg, lon_min, lon_sec, lon_dir):
    """
    Pack GPS coordinates in DMS format into 8-character string.

    Parameters:
        lat_deg, lat_min, lat_sec : int
        lat_dir : 'N' or 'S'
        lon_deg, lon_min, lon_sec : int
        lon_dir : 'E' or 'W'

    Returns:
        8-character string representing packed GPS location
    reverse - 
        packed_str = sys_loc_str  # your 8-character string
        print(f"Latitude: {ord(packed_str[0])}° {ord(packed_str[1])}' {ord(packed_str[2])}\" {packed_str[3]}")
        print(f"Longitude: {ord(packed_str[4])}° {ord(packed_str[5])}' {ord(packed_str[6])}\" {packed_str[7]}")
    """
    # Convert integers to single-character using chr()
    return (
        chr(lat_deg) + chr(lat_min) + chr(lat_sec) + lat_dir +
        chr(lon_deg) + chr(lon_min) + chr(lon_sec) + lon_dir
    )

# ------------------------------------------------------------------------------
def write_module_direct(cmd_handler, log_handler, module: str):
    """Write for all writable parameters in a module."""
    params = CMD_TABLE.get(module, {})
    for param, info in params.items():
        if info.get("writable", True) is False:
            log_handler.log(f"[SKIP] Skipping read-only param: {module} -> {param}")
            continue  # Skip read-only

        # Step 1: Try default
        gui_info = info.get("gui")
        if gui_info is None:
            value = None
        else:
            value = gui_info.get("default")
            options = gui_info.get("options")
            if options and value in options:
                value = options[value]  # convert display label to actual value

        # Step 2: Fallback to allowed or range
        if value is None and "allowed" in info:
            value = info["allowed"][0]
        elif value is None and "range" in info:
            value = info["range"][0]
        elif value is None and "pattern" in info:
            value = datetime.now().strftime('%y%m%d')
            param_bytes = value.encode("utf-8")
            param_size = info.get("size")
            # Ensure it's padded or truncated to param_size
            if len(param_bytes) < param_size:
                param_bytes = param_bytes.ljust(param_size, b'\x00')
            else:
                param_bytes = param_bytes[:param_size]            

        if value is None:
            log_handler.log(f"[SKIP] {module}.{param} has no default/allowed/range value")
            continue

        # Step 3: Perform write
        success = write_single_param_direct(cmd_handler, log_handler, module, param, value)
        log_handler.log(f"[WRITE] {module}.{param} = {value} -> {'OK' if success else 'FAIL'}")
        
# ------------------------------------------------------------------------------
def write_single_param_direct(cmd_handler, log_handler, module, param, value) -> bool:
    """
    Perform direct write for a single param.
    Args:
        module - e.g., 'ADC', 'BRD' or 'SYS'
        param  - e.g., 'SRATE', ''
    Returns:
        True if write succeeded, False otherwise
    """
    # Step 1: # Validate module and parameter in CMD_TABLE
    if module not in CMD_TABLE or param not in CMD_TABLE[module]:
        safe_log(log_handler, f"[CMD_TABLE] Invalid module/param: {module}.{param}", tag = "error")
        return False  # validation function logs internally
    
    # Step 2: Check this parameter writable?
    if not CMD_TABLE[module][param].get("writable", True):
        safe_log(log_handler, f"[INFO] Skipping read-only param: {flat_key}->{module}->{param}", tag = "error")
        return False

    flat_key = CMD_TABLE[module][param].get("flat_key", f"{module.lower()}_{param.lower()}")
    
    try:
        ok, validated_value = validate_param_value(module, param, value)
        if not ok:
            safe_log(log_handler, f"[ERROR] Value Error {flat_key}->{module}->{param}: {value}", tag = "error")
            return False  # validation function logs internally
            
        safe_log(log_handler, f"[TX] {flat_key}->{module}->{param} = {validated_value}", tag = "info")
        result = cmd_handler.set_remote_value(flat_key, module, param, validated_value)
        
        if result:
            safe_log(log_handler, f"Failed to write {flat_key}", tag = "error")
            return False
        else:
            safe_log(log_handler, f"Successfully written {flat_key}", tag = "info")
            return True
        
    except Exception as e:
        safe_log(log_handler, f"[EXCEPTION] {flat_key} write failed: {e}", tag = "error")
        return False

# ------------------------------------------------------------------------------
def read_module_direct(cmd_handler, log_handler, module: str):
    """Read for all parameters in a module."""
    params = CMD_TABLE.get(module, {})
    for param, info in params.items():
        success, value = read_single_param_direct(cmd_handler, log_handler, module, param)
        log_handler.log(f"[READ] {module}.{param} = {value} -> {'OK' if success else 'FAIL'}")
        
# ------------------------------------------------------------------------------
def read_single_param_direct(cmd_handler, log_handler, module, param) -> bool:
    """
    Perform direct read for a single param.
    Args:
        module - e.g., 'ADC', 'BRD' or 'SYS'
        param  - e.g., 'SRATE'
    Returns:
        Tuple (True, value) if read and validation succeed, else (False, None)
    """

    if module not in CMD_TABLE or param not in CMD_TABLE[module]:
        safe_log(log_handler, f"Invalid module/param: {module}.{param}", tag="error")
        return False, None

    flat_key = CMD_TABLE[module][param].get("flat_key", f"{module.lower()}_{param.lower()}")

    try:
        safe_log(log_handler, f"[RX] Reading {flat_key} -> {module} -> {param}", tag="info")
        value = cmd_handler.get_remote_value(flat_key, module, param)
        if value is None:
            safe_log(log_handler, f"Remote read failed for {flat_key}", tag="error")
            return False, None

        ok, validated_value = validate_param_value(module, param, value)
        if not ok:
            safe_log(log_handler, f"Validation failed for {flat_key} -> {value}", tag="error")
            return False, None

        safe_log(log_handler, f"{module}->{param}->{validated_value} read successfully", tag="info")
        return True, validated_value

    except Exception as e:
        safe_log(log_handler, f"[EXCEPTION] {flat_key} read failed: {e}", tag="error")
        return False, None

# ------------------------------------------------------------------------------
if __name__ == "__main__":
    from common.core.path_manager import PathManager
    # Define project-relative folders to be added to sys.path
    USEFUL_FOLDERS = [
        'common/core',
        'common/utils',
        'common/modules',
        # Add more here as needed
    ]
    path_mgr = PathManager(__file__, USEFUL_FOLDERS)
