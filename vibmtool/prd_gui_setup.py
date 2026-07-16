#-------------------------------------------------------------------------------
# Production Setup GUI — Cleaned and Reviewed
#-------------------------------------------------------------------------------
"""
This module provides the GUI setup and INI file management interface for Production Tools.
It supports two modes: Master and Device setup, both using the `InputManager` as the single
source of truth for editable values. All widgets are bound directly to this dict.

Main Classes:
- InputManager   -> Controls value loading/saving for both master and device
- SetupManager   -> Launches dialog based on user selection (New/Edit)
- SetupDialog    -> GUI dialog for editing values and saving to INI
- SummaryDialog  -> Loads a master INI file and compares it to existing device files
"""
#-------------------------------------------------------------------------------
# Imports
#-------------------------------------------------------------------------------
import os
import re
import logging
import tkinter as tk
from datetime  import datetime
from typing    import Any, Dict
from tkinter   import ttk, messagebox, filedialog, simpledialog

from vibmtool.prd_gui_meta   import *
from vibmshared.utils.gui_utils    import *
from vibmshared.utils.utils_helpers import *
from vibmshared.utils.config_io    import ConfigIO
from vibmtool.prd_features   import IS_ENABLED
from vibmshared.core.product_meta  import ProductMeta
from vibmshared.modules.cmd_remote import CMD_TABLE, MODULE_ALIASES
from vibmshared.modules.cmd_helpers import write_single_param_direct, read_single_param_direct
from vibmshared.core.sys_config    import get_sys_value, set_sys_value

#-------------------------------------------------------------------------------
# Validation constraints for serial number
#-------------------------------------------------------------------------------
SERIAL_RANGE = CMD_TABLE["SYS"]["SER_NO"].get("range", (0, 9999))

#-------------------------------------------------------------------------------
# Filename helpers
#-------------------------------------------------------------------------------
# client/order_id are free-text Entry fields (see prd_gui_meta.META_DEFINITIONS)
# with no character restriction, and both are woven into generated filenames
# (device_/master_/build_/summary_ *). Underscores are intentionally still
# allowed in client/order — restricting operator input isn't the fix here.
# Two separate concerns instead:
#   1) filesystem-illegal characters (path separators etc.) must still be
#      stripped, or a client/order value could break file creation outright.
#   2) any code that later re-parses a generated filename must not assume a
#      fixed number of "_"-separated fields, since client/order may contain
#      "_" themselves — see DEVICE_FILENAME_RE below.
_FILENAME_ILLEGAL_CHARS_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

def _sanitize_filename_part(text: str) -> str:
    """Strip characters that are illegal in filenames on Windows/POSIX.
    Underscores are deliberately left untouched — see module note above."""
    cleaned = _FILENAME_ILLEGAL_CHARS_RE.sub("-", str(text)).strip(" .")
    return cleaned or "unknown"

# Matches: device_<anything>_<digits>.ini — the trailing "_<digits>" group is
# the serial number, greedily anchored so it's found correctly no matter how
# many underscores appear earlier in <anything> (i.e. inside client/order).
DEVICE_FILENAME_RE = re.compile(r'^device_.*_(\d+)\.ini$', re.IGNORECASE)

def _serial_sort_key(sn):
    """Numeric serials sort numerically; non-numeric keys sort after them,
    alphabetically — one bad hand-edited key no longer aborts the whole
    summary load/export."""
    s = str(sn).strip()
    return (0, int(s), "") if s.isdigit() else (1, 0, s)

def _confirm_overwrite(path) -> bool:
    """Ask before overwriting an existing export/report file — save_to_ini()
    already asks; the fixed-name exports silently clobbered."""
    if os.path.exists(path):
        return messagebox.askyesno(
            "Overwrite File?",
            f"A file already exists:\n{os.path.basename(path)}\n\nDo you want to overwrite it?")
    return True

#-------------------------------------------------------------------------------
# Class: InputManager
#-------------------------------------------------------------------------------
class InputManager:
    """
    Central container for all editable config values.
    Acts as the unified source-of-truth between GUI widgets and INI files.
    All inputs follow INI layout (e.g. client_info, product_info, hardware_info).
    Supports both 'master' and 'device' mode by adapting skip keys and sections.
    """

    def __init__(self, config_dir = None, log_handler = None, path_handler = None, 
                        setup_mode: str = "master", is_new_setup: bool = True):
        
        self.config_dir  = config_dir
        self.log_handler = log_handler
        self.path_handler = path_handler
        self.setup_mode  = setup_mode

        self.value_state = "normal"
        
        if setup_mode == "master":
            self.skip_meta_keys  = META_MASTER_SKIP_KEYS
            self.skip_param_keys = PARAM_MASTER_SKIP_KEYS
            self.skip_section    = SECTION_MASTER_SKIP
        elif setup_mode == "device":
            self.skip_meta_keys  = META_DEVICE_SKIP_KEYS
            self.skip_param_keys = PARAM_DEVICE_SKIP_KEYS
            self.skip_section    = SECTION_DEVICE_SKIP
        else: # setup_mode == "program":
            self.skip_meta_keys  = META_PROGRAM_SKIP_KEYS
            self.skip_param_keys = PARAM_PROGRAM_SKIP_KEYS
            self.skip_section    = SECTION_PROGRAM_SKIP
            self.value_state = "normal" if is_new_setup else "readonly"

        self.inputs: Dict[str, Dict[str, Any]] = {
            v: {} for v in PRD_INI_SECTIONS.values() if v not in self.skip_section
        }

        self.source = None
        self.serial_no = None
        self.master_inputs = {}
        self.program_widgets = {}
        self.verification_results = {}  # {flat_key: ("PASS" or "FAIL", written, read)}
        
    # ------ META UPLOAD TO GUI ------------------------------------------------
    def draw_meta_block(self, parent: tk.Widget, client_inputs: Dict[str, Any], 
                                    product_inputs: Dict[str, Any]) -> None:
        """
        Render metadata fields (client_info and product_info) into labeled frames.
        The inputs dicts are filled with widget references.
        """
        meta_frame = ttk.Frame(parent)
        meta_frame.grid(row=0, column=0, pady=(PAD_TOP, 0), sticky="nsew")

        client_frame  = ttk.LabelFrame(meta_frame, style=WIDGET_STYLE_FRAME, text="Client and Order Info", padding=6)
        product_frame = ttk.LabelFrame(meta_frame, style=WIDGET_STYLE_FRAME, text="Product Build Info",    padding=6)
        client_frame.grid(row=0,  column=0, sticky="nsew")
        product_frame.grid(row=0, column=1, sticky="nsew", padx=(PAD_BETWEEN, 0))

        self._draw_meta_section(client_frame,  "client_info",  client_inputs)
        self._draw_meta_section(product_frame, "product_info", product_inputs)

    def _draw_meta_section(self, frame: ttk.LabelFrame, section: str, inputs: Dict[str, Any]) -> None:
        """Internal helper to draw a two-column layout of label-entry widgets."""
        for idx, key in enumerate(self.inputs[section]):
            col = (idx % 2) * 2
            row = idx // 2
            label_text = key.replace("_", " ").title()

            label = ttk.Label(frame, style=WIDGET_STYLE_LABEL, text=label_text)
            label.grid(row=row, column=col, sticky="e", padx=PAD_X_LABEL, pady=PAD_Y)

            width = 12 if section == 'product_info' else 24
            entry = ttk.Entry(frame, style=WIDGET_STYLE_ENTRY, width=width)
            # entry = ttk.Entry(frame, style=WIDGET_STYLE_VALUE, width=width)  
            entry.insert(0, self.inputs[section][key])
            entry.configure(state=self.value_state)
            entry.grid(row=row, column=col + 1, sticky="w", padx=PAD_X_WIDGET, pady=PAD_Y)

            Tooltip(entry, META_FIELD_TOOLTIPS.get(key, key))
            inputs[key] = entry

    # ------ PARAM UPLOAD TO GUI -----------------------------------------------
    def draw_param_frames(self, parent: tk.Widget, brd_inputs: Dict[str, Any], 
                           adc_inputs: Dict[str, Any], sys_inputs: Dict[str, Any]):
        """Draw frames for board, analog and system parameters."""
        param_frame = ttk.Frame(parent)
        param_frame.grid(row=1, column=0, pady=(PAD_TOP, 0), sticky="nsew")

        brd_frame = ttk.LabelFrame(param_frame, style=WIDGET_STYLE_FRAME, text=MODULE_ALIASES["BRD"], padding=6)
        adc_frame = ttk.LabelFrame(param_frame, style=WIDGET_STYLE_FRAME, text=MODULE_ALIASES["ADC"], padding=6)
        sys_frame = ttk.LabelFrame(param_frame, style=WIDGET_STYLE_FRAME, text=MODULE_ALIASES["SYS"], padding=6)
        brd_frame.grid(row=0, column=0, sticky="nsew")
        adc_frame.grid(row=0, column=1, sticky="nsew", padx=PAD_BETWEEN)
        sys_frame.grid(row=0, column=2, sticky="nsew")

        param_frame.columnconfigure((0, 1, 2), weight=1) # 0 - BRD, 1 - ADC, 2 - SYS

        # Add an inner frame with padding
        brd_inner = ttk.Frame(brd_frame)
        brd_inner.pack(fill="both", expand=True, pady=(0, 6), padx=6)
        self._draw_simple_block(brd_inner, "BRD", brd_inputs)

        adc_inner = ttk.Frame(adc_frame)
        adc_inner.pack(fill="both", expand=True, pady=(0, 6), padx=6)
        self._draw_simple_block(adc_inner, "ADC", adc_inputs)

        sys_inner = ttk.Frame(sys_frame)
        sys_inner.pack(fill="both", expand=True, pady=(0, 6), padx=6)
        self._draw_simple_block(sys_inner, "SYS", sys_inputs)

    # -- BRD / ADC / SYS (flat) ------------------------------------------------
    def _draw_simple_block(self, parent, m_key: str, inputs: Dict[str, Any]) -> None:
        """
        Draw flat parameter fields (like BRD/ADC/SYS) using draw_widget().
        Layout is two-column for hardware_info, single-column otherwise.
        """
        mod_def = CMD_TABLE.get(m_key)
        section = PRD_INI_SECTIONS.get(m_key)
        section_dict = self.inputs.get(section, {})

        row = draw_idx = 0

        if self.setup_mode == "program":
            ttk.Label(parent, text="Parameter", style=WIDGET_STYLE_LABEL).grid(
                row=0, column=0, sticky="e", padx=PAD_X_LABEL)
            ttk.Label(parent, text="Value",     style=WIDGET_STYLE_LABEL).grid(
                row=0, column=1, sticky="w", padx=0)
            ttk.Label(parent, text="Select",    style=WIDGET_STYLE_LABEL).grid(
                row=0, column=2, sticky="w", padx=PAD_X_LABEL)
            
            if section == 'hardware_info':
                ttk.Label(parent, text="Parameter", style=WIDGET_STYLE_LABEL).grid(
                    row=0, column=3, sticky="e", padx=PAD_X_LABEL)
                ttk.Label(parent, text="Value",     style=WIDGET_STYLE_LABEL).grid(
                    row=0, column=4, sticky="w", padx=0)
                ttk.Label(parent, text="Select",    style=WIDGET_STYLE_LABEL).grid(
                    row=0, column=5, sticky="w", padx=PAD_X_LABEL)
            row = 1

        for p_key, p_def in mod_def.items():
            gui_def = p_def.get("gui")
            flat_key = p_def.get("flat_key", f"{m_key.lower()}_{p_key.lower()}")
            if flat_key in self.skip_param_keys or not gui_def:
                continue

            val = section_dict.get(flat_key, gui_def.get("default", ""))

            if section == 'hardware_info': # Two-column layout for hardware_info
                col_block = (draw_idx % 2)  # 0 or 1
                if col_block == 0 and draw_idx > 0:
                    row += 1
            else:
                col_block = 0
                row = draw_idx + 1  # +1 for header row
                
            draw_idx += 1

            if self.setup_mode == "program":
                widget, selected = draw_widget_for_program(parent, row, col_block, flat_key,
                                                gui_def, val, self.value_state)
                self.program_widgets[flat_key] = {"section": section, "widget": widget, "select": selected}
            else:
                widget = draw_widget(parent, row, col_block, flat_key, gui_def, val)
                inputs[flat_key] = widget

            if gui_def.get("tooltip"):
                Tooltip(widget, gui_def["tooltip"])

    # ------ DEFAULT LOAD ------------------------------------------------------
    def load_from_defaults(self) -> None:
        """Populate *minimal* defaults from `META_DEFINITIONS` & `CMD_TABLE`."""
        # -- Meta defaults --------------------------------------------------
        for section, defs in META_DEFINITIONS.items():
            for key, spec in defs.items():
                if key in self.skip_meta_keys:
                    continue
                self.inputs[section][key] = spec.get("default", "")
                
        self.inputs["client_info"]['source'] = "Default"
        self.inputs["client_info"]['created_on'] = datetime.now().strftime("%d %b %Y")
        
        # -- CMD_TABLE defaults ---------------------------------------------
        for mod_key, mod_def in CMD_TABLE.items():
            section = PRD_INI_SECTIONS.get(mod_key)
            if not section:
                continue
            for p_key, p_def in mod_def.items():
                gui_def = p_def.get("gui", {})
                flat_key = p_def.get("flat_key", f"{mod_key.lower()}_{p_key.lower()}")
                if flat_key in self.skip_param_keys or not gui_def:
                    continue
                self.inputs[section][flat_key] = gui_def.get("default", "")

    # ------ MASTER LOAD -------------------------------------------------------
    def load_from_master(self, full_path: str) -> bool:
        # Ask for serial number to build new device config
        self.serial_no = simpledialog.askstring("Serial Number", "Enter Device Serial Number:")

        if not self.serial_no:
            self.log_handler.log("No serial number entered. Operation cancelled.", tag="warn")
            return False

        try:
            self.serial_no = int(self.serial_no.strip())
            if not SERIAL_RANGE[0] <= self.serial_no <= SERIAL_RANGE[1]:
                raise ValueError(f"Out of range {SERIAL_RANGE}")

        except ValueError:
            messagebox.showerror("Invalid Input", f"Serial number must be an integer in range {SERIAL_RANGE}")
            return False

        try:
            self.source = full_path # needed to save back device list
            cfg = ConfigIO(self.path_handler, self.log_handler)
            self.master_inputs = cfg.load_file(full_path)

            rel_path = self.path_handler.get_relative_path(full_path)
            self.log_handler.log(f"Loaded Master config for Device: {rel_path}", tag="info")

            for section, keys in self.master_inputs.items():
                if section not in self.inputs: #or section == "device_info":
                    continue
                for key in keys:
                    if key in self.inputs[section]:
                        self.inputs[section][key] = self.master_inputs[section][key]            

            # inject serial number, which is not in master config.
            self.inputs['system_info']['sys_ser_no'] = self.serial_no

            self.inputs["client_info"]['created_on'] = datetime.now().strftime("%d %b %Y")
            self.inputs['client_info']['source'] = self.path_handler.get_file_name_only(full_path)
            return True

        except Exception as e:
            self.log_handler.log(f"Error loading Master config: {e}", tag="error")
            messagebox.showerror("Error", f"Failed to load Master config: {e}")
            return False
                
    # ------ INI LOAD ----------------------------------------------------------
    def load_from_ini(self, full_path: str) -> None:
        cfg = ConfigIO(self.path_handler, self.log_handler)
        self.inputs = cfg.load_file(full_path)
        
        # needed to save back device list, if changed to new serial number
        if self.setup_mode == "device":
            # 'source' is the master INI this device was generated from. It may
            # be absent/blank (the old default was a dict, which crashed
            # os.path.join); degrade gracefully so device edit still opens.
            file_name = self.inputs.get("client_info", {}).get('source', "")
            if not file_name:
                self.log_handler.log(
                    "Device INI has no 'source' (master) reference; "
                    "serial-usage won't be marked back to a master.", tag="warn")
                self.source = None
                self.master_inputs = {}
            else:
                self.source = os.path.join(self.config_dir, file_name)
                if os.path.exists(self.source):
                    self.master_inputs = cfg.load_file(self.source)
                else:
                    self.log_handler.log(
                        f"Master file '{file_name}' referenced by this device INI "
                        f"was not found; serial-usage won't be marked back.", tag="warn")
                    self.master_inputs = {}

    # ----- INI SAVE -----------------------------------------------------------
    def save_to_ini(self) -> None:
         # Save to file
        # str(): ConfigIO literal_eval turns purely-numeric client/order into
        # int (and "True" into bool); .lower()/.title() then crash ([T6]).
        client = str(self.inputs["client_info"].get('client', 'unknown'))
        order  = str(self.inputs["client_info"].get('order_id', '0000'))

        # Sanitize only for filename use — the unsanitized values are still
        # what gets written into the INI content itself.
        fname_client = _sanitize_filename_part(client.lower())
        fname_order  = _sanitize_filename_part(order)

        if self.setup_mode == "device":
            serial_no = self.inputs["system_info"].get('sys_ser_no', '0000')
            file_name = f"{self.setup_mode}_{fname_client}_{fname_order}_{serial_no}.ini"
        else:
            file_name = f"{self.setup_mode}_{fname_client}_{fname_order}.ini"
            
        full_path = os.path.join(self.config_dir, file_name)

        if os.path.exists(full_path):
            result = messagebox.askyesno("Overwrite File?",
                f"A file already exists:\n{file_name}\n\nDo you want to overwrite it?")
            if not result:
                return
        
        dialog  = self.setup_mode.replace("_", " ").title()
        try:
            cfg = ConfigIO(self.path_handler, self.log_handler)
            cfg.save_file(full_path, self.inputs)
            rel_path = self.path_handler.get_relative_path(full_path)
            self.log_handler.log(f"Saved {dialog} Config: {rel_path}", tag='info')
            messagebox.showinfo("Saved", f"{dialog} config saved to {rel_path}")

            if self.setup_mode == "device":
                self.mark_serial_used_in_master()

        except Exception as e:
            self.log_handler.log(f"Save {dialog} File failed: {e}", tag='error')

    # -- GUI - dict synchronisation helpers ------------------------------------
    def update_from_gui(self, client_inputs: Dict[str, Any], product_inputs: Dict[str, Any], 
                                brd_inputs: Dict[str, Any], adc_inputs: Dict[str, Any], 
                                sys_inputs: Dict[str, Any]):
        """Pull values from live GUI widgets into :pyattr:`inputs`."""
        # --- Meta section straightforward --------------------------------
        for key, widget in client_inputs.items():
            self.inputs["client_info"][key] = get_widget_value(widget)
                
        for key, widget in product_inputs.items():        
            self.inputs["product_info"][key] = get_widget_value(widget)

        #  Generation info --------------------------------------
        self.inputs["client_info"]['created_on']  = datetime.now().strftime("%d %b %Y")
 
        # --- Modules -------------------------------------------------------
        # Modules Section
        for key, widget in brd_inputs.items():
            self.inputs["hardware_info"][key] = get_widget_value(widget)
        for key, widget in adc_inputs.items():
            self.inputs["analog_info"][key] = get_widget_value(widget)
        for key, widget in sys_inputs.items():
            self.inputs["system_info"][key] = get_widget_value(widget)

    # -- DEVICE LIST helper (serial numbers) -----------------------------------
    def build_device_list(self) -> None:
        """Regenerate the device_info register from base_serial/total_qty,
        MERGING with the existing register ([T1], DECIDED 2026-07-16):
        - serials still in range keep their existing "used, <date>" value;
        - "used" entries that fall OUT of a shrunk range are KEPT (build
          history is never silently discarded);
        - only out-of-range "unused" entries are dropped.
        Previously this cleared the whole section, so editing a master reset
        every built device to "unused" and Summary flagged them YES[Error]."""
        try:
            base  = int(self.inputs["client_info"].get("base_serial", 0))
            total = int(self.inputs["client_info"].get("total_qty", 0))
        except ValueError:
            raise ValueError("Base serial / total units must be integers")

        old = self.inputs.get("device_info", {}) or {}
        new_list = {}
        for sn in range(base, base + total):
            key  = str(sn)
            prev = str(old.get(key, "unused"))
            new_list[key] = prev if prev.startswith("used") else "unused"

        # keep out-of-range USED entries (history), drop out-of-range unused
        for key, val in old.items():
            key = str(key)
            if key not in new_list and str(val).startswith("used"):
                new_list[key] = val

        self.inputs["device_info"] = new_list

    # -- Mark used in Master File of serial number -----------------------------
    def mark_serial_used_in_master(self) -> None:
        """Update the device_info section in master_inputs with current serial marked as 'used'."""
        if not self.source:
            return

        # Ensure 'device_info' section exists
        if "device_info" not in self.master_inputs:
            self.master_inputs["device_info"] = {}

        raw = self.inputs.get("system_info", {}).get("sys_ser_no")
        serial = "" if raw is None else str(raw).strip()
        if serial.isdigit():
            serial = str(int(serial))   # normalize " 105"/"0105" -> "105"
        if not serial:
            self.log_handler.log("Serial number missing, skipping device_info update.", tag="warn")
            return

        self.master_inputs["device_info"][serial] = (f"used, {datetime.now().strftime('%d %b %Y')}")
        # Check if master INI file exists
        if not os.path.exists(self.source):
            self.log_handler.log(f"Master INI file not found: {self.source}. Skipped marking serial.", tag="warn")
        else:
            try:
                cfg = ConfigIO(self.path_handler, self.log_handler)
                cfg.save_file(self.source, self.master_inputs)
                rel_path = self.path_handler.get_relative_path(self.source)
                self.log_handler.log(f"Marked SerNo {serial} as used in {rel_path}.", tag="info")
            except Exception as e:
                self.log_handler.log(f"Failed to update master device_info: {e}", tag="error")

    def get_gui_to_internal_value(self, module: str, param: str, gui_value: Any) -> Any:
        """
        Converts GUI value (e.g., dropdown label) to internal value (e.g., 'U' for USB).
        If no mapping is defined, returns the gui_value itself.
        """
        try:
            gui_def = CMD_TABLE[module][param].get("gui", {})
            options = gui_def.get("options", {})
            if gui_value not in options:
                self.log_handler.log(f"Unmapped GUI value '{gui_value}' for {module}:{param}", tag="warn")
            return options.get(gui_value, gui_value)  # fallback if no match
        except Exception as e:
            raise ValueError(f"Failed to convert GUI value for {module}:{param}: {e}")

    def get_internal_value_to_gui(self, module: str, param: str, internal_value: Any) -> Any:
        """
        Converts internal value (e.g., 'U') to GUI label (e.g., 'USB') for display.
        If no mapping exists, returns the internal value as-is.
        """
        try:
            gui_def = CMD_TABLE[module][param].get("gui", {})
            options = gui_def.get("options", {})
            # Reverse mapping: value -> label
            reverse_map = {v: k for k, v in options.items()}
            return reverse_map.get(internal_value, internal_value)
        except Exception as e:
            raise ValueError(f"Failed to map internal value to GUI label for {module}:{param}: {e}")
        
    def write_single_param(self, cmd_handler, flat_key, entry):
        """
        Perform write for a single param.
        Args:
            flat_key - e.g., 'brd_hw_cfg_rtc'
            entry - dict with ['section', 'widget', 'select']

        Returns:
            (True, validated_value) if write succeeded, (False, None) otherwise.
        """
        # Step 1: Get module name from section
        section = entry["section"]
        module  = next((k for k, v in PRD_INI_SECTIONS.items() if v == section), None)
        if module is None:
            safe_log(self.log_handler, f"[ERROR] INI {section} didn't have module", tag="error")
            return False, None

        # Step 2: Get param name from CMD_TABLE
        cmd_def = CMD_TABLE.get(module, {})
        param = next((p for p, d in cmd_def.items() if d.get("flat_key") == flat_key), None)
        if param is None:
            safe_log(self.log_handler, f"[ERROR] {section}->{module} didn't have param", tag="error")
            return False, None

        # Step 3: Check this parameter writable?
        if not CMD_TABLE[module][param].get("writable", True):
            safe_log(self.log_handler, f"[INFO] Skipping read-only param: {flat_key} ({module} -> {param})", tag="info")
            return False, None

        # Step 4: Get current value from widget
        value  = None
        widget = entry["widget"]
        
        if isinstance(widget, ttk.Entry):
            value = widget.get()
        elif hasattr(widget, "var") and isinstance(widget.var, tk.BooleanVar):
            value = "1" if widget.var.get() else "0"
        elif hasattr(widget, "var") and isinstance(widget.var, tk.StringVar):
            gui_value = widget.var.get()
            value = self.get_gui_to_internal_value(module, param, gui_value)

        try:
            # Validated locally so callers (e.g. write_and_verify_device's
            # read-back comparison) get the validated value back on success.
            # write_single_param_direct() below validates again internally
            # before sending — cheap and pure, and it keeps that function's
            # existing contract/return type untouched for its other caller,
            # write_module_direct().
            ok, validated_value = validate_param_value(module, param, value)
            if not ok:
                safe_log(self.log_handler, f"[ERROR] Value Error {flat_key}->{module}->{param}: {value}", tag="error")
                return False, None  # validation function logs internally

            # Step 5: Delegate the actual transmit to cmd_helpers' direct
            # helper instead of calling cmd_handler.set_remote_value()
            # directly. The old code here never special-cased a "WAIT"
            # (session-mode) reply — it fell straight into the failure
            # branch — unlike write_single_param_direct(), which already
            # polls correctly via _wait_for_last_reply(). See CLAUDE.md
            # known issues ("last_reply is confirmed unconsumed" /
            # write_module_direct correction). Currently unreachable in
            # practice since VibMTool never enables session mode, but this
            # removes the duplicate/incorrect logic rather than leaving a
            # latent trap plus two implementations to keep in sync.
            success = write_single_param_direct(cmd_handler, self.log_handler, module, param, validated_value)
            return success, (validated_value if success else None)

        except Exception as e:
            safe_log(self.log_handler, f"[EXCEPTION] {flat_key} write failed: {e}", tag="error")
            return False, None
    
    def read_single_param(self, cmd_handler, flat_key, entry):
        """
        Read a single parameter from remote, validate it, and update the GUI widget.
        Args:
            flat_key - e.g., 'brd_hw_cfg_rtc'
            entry - dict with ['section', 'widget', 'select']
        Returns:
            (True, validated_value) if read succeeded and widget updated, (False, None) otherwise.
        """
        # Step 1: Get module name from section
        section = entry["section"]
        module = next((k for k, v in PRD_INI_SECTIONS.items() if v == section), None)
        if module is None:
            safe_log(self.log_handler, f"[ERROR] INI section '{section}' has no mapped module", tag="error")
            return False, None

        # Step 2: Get param name from CMD_TABLE
        cmd_def = CMD_TABLE.get(module, {})
        param = next((p for p, d in cmd_def.items() if d.get("flat_key") == flat_key), None)
        if param is None:
            safe_log(self.log_handler, f"[ERROR] {module} has no parameter for flat_key: {flat_key}", tag="error")
            return False, None

        # Step 3: Delegate the actual read to cmd_helpers' direct helper.
        # read_single_param_direct() already validates and correctly polls
        # for a "WAIT" (session-mode) reply via _wait_for_last_reply(); the
        # old code here called cmd_handler.get_remote_value() directly and
        # fed a literal "WAIT" string straight into validate_param_value(),
        # which logged it as a validation failure instead of a pending
        # reply. See CLAUDE.md known issues. Currently unreachable in
        # practice (VibMTool never enables session mode), but this removes
        # the duplicate/incorrect logic rather than leaving it as a trap.
        try:
            success, validated_value = read_single_param_direct(cmd_handler, self.log_handler, module, param)
        except Exception as e:
            safe_log(self.log_handler, f"[EXCEPTION] {flat_key} read failed: {e}", tag="error")
            success, validated_value = False, None

        widget = entry["widget"]

        if not success:
            # GUI cleanup on failure
            if isinstance(widget, ttk.Entry):
                widget.delete(0, tk.END)
            elif hasattr(widget, "var"):
                widget.var.set("")  # Clear checkbox / dropdown / string
            return False, None

        # Step 4: Update the received value to widget
        # --- Update GUI widget ---
        param_info = cmd_def[param]
        gui_def = param_info.get("gui", {})

        if isinstance(widget, ttk.Entry):
            widget.delete(0, tk.END)
            widget.insert(0, str(validated_value))

        elif hasattr(widget, "var") and isinstance(widget.var, tk.BooleanVar):
            widget.var.set(bool(int(validated_value)))  # Ensure 1/0 gets converted properly

        elif hasattr(widget, "var") and isinstance(widget.var, tk.StringVar):
            # Convert internal value (e.g., 'U') to display label (e.g., 'USB') if options exist
            gui_value = self.get_internal_value_to_gui(module, param, validated_value)
            widget.var.set(gui_value)

        else:
            safe_log(self.log_handler, f"[WARN] Unknown widget type for {flat_key}", tag="warn")

        safe_log(self.log_handler, f"[INFO] Read success: {module} -> {param} = {validated_value}", tag="info")

        return True, validated_value
    
#-------------------------------------------------------------------------------
# Class: SetupManager
#-------------------------------------------------------------------------------
class SetupManager:
    """
    Launch point for master/device config setup.
    Prompts user for mode (New or Edit) and opens SetupDialog.
    """
    def __init__(self, parent, log_handler, path_handler,
                    setup_mode: str = "master", cmd_handler = None):
        self.parent       = parent
        self.log_handler  = log_handler
        self.path_handler = path_handler
        self.setup_mode   = setup_mode
        self.cmd_handler  = cmd_handler
        
        self.new_setup = None
        self.completed = False   # True once the SetupDialog actually opened
        self.config_dir  = path_handler.get_config_path()
        self._run()

    # -------------------------------------------------------------------
    def _run(self):
        """Prompt user for New/Edit mode and select config file accordingly."""
        title = f"{self.setup_mode.replace('_', ' ').title()} Setup"

        if self.setup_mode == "master" or self.setup_mode == "device":
            question = f"Do you want a NEW {title} Config?\n\nYes = New\nNo  = Edit existing\nCancel = Abort"

        else: # program mode
            question = f"Do you want Program from?\n\nYes = Defaults\nNo  = Device INI\nCancel = Abort"
            
        # askyesnocancel: returns None on Cancel/window-X, making the branch
        # below LIVE — askyesno could only return True/False, so the None
        # check was dead and there was no way to back out of this prompt
        # (the branch's evident original intent was a real cancel path).
        self.new_setup = messagebox.askyesnocancel(
            title,
            question,
        )

        if self.new_setup is None:
            self.log_handler.log(f"{title} cancelled.", tag="warn")
            return

        # Set filename pattern based on mode and new_setup
        if self.new_setup:   # New - master and program from default, Device from master
            if self.setup_mode == "master" or self.setup_mode == "program":
                dialog_title = None
                file_pattern = None
            else:
                dialog_title = "Select existing Master INI"
                file_pattern = "master_*.ini"

        else:   # Edit Master/Device, build from device
            if self.setup_mode == "master" or self.setup_mode == "device": 
                dialog_title = f"Select Existing {title}"
                file_pattern = f"{self.setup_mode}_*.ini"
            
            else:  # program
                dialog_title = "Select Device INI"
                file_pattern = "device_*.ini"

        setup_path = None
        if dialog_title != None:
            setup_path = filedialog.askopenfilename(
                title=dialog_title,
                initialdir=self.config_dir,
                filetypes=[("INI Files", file_pattern)]
            )
            if not setup_path:
                self.log_handler.log(f"Edit {title} cancelled.", tag="warn")
                return

        dialog = SetupDialog(
            self.parent,
            self.log_handler,
            self.path_handler,
            self.setup_mode,
            self.cmd_handler,
            setup_path,
            self.new_setup,
        )
        # SetupDialog can abort before creating its window (e.g. [T4]
        # cancelled serial prompt) — only then is .opened left False.
        self.completed = getattr(dialog, 'opened', False)

#-------------------------------------------------------------------------------
# Class: SetupDialog
#-------------------------------------------------------------------------------
class SetupDialog:
    """
    Modal dialog for creating/editing config files.
    Handles GUI layout, widget binding, and save logic.
    """
    def __init__(self, parent, log_handler, path_handler, setup_mode,
                                cmd_handler= None,
                                setup_path = None, new_setup = None):
        # Store
        self.parent       = parent
        self.log_handler  = log_handler
        self.path_handler = path_handler
        self.setup_mode   = setup_mode
        self.cmd_handler  = cmd_handler
        self.setup_path   = setup_path
        self.new_setup    = new_setup
        self.config_dir   = path_handler.get_config_path()
        self.opened       = False   # set True once the Toplevel is created

        self.select_all_state = tk.BooleanVar(value=True)
 
        # Unified data object -------------------------------------------
        self.im = InputManager(config_dir = self.config_dir,
                                log_handler = self.log_handler, path_handler = self.path_handler,
                                setup_mode = self.setup_mode, is_new_setup = self.new_setup)
        
        prefix = self.setup_mode.replace("_", " ").title()

        if self.setup_mode == 'master':
            rel_path = self.path_handler.get_relative_path(self.setup_path)
            if self.new_setup: # from defaults
                self.im.load_from_defaults()
                self.log_handler.log(f"Loaded Default Master Config", tag='info')
                
            else:   # edit mode
                self.im.load_from_ini(self.setup_path)
                self.log_handler.log(f"Loaded Exiting {prefix} Config from: {rel_path}", tag='info')
            
        elif self.setup_mode == 'device':
            rel_path = self.path_handler.get_relative_path(self.setup_path)
            if self.new_setup: # from Master, default also needed to populated missing keys
                self.im.load_from_defaults()
                if not self.im.load_from_master(self.setup_path):
                    # Serial prompt cancelled/invalid or master unreadable —
                    # abort instead of opening the dialog on pure defaults and
                    # logging a misleading "Loaded" message ([T4]).
                    self.log_handler.log(f"{prefix} setup aborted — master not applied.", tag="warn")
                    return
                self.log_handler.log(f"Loaded {prefix} Config from: {rel_path}", tag='info')
            else:
                self.im.load_from_ini(self.setup_path)
                self.log_handler.log(f"Loaded Exiting {prefix} Config from: {rel_path}", tag='info')

        elif self.setup_mode == 'program':
            rel_path = self.path_handler.get_relative_path(self.setup_path)

            if self.new_setup: # from defaults
                self.im.load_from_defaults()
                self.log_handler.log(f"Loaded Default Master Config", tag='info')
                
            else:   # from device ini   
                self.im.load_from_ini(self.setup_path)
                self.log_handler.log(f"Loaded Exiting {prefix} Config from: {rel_path}", tag='info')

        else:
            self.log_handler.log(f"{prefix} not defined", tag='warn')

        self.parent.update()  # ensures Tk tear-down after askstring
        
        # TK window ------------------------------------------------------
        self.window = tk.Toplevel(self.parent)
        self.opened = True
        ProductMeta.set_icon(self.window)
        self.window.title(f"{prefix} Setup")
        self.window.geometry("800x400")

        # Parent Container frame -----------------------------------------
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill="both", expand=True, padx=PAD_SIDE, pady=PAD_TOP)

        # GUI input containers -------------------------------------------------
        self.client_inputs  = {}
        self.product_inputs = {}
        self.brd_inputs     = {}
        self.adc_inputs     = {}
        self.sys_inputs     = {}

        self.im.draw_meta_block(main_frame, self.client_inputs, self.product_inputs)

        # Parameters -----------------------------------------------------------
        self.im.draw_param_frames(main_frame, self.brd_inputs, self.adc_inputs, self.sys_inputs)

        if self.setup_mode == "program":
            self._draw_program_footer_buttons(main_frame)

        else:
            self._draw_footer_buttons(main_frame)

        finalize_geometry(self.window)

    # Save / Cancel Buttons ----------------------------------------------------
    def _draw_footer_buttons(self, main_frame):
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, pady=(PAD_BOTTOM, 0), sticky="ew")

        btn_save = ttk.Button(btn_frame, style=WIDGET_STYLE_BUTTON, text="Save", width=12, 
                   command=self._on_save, cursor="hand2")
        btn_save.pack(side="left",padx=(0, PAD_SIDE))
        apply_tooltip(btn_save, "Save", PROGRAM_KEY_TOOLTIPS)
        
        btn_cancel = ttk.Button(btn_frame, style=WIDGET_STYLE_BUTTON, text="Cancel", width=12, 
                    command=self.window.destroy, cursor="hand2")
        btn_cancel.pack(side="right", padx=(PAD_SIDE, 0))
        apply_tooltip(btn_cancel, "Cancel", PROGRAM_KEY_TOOLTIPS)

    # Write/Read/Verify/Cancel Buttons -----------------------------------------
    def _draw_program_footer_buttons(self, main_frame):
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, pady=(PAD_BOTTOM, 0), sticky="ew")
        
        # Select All button at left
        self.btn_select = ttk.Button(btn_frame, text="Deselect All", width=12,
                        command=self.toggle_select_all, cursor="hand2",
                        style=WIDGET_STYLE_BUTTON, takefocus=False)
        self.btn_select.pack(side="left", padx=(0, PAD_SIDE))
        apply_tooltip(self.btn_select, "select_all", PROGRAM_KEY_TOOLTIPS)
        
        for label, command in [
            ("Write",           self.write_to_device),
            ("Read",            self.read_from_device),
            ("Write & Verify",  self.write_and_verify_device),
            ("Save Report",     self.save_device_report)
        ]:
            btn = ttk.Button(btn_frame, text=label, width=12, command=command,
                            cursor="hand2", style=WIDGET_STYLE_BUTTON, takefocus=False)
            btn.pack(side="left", padx=(0, PAD_SIDE))
            apply_tooltip(btn, label, PROGRAM_KEY_TOOLTIPS)

        # Cancel button at far right
        btn = ttk.Button(btn_frame, text="Cancel", width=12,
                   command=self.window.destroy, cursor="hand2",
                   style=WIDGET_STYLE_BUTTON, takefocus=False)
        btn.pack(side="right", padx=(PAD_SIDE, 0))
        apply_tooltip(btn, "Cancel", PROGRAM_KEY_TOOLTIPS)
 
    def toggle_select_all(self):
        new_state = self.select_all_state.get()  # Get current mode (True = select all)

        new_state = True if not new_state else False

        for entry in self.im.program_widgets.values():
            entry["select"].set(new_state)
        
        # Flip state for next click
        self.select_all_state.set(new_state)

        # Update button text based on current state
        if new_state:
            self.btn_select.config(text="Deselect All")
        else:
            self.btn_select.config(text="Select All")

    def _get_serial_from_widget(self):
        """Validated serial from the sys_ser_no widget -> (ok, int).
        Guards the previously-unchecked int() that crashed the Tk callback
        silently on empty/non-numeric input, and applies SERIAL_RANGE, which
        was only enforced on the load_from_master prompt path ([T2])."""
        raw = self.im.program_widgets['sys_ser_no']['widget'].get()
        try:
            serial_no = int(str(raw).strip())
            if not SERIAL_RANGE[0] <= serial_no <= SERIAL_RANGE[1]:
                raise ValueError(f"out of range {SERIAL_RANGE}")
        except (ValueError, TypeError):
            msg = f"Serial number must be an integer in range {SERIAL_RANGE} (got: '{raw}')"
            self.log_handler.log(f"[ERROR] {msg}", tag="error")
            messagebox.showerror("Invalid Serial Number", msg)
            return False, None
        return True, serial_no

    def write_to_device(self):
        """Write selected parameters to the connected device."""

        if not any(entry["select"].get() for entry in self.im.program_widgets.values()):
            self.log_handler.log("No parameters selected to process.", tag="warn")
            messagebox.showwarning("Warning", "No parameters selected to process.")
            return  # or handle gracefully depending on context
        
        ok, serial_no = self._get_serial_from_widget()
        if not ok:
            return
        if get_sys_value("sys_ser_no") != serial_no:   # full INI rewrite only on change
            set_sys_value("sys_ser_no", serial_no)
        
        for flat_key, entry in self.im.program_widgets.items():
            if entry["select"].get():
                success, _ = self.im.write_single_param(self.cmd_handler, flat_key, entry)
                # per-param outcome already logged by write_single_param;
                # the old ["status"] store here was write-only ([T7])
                
    def read_from_device(self):
        """Read selected parameters from the connected device."""

        if not any(entry["select"].get() for entry in self.im.program_widgets.values()):
            self.log_handler.log("No parameters selected to process.", tag="warn")
            messagebox.showwarning("Warning", "No parameters selected to process.")
            return  # or handle gracefully depending on context
        
        ok, serial_no = self._get_serial_from_widget()
        if not ok:
            return
        if get_sys_value("sys_ser_no") != serial_no:   # full INI rewrite only on change
            set_sys_value("sys_ser_no", serial_no)
        
        for flat_key, entry in self.im.program_widgets.items():
            if entry["select"].get():
                success, _ = self.im.read_single_param(self.cmd_handler, flat_key, entry)
                # per-param outcome already logged by read_single_param;
                # the old ["status"] store here was write-only ([T7])

    def write_and_verify_device(self):
        """Perform write + read-back verification for selected parameters."""
        if not any(entry["select"].get() for entry in self.im.program_widgets.values()):
            self.log_handler.log("No parameters selected to process.", tag="warn")
            messagebox.showwarning("Warning", "No parameters selected to process.")
            return

        ok, serial_no = self._get_serial_from_widget()
        if not ok:
            return
        if get_sys_value("sys_ser_no") != serial_no:   # full INI rewrite only on change
            set_sys_value("sys_ser_no", serial_no)

        self.im.verification_results = {}  # Clear old results

        for flat_key, entry in self.im.program_widgets.items():
            if not entry["select"].get():
                self.im.verification_results[flat_key] = ("N/A", "N/A", "N/A")    
                continue

            # --- Write operation ---
            write_ok, written_value = self.im.write_single_param(self.cmd_handler, flat_key, entry)
            if not write_ok:
                self.im.verification_results[flat_key] = ("FAIL", "N/A", "N/A")
                self.log_handler.log(f"[ERROR] Failed to write {flat_key}", tag="error")
                logging.info(f"{flat_key} not written to device")
                continue

            # --- Read-back operation ---
            read_ok, read_value = self.im.read_single_param(self.cmd_handler, flat_key, entry)
            if not read_ok:
                self.im.verification_results[flat_key] = ("FAIL", written_value, "N/A")
                self.log_handler.log(f"[ERROR] Failed to read {flat_key} after write", tag="error")
                logging.info(f"{flat_key} read-back failed")
                continue

            # --- Compare written vs read values ---
            status = "PASS" if str(written_value) == str(read_value) else "FAIL"
            self.im.verification_results[flat_key] = (status, written_value, read_value)

            # Log the result (GUI + file)
            log_color = "info" if status == "PASS" else "error"
            self.log_handler.log(
                f"[VERIFY] {flat_key} -> {status} (Wrote: {written_value}, Read: {read_value})",
                tag=log_color
            )
            logging.info(f"[VERIFY] {flat_key}: {status} - Wrote: {written_value}, Read: {read_value}")

    def save_device_report(self):
        """
        Save the Build Verification Report as a text file.
        Collects GUI inputs and verification results.
        """
        # --- Step 1: Update GUI data to internal dicts ---
        self.im.update_from_gui(self.client_inputs, self.product_inputs, 
                                self.brd_inputs, self.adc_inputs, self.sys_inputs)

        # --- Step 2: Get meta info ---
        client    = self.im.inputs["client_info"].get('client',     'Client')
        order_id  = self.im.inputs["client_info"].get('order_id',   'Order_Id')
        serial_no = self.im.inputs["system_info"].get('sys_ser_no', 'Ser_no')
        timestamp = datetime.now().strftime("%d %b %Y %I:%M:%S %p")
        self.im.inputs["client_info"]["created_on"] = timestamp

        # --- Step 3: Prepare output file name ---
        filename = f"build_{_sanitize_filename_part(client)}_{_sanitize_filename_part(order_id)}_{serial_no}.txt"
        file_path = os.path.join(self.config_dir, filename)
        if not _confirm_overwrite(file_path):
            return

        # --- Step 4: Collect all input dictionaries ---
        all_sections = [
            ("Client Info",    self.im.inputs["client_info"]),
            ("Product Info",   self.im.inputs["product_info"]),
            ("Board Params",   self.im.inputs["hardware_info"]),
            ("ADC Params",     self.im.inputs["analog_info"]),
            ("System Params",  self.im.inputs["system_info"]),
        ]
        
        # Open file for writing
        with open(file_path, "w", encoding="utf-8") as f:
            
            f.write("Build Verification Report\n")
            # Write meta sections - Client and Product
            for title, section in all_sections[:2]:
                f.write("-" * 80 + "\n")
                f.write(f"{title}:\n")
                for k, v in section.items():
                    f.write(f"  {k:<20}: {v}\n")
                f.write("\n")
                
            # Column header
            f.write("-" * 80 + "\n")
            f.write("Parameters Info\n")
            f.write(f"{'No.':<4} {'Module':<8} {'Parameter':<10} {'Value':<8} {'Selected':<8} {'Status':<8} {'Written':<10} {'Read':<8} {'Remark'}\n")
            f.write("-" * 80 + "\n")

            # Write each parameter
            for idx, (flat_key, result) in enumerate(self.im.verification_results.items(), 1):
                widget_info = self.im.program_widgets.get(flat_key)
                if not widget_info:
                    continue

                section = widget_info.get("section")
                gui_val = self.im.inputs.get(section, {}).get(flat_key, "N/A")

                module  = next((k for k, v in PRD_INI_SECTIONS.items() if v == section), section)
                cmd_def = CMD_TABLE.get(module, {})
                param   = next((p for p, d in cmd_def.items() if d.get("flat_key") == flat_key), flat_key)

                status, written, read = result
                selected = "Yes" if status != "N/A" else "No"

                # Stringify written/read values
                w_str = str(written) if written is not None else "-"
                r_str = str(read) if read is not None else "-"

                # Row write
                mark = " <== FAIL" if status == "FAIL" else ""
                f.write(f"{idx:<4} {module:<8} {param:<10} {gui_val:<8} {selected:<8} {status:<8} {w_str:<10} {r_str:<8}{mark}\n")
                
                # f.write(f"{idx:<4} {module:<10} {param:<10} {gui_val:<10} {selected:<10} {status:<8} {w_str:<10} {r_str:<10}\n")

            f.write("-" * 80 + "\n")
            f.write("End of Report\n")

        # Log and inform
        self.log_handler.log(f"[INFO] Build report saved to: {file_path}", tag="info")
        logging.info(f"Build verification report saved: {file_path}")

    # -- SAVE ------------------------------------------------------------------
    def _on_save(self):
        """Save config to INI and close window."""
        try:
            # 1) Pull values -------------------------------------------------
            self.im.update_from_gui(self.client_inputs, self.product_inputs, 
                                    self.brd_inputs, self.adc_inputs, self.sys_inputs)
            # 2) Device list -------------------------------------------------
            if self.setup_mode == 'master':
                self.im.build_device_list()
            # 3) Save INI ----------------------------------------------------
            self.im.save_to_ini()
            # 4) Close Window-------------------------------------------------
            self.window.destroy()

        except Exception as e:
            messagebox.showerror("Error", str(e))

#-------------------------------------------------------------------------------
# Class: SummaryDialog
#-------------------------------------------------------------------------------
class SummaryDialog:
    """
    Dialog that loads a master config and compares it with available device files.
    Provides export options in text, CSV, and PDF formats.
    """
    def __init__(self, parent, log_handler, path_handler):
        self.parent = parent
        self.log_handler  = log_handler
        self.path_handler = path_handler
        self.config_dir   = self.path_handler.get_config_path()

        self.inputs = {
            v: {} for v in PRD_INI_SECTIONS.values() if v not in SUMMARY_SKIP_SECTION
        }
        self.metadata_hdr = []
        self.client_info = {}
        self.export_file = None
        self.displayed_serials = set()   # exists even if load_master_file() fails
        self.completed = False           # True once the master loaded cleanly
        self.start()

    #---------------------------------------------------------------------------
    def start(self):
        """Prompt to select master INI file and initialize display."""
        self.log_handler.log("Load Master File", tag="info")
        self.master_file = filedialog.askopenfilename(
            title="Select Master File",
            initialdir=self.config_dir,
            filetypes=[("INI Files", "master_*.ini")]
        )
        if not self.master_file:
            self.log_handler.log("No master file selected.", tag="warn")
            return

        self._init_ui()
        self.completed = self.load_master_file(self.master_file)

    #---------------------------------------------------------------------------
    def _init_ui(self):
        """Build the UI layout for summary tree and buttons."""
        # TK window ------------------------------------------------------
        self.window = tk.Toplevel(self.parent)
        ProductMeta.set_icon(self.window)
        self.window.title("Summary Report")
        self.window.geometry("700x500")

        # Parent Container frame -----------------------------------------
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill="both", expand=True, padx=PAD_SIDE, pady=PAD_TOP)

        # Header label (loaded master info)
        self.hdr_label = ttk.Label(main_frame, text="Loaded Master: N/A", font=STATUS_FONT)
        self.hdr_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        # Treeview + scrollbar frame
        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        main_frame.rowconfigure(1, weight=1)  # allow expansion
        main_frame.columnconfigure(0, weight=1)

        style = ttk.Style(main_frame)
        style.configure("Treeview", font=STATUS_FONT)
        style.configure("Treeview.Heading", font=STATUS_FONT)

        self.tree = ttk.Treeview(tree_frame, columns=("Serial", "Status", "Created", "File"), show="headings")
        for col, label, width in [
            ("Serial",  "Serial Number", 100),
            ("Status",  "Device Status", 100),
            ("Created", "Created On",   120),
            ("File",    "Device File",   120)
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="center")

        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # Buttons frame — packed to the right
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, sticky="e", pady=(PAD_TOP, PAD_BOTTOM))
        for label, cmd in [
            ("Export Text", self.export_text),
            ("Export CSV", self.export_csv),
            ("Export PDF", self.export_pdf)
        ]:
            ttk.Button(
                btn_frame, style=WIDGET_STYLE_BUTTON, text=label,
                width=12,  command=cmd, cursor="hand2"
            ).pack(side="left", padx=(PAD_SIDE, 0))

    #---------------------------------------------------------------------------
    def generate_metadata_header(self) -> list:
        """Return a list of formatted metadata lines for export headers."""
        # str() guards — see [T6]; this runs OUTSIDE export_text's try, so an
        # AttributeError here was previously uncaught.
        client   = str(self.client_info.get("client", "unknown")).title()
        order_id = str(self.client_info.get("order_id", "0000"))
        created  = datetime.now().strftime("%d %b %Y %H:%M:%S")
        master   = os.path.basename(self.master_file)
        self.export_file = f"summary_{_sanitize_filename_part(client.lower())}_{_sanitize_filename_part(order_id)}"

        self.metadata_hdr = [
            "Production Summary",
            f"Client       : {client}",
            f"Order ID     : {order_id}",
            f"Created On   : {created}",
            f"Master File  : {master}",
        ]

#-------------------------------------------------------------------------------
    def load_master_file(self, master_file):
        """
        Load and display information from the selected Master INI file.
        Populates the Treeview with device serials listed in the master and
        any matching or extra device files found in the config directory.
        """
        try:
		    # --- Load master file ---
            cfg = ConfigIO(self.path_handler, self.log_handler)
            self.master_inputs = cfg.load_file(master_file)

            # Extract client and device info
            self.client_info = self.master_inputs.get("client_info", {})
            self.device_info = self.master_inputs.get("device_info", {})
            # str() guard — [T6] gap: this site was missed in the Phase-1
            # consumer fixes; a purely-numeric client name crashed the whole
            # summary load via the outer except.
            client   = str(self.client_info.get("client", "unknown")).title()
            order_id = str(self.client_info.get("order_id", "0000"))

            # Update GUI and log
            self.hdr_label.config(text=f"Loaded Master: {client} - Order ID: {order_id}")
            rel_path = self.path_handler.get_relative_path(master_file)
            self.log_handler.log(f"Loaded Master config: {rel_path}", tag="info")

            # --- Scan device_*.ini files in config directory ---
            device_files_found = {}

            for fname in os.listdir(self.config_dir):
                if fname.startswith("device_") and fname.endswith(".ini"):
                    # Format: device_<client>_<order_id>_<serial>.ini — client/order
                    # are free text and may themselves contain "_", so the serial
                    # is extracted via an anchored regex on the trailing numeric
                    # group rather than a fixed split-position (parts[3]), which
                    # silently returned the wrong field (or raised IndexError) for
                    # any client/order containing an underscore.
                    match = DEVICE_FILENAME_RE.match(fname)
                    if not match:
                        self.log_handler.log(
                            f"Skipping unrecognized device file (couldn't parse serial): {fname}",
                            tag="warn")
                        continue
                    serial = match.group(1)
                    fpath  = os.path.join(self.config_dir, fname)
                    try:
                        cfg = ConfigIO(self.path_handler, self.log_handler)
                        dev_cfg = cfg.load_file(fpath)
                        dt = dev_cfg.get("client_info", {}).get("created_on", "Missing Date")
                    except Exception:
                        dt = "Not readable"
                    device_files_found[serial] = dt

            # --- Populate Treeview from master file entries ---
            for row in self.tree.get_children():
                self.tree.delete(row)

            self.displayed_serials = set()

            for sn, entry in sorted(self.device_info.items(), key=lambda x: _serial_sort_key(x[0])):
                parts  = entry.split(",", 1)
                status = parts[0].strip()
                date   = parts[1].strip() if len(parts) > 1 else ""

                if status == "used":
                    gen_on = date if date else "Date Missing"
                    file_status = "Yes" if sn in device_files_found else "No"

                elif status == "unused":
                    if sn in device_files_found:
                        # Device file exists but should not
                        gen_on = device_files_found[sn]
                        file_status = "YES[Error]"
                    else:
                        gen_on = "Not prepared"
                        file_status = "--"
                else:
                    gen_on = "Invalid status"
                    file_status = "?"

                self.tree.insert("", "end", values=(sn, status, gen_on, file_status))
                self.displayed_serials.add((sn, status, gen_on, file_status))

            # --- Handle extra device files not listed in master ---
            if IS_ENABLED("ENABLE_EXTRA_DEVICE"):
                existing_serials = {row[0] for row in self.displayed_serials}
                for sn, created in sorted(device_files_found.items(), key=lambda x: _serial_sort_key(x[0])):
                    if sn not in existing_serials:
                        self.tree.insert("", "end", values=(sn, "extra", created, "Yes"))
                        self.displayed_serials.add((sn, "extra", created, "Yes"))

            return True

        except Exception as e:
            self.log_handler.log(f"Failed to load master file: {e}", tag="error")
            messagebox.showerror("Error", f"Could not load Master file:\n{e}")
            return False

    #---------------------------------------------------------------------------
    def export_text(self):
        """
        Export the displayed serials summary to a TXT file.

        The file includes client/order metadata, a timestamp, and a table listing
        each device's serial number, status, creation date, and file availability.
        """
        if not self.displayed_serials:
            messagebox.showwarning("Warning", "No data to export.")
            return

        self.generate_metadata_header()
        file_name = f"{self.export_file}.txt"
        full_path = os.path.join(self.config_dir, file_name)
        if not _confirm_overwrite(full_path):
            return

        try:
            with open(full_path, "w", encoding="utf-8") as f:
                # --- Metadata Header ---
                for line in self.metadata_hdr:
                    f.write(line + "\n")
                f.write("\n")

                f.write("{:<15}{:<20}{:<20}{}\n".format("Serial No.", "Device Status", "Created On", "File"))
                f.write("=" * 70 + "\n")
                for sn, status, created, file in sorted(self.displayed_serials, key=lambda x: _serial_sort_key(x[0])):
                    f.write("{:<15}{:<20}{:<20}{}\n".format(sn, status, created, file))
                
            self.log_handler.log(f"Text Summary exported to: {file_name}", tag="info")
            messagebox.showinfo("Exported", f"Summary saved to {file_name}")

        except Exception as e:
            self.log_handler.log(f"Failed to export summary: {e}", tag="error")
            messagebox.showerror("Export Error", f"Failed to save summary:\n{e}")

    #---------------------------------------------------------------------------
    def export_csv(self):
        """
        Export the displayed serials summary to a CSV file.

        The CSV includes client/order metadata followed by tabular rows
        for each device's serial number, status, creation date, and file status.
        """
        import csv

        if not self.displayed_serials:
            messagebox.showwarning("Warning", "No data to export.")
            return

        self.generate_metadata_header()
        file_name = f"{self.export_file}.csv"
        full_path = os.path.join(self.config_dir, file_name)
        if not _confirm_overwrite(full_path):
            return

        try:
            with open(full_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # --- Metadata Header ---
                for line in self.metadata_hdr:
                    writer.writerow([line])
                writer.writerow([])

                # --- Table Header and Data Rows ---
                writer.writerow(["Serial No.", "Device Status", "Created On", "File"])
                for sn, status, created, file in sorted(self.displayed_serials, key=lambda x: _serial_sort_key(x[0])):
                    writer.writerow([sn, status, created, file])

            self.log_handler.log(f"CSV summary exported to: {file_name}", tag="info")
            messagebox.showinfo("Exported", f"CSV summary saved to {file_name}")

        except Exception as e:
            self.log_handler.log(f"Failed to export CSV: {e}", tag="error")
            messagebox.showerror("Export Error", f"Failed to save CSV:\n{e}")

    #---------------------------------------------------------------------------
    def export_pdf(self):
        """
        Export the displayed serials summary to a formatted PDF (A4 size).
        Uses matplotlib to render monospaced tabular data onto a page.
        """
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages

        if not self.displayed_serials:
            messagebox.showwarning("Warning", "No data to export.")
            return

        self.generate_metadata_header()
        file_name = f"{self.export_file}.pdf"
        full_path = os.path.join(self.config_dir, file_name)
        if not _confirm_overwrite(full_path):
            return

        try:
            with PdfPages(full_path) as pdf:
                fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4 portrait in inches
                ax.axis("off")

                # --- Prepare Content ---
                lines = self.metadata_hdr
                lines.append("")
                lines.append("{:<15}{:<20}{:<20}{}".format("Serial No.", "Device Status", "Created On", "File"))
                lines.append("=" * 70)
                for sn, status, created, file in sorted(self.displayed_serials, key=lambda x: _serial_sort_key(x[0])):
                    lines.append("{:<15}{:<20}{:<20}{}".format(sn, status, created, file))

                # --- Insert Text ---
                fig.text(0.1, 0.95, "\n".join(lines), fontsize=9, va='top', family='monospace')
                pdf.savefig(fig)
                plt.close(fig)

            self.log_handler.log(f"PDF summary exported to: {file_name}", tag="info")
            messagebox.showinfo("Exported", f"PDF summary saved to {file_name}")

        except Exception as e:
            self.log_handler.log(f"Failed to export PDF: {e}", tag="error")
            messagebox.showerror("Export Error", f"Failed to save PDF:\n{e}")
