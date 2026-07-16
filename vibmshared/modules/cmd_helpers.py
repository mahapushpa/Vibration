"""cmd_helper.py
=================================
Unified structure using CMD_TABLE as the single source of truth.
"""
#-------------------------------------------------------------------------------
import  sys
import  time
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
from vibmshared.utils.gui_utils     import *
from vibmshared.modules.cmd_remote  import CMD_TABLE, CMD_TIMEOUT_SEC
from vibmshared.utils.utils_helpers import validate_param_value, safe_log
from vibmshared.core.common         import get_session_flag

# ------------------------------------------------------------------------------
# Polling for async (session-mode) replies
# ------------------------------------------------------------------------------
# When session is on, send_command() returns "WAIT" immediately: the reply is
# actually delivered later by the background SerialReader thread, which calls
# rcv_response() (clearing the global 'cmd_waiting' flag and setting
# cmd_handler.last_reply). These helpers are the only consumers of that
# mechanism, so they must poll for it here rather than treating "WAIT" as a
# value or a failure.
WAIT_POLL_INTERVAL_SEC = 0.05
WAIT_POLL_MAX_ITERS    = max(1, int(CMD_TIMEOUT_SEC / WAIT_POLL_INTERVAL_SEC))

def _wait_for_last_reply(cmd_handler, log_handler, flat_key):
    """
    Poll for the async reply to a command sent while session was on.
    Returns the reply tuple (resp_code, module, param, value) once the
    background thread has processed it, or None if it never arrives within
    CMD_TIMEOUT_SEC.
    """
    for _ in range(WAIT_POLL_MAX_ITERS):
        # rcv_response() clears cmd_waiting at the same moment it sets
        # last_reply, so a False flag means the reply (if any) is ready.
        if not get_session_flag('cmd_waiting'):
            return cmd_handler.last_reply
        time.sleep(WAIT_POLL_INTERVAL_SEC)

    safe_log(log_handler, f"[TIMEOUT] {flat_key}: no reply received within {CMD_TIMEOUT_SEC}s (WAIT)", tag = "error")
    return None

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

        # Step 2: Fallback to top-level default, allowed, or range
        # Some CMD_TABLE entries (e.g. SYS_NAME, SYS_LOC) have "gui": None
        # and define their default via a top-level "default" key instead of
        # nested under "gui" — without this check those params were always
        # left as value=None and silently [SKIP]ped (never writable via the
        # toolbar "Set" buttons). See CLAUDE.md known issues.
        if value is None and "default" in info:
            value = info["default"][0]
        elif value is None and "allowed" in info:
            value = info["allowed"][0]
        elif value is None and "range" in info:
            value = info["range"][0]
        elif value is None and "pattern" in info:
            # Pattern-only params (e.g. date fields): use today's date as the
            # value. encode_value() handles size padding/truncation downstream,
            # so no local byte-packing is needed here.
            value = datetime.now().strftime('%y%m%d')

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
        safe_log(log_handler, f"[INFO] Skipping read-only param: {module}->{param}", tag = "error")
        return False

    flat_key = CMD_TABLE[module][param].get("flat_key", f"{module.lower()}_{param.lower()}")
    
    try:
        ok, validated_value = validate_param_value(module, param, value)
        if not ok:
            safe_log(log_handler, f"[ERROR] Value Error {flat_key}->{module}->{param}: {value}", tag = "error")
            return False  # validation function logs internally
            
        safe_log(log_handler, f"[TX] {flat_key}->{module}->{param} = {validated_value}", tag = "info")
        success, resp_code = cmd_handler.set_remote_value(flat_key, module, param, validated_value)

        if resp_code == "WAIT":
            safe_log(log_handler, f"[TX] {flat_key} reply pending (session mode), waiting...", tag = "info")
            reply = _wait_for_last_reply(cmd_handler, log_handler, flat_key)

            if not reply or len(reply) < 4:
                safe_log(log_handler, f"Failed to write {flat_key} (no reply)", tag = "error")
                return False

            ack_code = reply[0]
            if ack_code != 0x00:  # CMD_ACK
                safe_log(log_handler, f"Failed to write {flat_key} (response code {ack_code})", tag = "error")
                return False

            safe_log(log_handler, f"Successfully written {flat_key}", tag = "info")
            return True

        if not success:
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

        if value == "WAIT":
            safe_log(log_handler, f"[RX] {flat_key} reply pending (session mode), waiting...", tag="info")
            reply = _wait_for_last_reply(cmd_handler, log_handler, flat_key)

            if not reply or len(reply) < 4:
                safe_log(log_handler, f"Remote read failed for {flat_key} (no reply)", tag="error")
                return False, None

            resp_code, _, _, value = reply
            if resp_code != 0x00:  # CMD_ACK
                safe_log(log_handler, f"Remote read failed for {flat_key} (response code {resp_code})", tag="error")
                return False, None

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
    from vibmshared.core.path_manager import PathManager
    # Define project-relative folders to be added to sys.path
    USEFUL_FOLDERS = [
        'vibmshared/core',
        'vibmshared/utils',
        'vibmshared/modules',
        # Add more here as needed
    ]
    path_mgr = PathManager(__file__, USEFUL_FOLDERS)
