#-------------------------------------------------------------------------------
"""
sys_config.py - Handles system INI loading and validation
"""
#-------------------------------------------------------------------------------
import os
import sys
from pathlib import Path

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
#-------------------------------------------------------------------------------
import ast
import hashlib
import logging
import configparser
import matplotlib as mpl
import matplotlib.pyplot as plt

from datetime import datetime

#-------------------------------------------------------------------------------
from common.core.product_meta import UserMeta
from common.utils.sys_helpers import validate_sys_value
from common.core.common import (
    default_PathSettings, default_LocalParameters, default_RemoteParameters,
    default_RemoteDerivedParameters, default_SignalParameters, default_PlotParameters,
    default_TfParameters
)

#-------------------------------------------------------------------------------
# Keys that represent relative paths in the INI file
INI_PATH_KEYS = {"log_path", "data_path", "config_path"}

INI_FILE = "sys_config.ini"

# -------------------------------------------------------------------------------
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Global error handler."""
    if issubclass(exc_type, KeyboardInterrupt):
        return  # Let default handler handle keyboard exits
    print("[FATAL] Unhandled exception. See log for details.")
    logging.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

#------------------------------------------------------------------------------
def configure_logging(log_path, log_on_console, csv_logs, debug_mode):
    
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")

    # --- Text log ---
    txt_filename = f"Log{timestamp}.txt"
    log_path_txt = os.path.join(log_path, txt_filename)

    txt_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(module)s.%(funcName)s:%(lineno)d | %(message)s")

    handlers = [logging.FileHandler(log_path_txt, mode = 'w')]
    handlers[0].setFormatter(txt_formatter)

    # --- Optional console logging ---
    if log_on_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(txt_formatter)
        handlers.append(console_handler)

    # --- Optional CSV logging ---
    if csv_logs:
        csv_filename = f"Log{timestamp}.csv"
        log_path_csv = os.path.join(log_path, csv_filename)
        csv_formatter = logging.Formatter(
            '%(asctime)s,%(levelname)s,%(module)s,%(funcName)s,%(lineno)d,%(message)s')
        csv_handler = logging.FileHandler(log_path_csv, mode = 'w', encoding = 'utf-8')
        csv_handler.setFormatter(csv_formatter)
        handlers.append(csv_handler)

    # Set log level based on debug flag
    log_level = logging.DEBUG if debug_mode else logging.INFO

    logging.basicConfig(level = log_level, handlers = handlers, force = True)
    logging.info(f"Logging initialized: level = {logging.getLevelName(log_level)}, console = {log_on_console}, csv = {csv_logs}")
    # print(f"Logging initialized: level = {logging.getLevelName(log_level)}, console = {log_on_console}, csv = {csv_logs}")

#-------------------------------------------------------------------------------
def configure_plotting():
    if not sys.warnoptions:
        import warnings
        warnings.filterwarnings("ignore", category = UserWarning,
            message = "Treat the new Tool classes introduced in v1.5 as experimental for now")

    if mpl.get_backend() != 'TkAgg':
        try:
            mpl.use("TkAgg", force = True)
        except ImportError as e:
            logging.warning(f"Matplotlib backend error: {e}")
            print(f"[WARNING] Could not switch backend to TkAgg: {e}")

    current_backend = mpl.get_backend()
    logging.info(f"Matplotlib backend in use: {current_backend}")
    # print(f"[INFO] Matplotlib backend in use: {current_backend}")

    plt.rcParams['toolbar'] = 'None'
    plt.style.use('fast')
    plt.rcParams['lines.markersize'] = 3
    plt.rcParams['agg.path.chunksize'] = 0

    sys.excepthook = global_exception_handler
    logging.info("Global exception handler enabled")

    # mpl.rcParams.update({
    #     "font.family": "Segoe UI",
    #     "font.size": 11,
    #     "axes.titlesize": 12,
    #     "axes.labelsize": 11,
    #     "xtick.labelsize": 10,
    #     "ytick.labelsize": 10,
    # })
#-------------------------------------------------------------------------------
class SystemConfig:
    project_root = None  # class-level

    current = {}
    config_file = None  # Will be set during load
    defaults_by_group = {}

#-------------------------------------------------------------------------------
    @classmethod
    def set_project_root(cls, path):
        cls.project_root = Path(path).resolve()

    @staticmethod
    def cast_bool(x):
        return str(x).strip().lower() in ['1', 'true', 'yes', 'on']
    
    @staticmethod
    def cast_list(x):
        if isinstance(x, list):
            return x  # already a list
        try:
            return ast.literal_eval(x)
        except Exception:
            print(f"[WARN] Failed to cast list: {x}, returning empty list")
            return []

#-------------------------------------------------------------------------------
    @classmethod
    def valid_keys(cls):
        return set(cls.current.keys())

#-------------------------------------------------------------------------------
    @classmethod
    def _infer_type(cls, v):
        if isinstance(v, bool):
            return cls.cast_bool
        elif isinstance(v, list):
            return cls.cast_list
        else:
            return type(v)

#-------------------------------------------------------------------------------
    @classmethod
    def build_defaults(cls, final_path_settings):
        # Update default_PathSettings with final paths from PathManager
        for k in default_PathSettings:
            default_PathSettings[k] = final_path_settings.get(k, default_PathSettings[k])

        # Non-rule-based (no validation needed)
        nonrule_based_groups = {
            'from PathSettings': default_PathSettings,
            'from default_LocalParameters': default_LocalParameters,
            'from default_RemoteDerivedParameters': default_RemoteDerivedParameters,
        }
        
        # Rule-based (requires validation before accepting)
        rule_based_groups = {
            'from default_RemoteParameters': default_RemoteParameters,
            'from default_SignalParameters': default_SignalParameters,
            'from default_PlotParameters': default_PlotParameters,
            'from default_TfParameters': default_TfParameters,
        }

        cls.defaults_by_group = {**nonrule_based_groups, **rule_based_groups}

        cls.rule_based_keys = set()
        cls.nonrule_based_keys = set()
        cls.failed_keys = set()     # used on load, kept here for central place
        cls.validated_keys = set()

        # Populate both sets
        for group in nonrule_based_groups.values():
            cls.nonrule_based_keys.update(k.strip() for k in group.keys())
        for group in rule_based_groups.values():
            cls.rule_based_keys.update(k.strip() for k in group.keys())

        cls.type_map = {}
        # Direct build for non-rule-based (accept all)
        for section, items in nonrule_based_groups.items():
            for k, v in items.items():
                cls.type_map[k.strip()] = cls._infer_type(v)

        # Validate and build
        for section, items in rule_based_groups.items():
            for k, v in items.items():
                if validate_sys_value(k, v):   # same function used in dynamic saving
                    cls.type_map[k.strip()] = cls._infer_type(v)

#-------------------------------------------------------------------------------
    @classmethod
    def compute_checksum(cls, data_dict):
        joined = ''.join(f"{k}={str(v).strip()}" for k, v in sorted(data_dict.items()))
        digest = hashlib.sha1(joined.encode()).hexdigest()
        return '0x' + (digest[:4]).upper()  # Ensures full uppercase (2-byte hex string)

#-------------------------------------------------------------------------------
    @classmethod
    def load(cls, abs_paths: dict, rel_paths: dict):

        from common.utils.utils_helpers import log_info_msg

        cls.build_defaults(rel_paths)

        flat_defaults = {}
        for section_dict in cls.defaults_by_group.values():
            for key, val in section_dict.items():
                flat_defaults[key.strip()] = str(val).strip()

        config_path_abs = Path(abs_paths["config_path"]).resolve()
        cls.config_file = str(config_path_abs / INI_FILE)

        # If config file missing, create fresh one
        if not os.path.exists(cls.config_file):
            print("[INFO] sys_config.ini not found. Creating default config.")
            cls.current = flat_defaults.copy()
            meta_action = cls.save(meta_action = "auto_generated_on")
            # Now re-read and re-process it to apply parsing and type casting
            cls.load(abs_paths, rel_paths)  # reload with proper casting (recursive call)
            return meta_action

        config = configparser.ConfigParser()
        config.read(cls.config_file)

        flat_config = {}
        for section in config.sections():
            if section != 'meta':
                for k, v in config[section].items():
                    flat_config[k.strip()] = v.strip()

        # Normalize + merge
        merged = {**flat_defaults, **flat_config}
        normalized_merged = {k.strip(): str(v).strip() for k, v in merged.items()}

        # Type casting and validation of values
        typed_merged = {}
        for k, v in normalized_merged.items():
            caster = cls.type_map.get(k, str)
            try:
                casted_val = caster(v)
            except Exception as e:
                print(f"[ERROR] Failed to cast {k} = {v} using {caster}: {e}")
                # casted_val = flat_defaults[k]
                casted_val = cls.type_map[k](flat_defaults[k])

            if k in cls.rule_based_keys:
                if not validate_sys_value(k, casted_val):
                    print(f"[ERROR] Invalid INI value: {k} = {casted_val}, restoring default")
                    logging.error(f"[ERROR] Invalid INI value: {k} = {casted_val}, restoring default")
                    # casted_val = flat_defaults[k]
                    casted_val = cls.type_map[k](flat_defaults[k])
                    cls.failed_keys.add(k)
                else:
                    cls.validated_keys.add(k)

            typed_merged[k] = casted_val

        # Re-normalize the typed data for string-based comparison and checksum
        normalized_from_typed = {k: str(v).strip() for k, v in typed_merged.items()}

        # Structural check
        if set(normalized_from_typed.keys()) != set(flat_defaults.keys()):
            logging.info("sys_config.ini updated due to structure change.")
            cls.log_diff(flat_config, flat_defaults)
            cls.current = typed_merged
            meta_action = cls.save(meta_action = "last_edit_save_on")
            return meta_action

        # Checksum check
        file_checksum = config['meta'].get('config_checksum', '').strip() #.upper()
        calc_checksum = cls.compute_checksum(normalized_from_typed)

        if file_checksum != calc_checksum:
            log_info_msg("[WARN] sys_config.ini checksum mismatch. Restoring from defaults...", do_print = True)
            cls.current = {k: v for k, v in flat_defaults.items()}
            meta_action = cls.save(meta_action = "checksum_failed_on")
            return meta_action
            
        else:
            logging.info("sys_config.ini loaded (latest_used_on)")
            # meta_action = cls.save(meta_action = "latest_used_on")
            meta_action = "latest_used_on"
            cls.current = typed_merged
            return meta_action

#-------------------------------------------------------------------------------
    @classmethod
    def save(cls, meta_action = "last_edit_save_on"):
        config = configparser.ConfigParser()
        now = datetime.now().strftime('%d %b %Y %H:%M:%S')
        
        config.read(cls.config_file)  # Load previous meta values
        meta = dict(config['meta']) if config.has_section('meta') else {}
        meta['config_checksum'] = cls.compute_checksum(cls.current)

        if meta_action == "latest_used_on":
            meta['latest_used_on'] = now
        elif meta_action == "checksum_failed_on":
            meta['checksum_failed_on'] = now
            meta['latest_used_on'] = now
        else:
            meta['auto_generated_on'] = now
            meta['last_edit_save_on'] = now
            meta['latest_used_on'] = now

        # Save updated meta back
        config['meta'] = meta

        # Write grouped sections
        for section, items in cls.defaults_by_group.items():
            config[section] = {}
            for key in items:
                config[section][key] = str(cls.current.get(key, items[key]))

        if not cls.config_file:
            raise RuntimeError("SystemConfig.config_file is not set. Call load() first.")
        
        with open(cls.config_file, "w") as f:
            config.write(f)

        logging.info("sys_config.ini saved ({meta_action})")
        return meta_action
        
#-------------------------------------------------------------------------------
    @classmethod
    def log_diff(cls, config_dict, defaults_dict):
        config_clean = {k.strip(): str(v).strip() for k, v in config_dict.items()}
        default_clean = {k.strip(): str(v).strip() for k, v in defaults_dict.items()}

        extra_keys = set(config_clean) - set(default_clean)
        missing_keys = set(default_clean) - set(config_clean)
        changed_values = {
            k: (default_clean[k], config_clean[k])
            for k in default_clean
            if k in config_clean and default_clean[k] != config_clean[k]
        }

        if extra_keys or missing_keys or changed_values:
            logging.warning("[SYS CONFIG] Structural change detected in keys.")
            for k in sorted(extra_keys):
                print(f"[EXTRA KEY] {k} = {config_clean[k]}")
                logging.info(f"[EXTRA KEY] {k} = {config_clean[k]}")
            for k in sorted(missing_keys):
                print(f"[MISSING KEY] {k} = {default_clean[k]}")
                logging.info(f"[MISSING KEY] {k} = {default_clean[k]}")
            for k, (dval, cval) in sorted(changed_values.items()):
                print(f"[CHANGED] {k}: DEFAULT='{dval}' -> INI='{cval}'")
                logging.info(f"[CHANGED] {k}: DEFAULT='{dval}' -> INI='{cval}'")

#-------------------------------------------------------------------------------
    @classmethod
    def ensure_loaded(cls, abs_paths: dict, rel_paths: dict):
        if not cls.current:
            status = cls.load(abs_paths, rel_paths)
            return status  # return status string like 'first_run', 'checksum_failed', etc.
        return "latest_used_on"

# ------------------------------------------------------------------------------
# External access helpers
# ------------------------------------------------------------------------------
def get_sys_value(key, default = None, validate = True):
    
    if validate and key not in SystemConfig.current:
        raise KeyError(f"[SystemConfig] Unknown key: '{key}'")

    value = SystemConfig.current.get(key, default)
    caster = SystemConfig.type_map.get(key)

    try:
        result = caster(value) if caster else value
        
    except (ValueError, TypeError):
        raise ValueError(f"[SystemConfig] Failed to convert '{key}' to {caster}")

    if key in INI_PATH_KEYS:
        if SystemConfig.project_root is None:
            raise RuntimeError("SystemConfig.project_root is not set. Call set_project_root(...) first.")
        return (SystemConfig.project_root / result).resolve()

    return result
    
#-------------------------------------------------------------------------------
def set_sys_value(key, value, validate = True, autosave = True):
    """Set a system value with optional validation and autosave."""
    from common.utils.sys_helpers import validate_sys_value
    
    is_valid = validate_sys_value(key, value)
    
    if not is_valid and key not in SystemConfig.current:
        raise KeyError(f"[SystemConfig] Unknown key: '{key}'")

    SystemConfig.current[key] = str(value).strip()
    
    if autosave:
        meta_action = SystemConfig.save(meta_action = "last_edit_save_on")
        logging.info(f"[INFO] maps_sys.ini loaded ({meta_action})")
        
#-------------------------------------------------------------------------------
def set_sys_value_default(key, value):
    """Set a system default value with validation (used in first-run INI creation)."""
    from common.utils.sys_helpers import validate_sys_value
    is_valid = validate_sys_value(key, value)
    if not is_valid and key not in SystemConfig.current:
        raise KeyError(f"[SystemConfig] Unknown key: '{key}'")

    SystemConfig.defaults_by_group["Flags"][key] = value
    
#-------------------------------------------------------------------------------
def sys_reset_to_defaults(meta_action = "restored_defaults"):
    SystemConfig.build_defaults()
    flat_defaults = {
        k.strip(): str(v).strip()
        for section in SystemConfig.defaults_by_group.values()
        for k, v in section.items()
    }
    SystemConfig.current = flat_defaults
    meta_action = SystemConfig.save(meta_action = meta_action)
    logging.info(f"[INFO] maps_sys.ini loaded ({meta_action})")

#-------------------------------------------------------------------------------
def sys_config_init(path_mgr):
    from common.core.common import default_LocalParameters

    abs_paths = path_mgr.get_output_path_settings()
    rel_paths = path_mgr.get_relative_path_settings()
    
    SystemConfig.set_project_root(path_mgr.project_root)

    configure_logging(
        log_path       = abs_paths.get("log_path", "./logs"),
        log_on_console = bool(default_LocalParameters.get("log_console", 0)),
        csv_logs       = bool(default_LocalParameters.get("log_csv", 0)),
        debug_mode     = bool(default_LocalParameters.get("debug_mode", 0)),
    )

    configure_plotting()

    ini_status = SystemConfig.ensure_loaded(abs_paths, rel_paths)
    
    from common.core.sys_config import get_sys_value
    UserMeta(config_path = get_sys_value('config_path'))
    
    if hasattr(SystemConfig, 'validated_keys'):
        total_valid = len(SystemConfig.validated_keys)
        total_fail  = len(SystemConfig.failed_keys)
        total_rule  = len(SystemConfig.rule_based_keys)
        logging.info(f"Rule-based INI checks: {total_valid} passed, {total_fail} failed, of {total_rule} total")

        if total_fail > 0:
            msg = f"[FAIL] {total_fail} rule-based INI value(s) failed validation."
            logging.error(msg)
            print(f"[ERROR] {msg}")

            if get_sys_value('debug_mode'):
                raise ValueError(msg)
            
    return ini_status

#*******************************************************************************
if __name__ == '__main__':
    ini_status = sys_config_init()
    # print(f"[INFO] maps_sys.ini loaded ({ini_status})")
#-------------------------------------------------------------------------------
