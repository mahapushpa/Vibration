# vibmshared/common.py
"""
common.py — Default settings and shared constants for session, plot, signal, and system configuration.
Used by: maps_sysconfig, GUI setup, simulation, file save, and processing modules.
"""
#-------------------------------------------------------------------------------
import os
import sys
from pathlib import Path

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

#-------------------------------------------------------------------------------
import  logging
import  traceback
import  numpy as np

#-------------------------------------------------------------------------------
dt_sample     = np.dtype('<i2')  # Platform-independent int16 (little-endian)
dt_time_hdr   = np.dtype('<u4')  # Platform-independent uint32 (little-endian)
dt_sample_hdr = np.dtype('<u2')  # Platform-independent uint16 (little-endian)

#-------------------------------------------------------------------------------
# Parameter Sets (life is current session only, changeable from gui)
SessionParameters = {
    'session'       : False,    # Session on and off
    'record'        : False,    # Data record on or off
    'prev_record'   : False,    # Recording is active
    'cmd_waiting'   : False,    # Waiting reply from remote
    'connection'    : None,     # Connected to simulation_mode or Remote live mode
    'event'         : True,     # Event detection is on or off
    'pause'         : False,    # Screen pause on or off
}

#-------------------------------------------------------------------------------
# Parameter Sets (factory default, cannot be changed from gui)
default_LocalParameters = {
    'audio_feedback' : True,
    'use_yscale_db'  : False,

    'record_csv'     : False,
    'notch_enable'   : False,
    'geo_override'   : False,
    
    'debug_mode'     : False,
    'log_csv'        : False,
    'log_console'    : False,
    'simulation_mode': True,
}

#-------------------------------------------------------------------------------
# Parameter Sets (remote device values will override during start process)
# make sure these names and flat key in cmd_table are same.
default_RemoteParameters = {
    # --- ADC Related ---
    'adc_calib'     : False,
    'adc_cal_sts'   : False,
    'adc_srate'     : 1024,
    'adc_msrate'    : 8192,
    'adc_fragment'  : 1024,    # in words
    'adc_channels'   : 5,
    'adc_notch'     : False,
    'adc_e_level'   : 1000,    # adc counts
    
    # --- System Info ---
    'sys_ser_no'    : 0,
    'sys_fw_ver'    : '121A10:25:17250810',
    'sys_hw_ver'    : 'HWVR',
    'sys_mfg_date'  : '250606',
    'sys_sys_name'  : 'MAPS_JPR',
    'sys_sys_loc'   : chr(26)+chr(55)+chr(11)+'N'+chr(75)+chr(47)+chr(16)+'E', #'2691N7578E',

    'sys_sys_auto'  : False,
    'sys_sys_com'   : 'U',
    'sys_default'   : False,
}

default_RemoteDerivedParameters = {
    # handling of sys_adc_params, sys_geophone_params 
    'brd_hw_gps'  : False,
    'brd_hw_rtc'  : False,
    'brd_hw_usd'  : False,
    'brd_hw_bat'  : False,
    'brd_hw_com_module': False,
    
    'brd_adc_pol'   : 'B',
    'brd_adc_span'  : 5,
    'brd_adc_bits'  : 16,
    
    'brd_notch_freq'    : 0,
    'brd_geo_range_ext' : 1,
    'brd_geo_ext_freq'  : 10,
    'brd_geo_nat_freq'  : 10,

    # need to remove from here, they are internal calculations
    'sys_no_of_fragments': 1,
    'sys_data_hdr_size'  : 5,       # in words, from remote (not to be read)
    'sys_rcv_data_size'  : 1029*2,  # in bytes = 1024 + 5 
    'sys_serial_baudrate': 115200,  # not needed from remote
}

#-------------------------------------------------------------------------------
# Parameter Sets (factory default, cannot be changed from gui)
default_SignalParameters = {
    'filter'    :    ['highpass', 'lowpass'],
    'window'    :    'hann',
    'transform' :    'FFT',
}    

#-------------------------------------------------------------------------------
# Parameter Sets (factory default, cannot be changed from gui)
default_TfParameters = {
    'analysis_type'  : 'DT',
    'analysis_method': 'FFT',
}    

#-------------------------------------------------------------------------------
# Parameter Sets (factory default, cannot be changed from gui)
default_PlotParameters = {
    'time_xspan': 'span_sec',
    'time_yspan': 'CNT',
    'fft_yspan' : 'linear',
}

#-------------------------------------------------------------------------------
default_PathSettings = {
    'data_path'     : './data',
    'log_path'      : './logs',
    'config_path'   : './config'
}

# Default waveform config for Simulator
default_waveform_cfg = {
    'amplitude': 1000,               # Base amplitude for sine
    'frequencies': [7, 13, 17, 37],  # List of frequencies per channel
    'seed': 1234                     # Random seed for noise (optional, or None)
}

# ------------------------------------------------------------------------------
# Channel and Sensor Mapping (user editable)
channel_to_sensor = {
    0: {'name': "geophone",      'description': "Connected to Chn1 (A)"},
    1: {'name': "geophone",      'description': "Connected to Chn2 (B)"},
    2: {'name': "accelerometer", 'description': "on table leg"},
    3: {'name': "temperature",   'description': "ambient sensor"},
}

# ------------------------------------------------------------------------------
# Sensor to measurement unit mapping (user can add here, based on new sensor)
sensor_to_unit = {
    "geophone"      : "mm/s",
    "accelerometer" : "g",
    "temperature"   : "°C"
}

#-------------------------------------------------------------------------------
__all__ = [
    "SessionParameters",
    "default_LocalParameters",
    "default_RemoteParameters",
    "get_session_flag", "set_session_flag", "toggle_session_flag",
    "dt_sample", "dt_sample_hdr", "dt_time_hdr"
]

#-------------------------------------------------------------------------------
# Internal Lookup Map
internal_lookup = {}
parameter_sets = {
    'session': SessionParameters,
}
for dname, dref in parameter_sets.items():
    for key in dref:
        if key in internal_lookup:
            print(f"Duplicate flag name '{key}' found in SessionParameters.")
            raise KeyError(f"Duplicate flag name '{key}' found in SessionParameters.")
        internal_lookup[key] = dname

# ------------------------------------------------------------------------------
# Accessor Helpers
def get_session_flag(key):
    origin = internal_lookup.get(key)
    if origin == 'session': 
        return SessionParameters[key]

    print(f"Flag '{key}' does not belong to session parameters.")
    raise KeyError(f"Flag '{key}' does not belong to session parameters.")

#-------------------------------------------------------------------------------
def set_session_flag(key, value):
    origin = internal_lookup.get(key)
    if origin == 'session': 
        # SessionParameters[key] = bool(value)
        SessionParameters[key] = (value)
        return
    
    print(f"Flag '{key}' does not belong to session parameters.")
    raise KeyError(f"Flag '{key}' does not belong to session parameters.")

#-------------------------------------------------------------------------------
def toggle_session_flag(key):
    origin = internal_lookup.get(key)
    if origin != 'session':
        print(f"Flag '{key}' does not belong to session parameters.")
        raise KeyError(f"Flag '{key}' does not belong to session parameters.")
    SessionParameters[key] = not SessionParameters.get(key, False)

# ------------------------------------------------------------------------------
if __name__ == '__main__':
    from core.sys_config import sys_config_init, get_sys_value, set_sys_value
    from utils.utils_helpers import play_audio
    from vibmshared.core.path_manager import PathManager, USEFUL_FOLDERS
    path_mgr = PathManager(__file__, USEFUL_FOLDERS)
    sys_config_init(path_mgr)
    
    print("[TEST] Running common.py test")

    set_sys_value('simulation_mode', True)
    print("simulation_mode:", get_sys_value('simulation_mode'))

    play_audio('gui')
    play_audio('warning')
    play_audio('error')



