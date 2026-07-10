# Configuration Settings option of remote system
#-------------------------------------------------------------------------------
common_options = {
    'serial_no': '9876', 'hw_ver': 'V2.1',
}

#-------------------------------------------------------------------------------
hw_cfg_options = {
    'gps': False, 'rtc': True, 'sd_card': False, 'battery': True, 'com': 'gprs',
}

#-------------------------------------------------------------------------------
analog_cfg_options = {
    'bits': 16, 'range': 5, 'bit_value': 100, 'notch': True, 'notch_freq': 50 
}

#-------------------------------------------------------------------------------
geophone_cfg_options = {
    'nat_freq': 10, 'max_freq': 200, 'ext_ckt': True, 'ext_freq': 1 
}

#-------------------------------------------------------------------------------
# Define schema: (dict_key, code_letter, value_type)
CONFIG_SCHEMAS = {
    'common' : [
        ('serial_no',   'S', 'str'),
        ('hw_ver',      'H', 'str'),
    ],

    'fw': [
        ('hdr',         'H', 'int'),
        ('cal',         'C', 'int'),
    ],

    'hw': [
        ('gps',         'G', 'bool'),
        ('rtc',         'R', 'bool'),
        ('sd_card',     'S', 'bool'),
        ('battery',     'B', 'bool'),
        ('com_channel', 'C', 'str'),
    ],
    
    'analog': [
        ('polarity',    'P', 'str'),
        ('format',      'F', 'str'),
        ('range',       'R', 'int2'),
        ('bits',        'B', 'int2'),
    ],
    
    'geophone': [
        ('notch_freq',  'N', 'int2'),
        ('nat_freq',    'F', 'int2'),
        ('ext_freq',    'E', 'int'),
        ('ext_ckt',     'C', 'bool'),
    ],
}

#-------------------------------------------------------------------------------
def build_config_string(config_dict, config_type):
    if config_type not in CONFIG_SCHEMAS:
        raise ValueError(f"Unknown config type: {config_type}")
    
    parts = []
    for key, code, val_type in CONFIG_SCHEMAS[config_type]:
        val = config_dict.get(key)
        if val is None:
            raise KeyError(f"Missing key: {key}")
        if val_type == 'bool':
            parts.append(f"{code}{1 if val else 0}")
        elif val_type == 'int2':
            parts.append(f"{code}{int(val):02d}")  # pad to 2 digits
        elif val_type == 'int':
            parts.append(f"{code}{int(val)}")
        elif val_type == 'str':
            parts.append(f"{code}{val}")
        else:
            raise TypeError(f"Unsupported type: {val_type}")
    return ''.join(parts)

#-------------------------------------------------------------------------------
def get_config_string(config_type):
    if config_type == 'common':
        cfg  = build_config_string(common_options,  'common') # -> 'G0R1S0B1CG'
    if config_type == 'hw':
        cfg  = build_config_string(hw_cfg_options,  'hw') # -> 'G0R1S0B1CG'
    elif config_type == 'analog':
        cfg = build_config_string(analog_cfg_options, 'analog')  # -> 'PPBF5B16'
    elif config_type == 'geophone':
        cfg = build_config_string(geophone_cfg_options, 'geophone')  # -> 'N50F10E1C1'

    # print(cfg)    
    return cfg
    
# prep_cfg_str.py

"""
Helper functions to prepare set/get command strings for grouped and individual parameters.
"""

def get_cfg_set_string(param_dict, group=None):
    """Return a string for sending configuration to remote.
    If group is specified, format as a combined command.
    """
    if group:
        # Merge into single command for grouped types
        values = [f"{k}:{v}" for k, v in param_dict.items()]
        return f"SET_{group.upper()}=" + ",".join(values)
    else:
        # Individual single-key command
        k, v = next(iter(param_dict.items()))
        return f"SET_{k.upper()}={v}"

def get_cfg_get_string(param_dict, group=None):
    """Return a string to request configuration values from remote.
    If group is specified, request as a block.
    """
    if group:
        keys = [k.upper() for k in param_dict.keys()]
        return f"GET_{group.upper()}=" + ",".join(keys)
    else:
        k = next(iter(param_dict.keys()))
        return f"GET_{k.upper()}"
    
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    # from utils.prep_cfg_str import get_config_string
    common_cfg  = get_config_string('common')   # -> 'G0R1S0B1CG'
    hw_cfg  = get_config_string('hw')   # -> 'G0R1S0B1CG'
    adc_cfg = get_config_string('analog')   # -> 'PPBF5B16'
    geo_cfg = get_config_string('geophone')   # -> 'N50F10E1C1'
    print(hw_cfg)   # -> 'PPBF05B16'
    print(adc_cfg)  # -> 'PPBF05B16'
    print(geo_cfg)  # -> 'N50F10E01C1'
#-------------------------------------------------------------------------------
