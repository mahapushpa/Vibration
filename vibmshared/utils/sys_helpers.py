import re
import logging
from typing import Tuple, Optional

#-------------------------------------------------------------------------------
from vibmshared.modules.cmd_remote import CMD_TABLE
from vibmshared.utils.utils_helpers import validate_param_value, report_key_error
from vibmshared.core.parameters import (
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
    """Validate a single (scalar) system-config key/value.
    Delegates to validate_param_value() for CMD-mapped (remote) keys,
    otherwise checks the matching Param class."""
    # Rule 1: If key maps to remote CMD, validate with CMD_TABLE
    mod_param = get_module_param_from_flatkey(key)
    if mod_param:
        module, param = mod_param
        # validate_param_value() returns a (bool, normalized_value) tuple;
        # return only the bool. A non-empty tuple is always truthy, so the
        # old `return validate_param_value(...)` silently accepted every
        # invalid remote value at the call sites (all of which test it as a
        # plain bool).
        ok, _ = validate_param_value(module, param, value)
        return ok

    # Rule 2: If key belongs to a Param class, validate there
    if FilterParams.is_valid(key, value):    return True
    if WindowParams.is_valid(key, value):    return True
    if TransformParams.is_valid(key, value): return True
    if TFParams.is_valid(key, value):        return True
    if PlotParams.is_valid(key, value):      return True

    # report_key_error() returns False (or raises in debug mode) — return it
    # so this function always yields a proper bool rather than an implicit None.
    return report_key_error(f"[ERROR] Invalid value for {key} -> {value}")
