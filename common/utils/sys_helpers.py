import re
import logging
from typing import Tuple, Optional

#-------------------------------------------------------------------------------
from common.modules.cmd_remote import CMD_TABLE
from common.utils.utils_helpers import validate_param_value, raise_key_error_msg
from common.core.parameters import (
    TFParams, 
    PlotParams,
    FilterParams, 
    WindowParams, 
    TransformParams, 
)

# Global variable (initially empty)
FLATKEY_TO_MODULE_PARAM: dict[str, tuple[str, str]] = {}

def get_module_param_from_flatkey(flat_key: str) -> tuple[str, str] | None:
    """
    Return (module, param) from flat_key.
    Lazy initialization: builds lookup table on first call if empty.
    """
    global FLATKEY_TO_MODULE_PARAM

    # Build table only if empty
    if not FLATKEY_TO_MODULE_PARAM:
        for module_name, module_dict in CMD_TABLE.items():
            for param_name, param_dict in module_dict.items():
                fk = param_dict.get("flat_key")
                if fk:
                    FLATKEY_TO_MODULE_PARAM[fk] = (module_name, param_name)
    # Lookup
    result = FLATKEY_TO_MODULE_PARAM.get(flat_key)
#    if result is None:
#        logging.warning(f"[WARNING] flat_key '{flat_key}' not found in CMD_TABLE.")
    return result
   
#-------------------------------------------------------------------------------
def validate_sys_value(key, value):
    """
    Validate a system-level key and value.
    Delegates to validate_param_value for remote keys.
    """
    if isinstance(value, list):
        for v in value:
            if not _validate_sys_single_value(key, v):
                print(f"[ERROR] List entry for {key} is invalid: {v}")
                return False
        return True
    return _validate_sys_single_value(key, value)
    
#-------------------------------------------------------------------------------
def _validate_sys_single_value(key, value):
    """Set a value to current system config, with validation"""
    # Rule 1: If key maps to remote CMD, validate with CMD_TABLE
    mod_param = get_module_param_from_flatkey(key)
    if mod_param:
        module, param = mod_param
        return validate_param_value(module, param, value)
        
    # Rule 2: If key belongs to a Param class, validate there
    if FilterParams.is_valid(key, value):    return True
    if WindowParams.is_valid(key, value):    return True
    if TransformParams.is_valid(key, value): return True
    if TFParams.is_valid(key, value):        return True
    if PlotParams.is_valid(key, value):      return True

    raise_key_error_msg("[ERROR] Invalid value for {key} -> {value}")
