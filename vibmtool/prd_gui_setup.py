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
import logging
import tkinter as tk
from datetime  import datetime
from typing    import Any, Dict
from tkinter   import ttk, messagebox, filedialog, simpledialog

from productiontool.prd_gui_meta   import *
from common.utils.gui_utils    import *
from common.utils.utils_helpers import *
from common.utils.config_io    import ConfigIO
from productiontool.prd_features   import IS_ENABLED
from common.core.product_meta  import ProductMeta
from common.modules.cmd_remote import CMD_TABLE, MODULE_ALIASES
from common.core.sys_config    import set_sys_value

#-------------------------------------------------------------------------------
# Validation constraints for serial number
#-------------------------------------------------------------------------------
SERIAL_RANGE = CMD_TABLE["SYS"]["SER_NO"].get("range", (0, 9999))

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
                        setup_mode: str = "master", state_write: str = "True"):
        
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
            self.value_state = "normal" if state_write else "readonly"  

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
    def load_from_master(self, full_path: str) -> None:
        # Ask for serial number to build new device config
        self.serial_no = simpledialog.askstring("Serial Number", "Enter Device Serial Number:")

        if not self.serial_no:
            self.log_handler.log("No serial number entered. Operation cancelled.", tag="warn")
            return

        try:
            self.serial_no = int(self.serial_no.strip())
            if not SERIAL_RANGE[0] <= self.serial_no <= SERIAL_RANGE[1]:
                raise ValueError(f"Out of range {SERIAL_RANGE}")

        except ValueError:
            messagebox.showerror("Invalid Input", f"Serial number must be an integer in range {SERIAL_RANGE}")
            return

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

        except Exception as e:
            self.log_handler.log(f"Error loading Master config: {e}", tag="error")
            messagebox.showerror("Error", f"Failed to load Master config: {e}")
            return
                
    # ------ INI LOAD ----------------------------------------------------------
    def load_from_ini(self, full_path: str) -> None:
        cfg = ConfigIO(self.path_handler, self.log_handler)
        self.inputs = cfg.load_file(full_path)
        
        # needed to save back device list, if changed to new serial number
        if self.setup_mode == "device":
            file_name   = self.inputs["client_info"].get('source', {})
            self.source = os.path.join(self.config_dir, file_name)
            self.master_inputs = cfg.load_file(self.source) 

    # ----- INI SAVE -----------------------------------------------------------
    def save_to_ini(self) -> None:
         # Save to file
        client = self.inputs["client_info"].get('client', 'unknown')
        order  = self.inputs["client_info"].get('order_id', '0000')

        if self.setup_mode == "device":
            serial_no = self.inputs["system_info"].get('sys_ser_no', '0000')
            file_name = f"{self.setup_mode}_{client.lower()}_{order}_{serial_no}.ini"
        else:
            file_name = f"{self.setup_mode}_{client.lower()}_{order}.ini"
            
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
        try:
            base  = int(self.inputs["client_info"].get("base_serial", 0))
            total = int(self.inputs["client_info"].get("total_qty", 0))
        except ValueError:
            raise ValueError("Base serial / total units must be integers")

        self.inputs["device_info"].clear()
        for sn in range(base, base + total):
            self.inputs["device_info"][str(sn)] = "unused"

    # -- Mark used in Master File of serial number -----------------------------
    def mark_serial_used_in_master(self) -> None:
        """Update the device_info section in master_inputs with current serial marked as 'used'."""
        if not self.source:
            return

        # Ensure 'device_info' section exists
        if "device_info" not in self.master_inputs:
            self.master_inputs["device_info"] = {}

        serial = self.inputs.get("system_info", {}).get("sys_ser_no")
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
        
    def write_single_param(self, cmd_handler, flat_key, entry) -> bool:
        """
        Perform write for a single param.
        Args:
            flat_key - e.g., 'brd_hw_cfg_rtc'
            entry - dict with ['section', 'widget', 'select']

        Returns:
            True if write succeeded, False otherwise
        """
        # Step 1: Get module name from section
        section = entry["section"]
        module  = next((k for k, v in PRD_INI_SECTIONS.items() if v == section), None)
        if module is None:
            self.log_handler.log(f"[ERROR] INI {section} didn't have module")
            return False, None

        # Step 2: Get param name from CMD_TABLE
        cmd_def = CMD_TABLE.get(module, {})
        param = next((p for p, d in cmd_def.items() if d.get("flat_key") == flat_key), None)
        if param is None:
            self.log_handler.log(f"[ERROR] {section}->{module} didn't have param")
            return False, None
                
        # Step 3: Check this parameter writable?
        if not CMD_TABLE[module][param].get("writable", True):
            self.log_handler.log(f"[INFO] Skipping read-only param: {flat_key} ({module} -> {param})")
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
            ok, validated_value = validate_param_value(module, param, value)
            if not ok:
                self.log_handler.log(f"[ERROR] Value Error {flat_key}->{module}->{param}: {value}")
                return False, None  # validation function logs internally
                
            self.log_handler.log(f"[TX] {flat_key}->{module}->{param} = {validated_value}")
            result = cmd_handler.set_remote_value(flat_key, module, param, validated_value)
            
            if result != 0x00:
                self.log_handler.log(f"[ERROR] Failed to write {flat_key}", tag="info")
                logging.info(f"{module}->{param}->{value} not written")            
                return False, None
            else:
                self.log_handler.log(f"[INFO] Successfully written {flat_key}", tag="info")
                logging.info(f"{module}->{param}->{value} written successfully")            
                return True, validated_value
            
        except Exception as e:
            self.log_handler.log(f"[EXCEPTION] {flat_key} write failed: {e}")
            return False, None
    
    def read_single_param(self, cmd_handler, flat_key, entry) -> bool:
        """
        Read a single parameter from remote, validate it, and update the GUI widget.
        Args:
            flat_key - e.g., 'brd_hw_cfg_rtc'
            entry - dict with ['section', 'widget', 'select']
        Returns:
            True if read succeeded and value updated, False otherwise
        """
        # Step 1: Get module name from section
        section = entry["section"]
        module = next((k for k, v in PRD_INI_SECTIONS.items() if v == section), None)
        if module is None:
            self.log_handler.log(f"[ERROR] INI section '{section}' has no mapped module", tag="error")
            return False, None

        # Step 2: Get param name from CMD_TABLE
        cmd_def = CMD_TABLE.get(module, {})
        param = next((p for p, d in cmd_def.items() if d.get("flat_key") == flat_key), None)
        if param is None:
            self.log_handler.log(f"[ERROR] {module} has no parameter for flat_key: {flat_key}", tag="error")
            return False, None
                
        # Step 3: Read the parameter value from remote
        try:
            self.log_handler.log(f"[RX] Reading {flat_key} -> {module} -> {param}", tag="info")
            value = cmd_handler.get_remote_value(flat_key, module, param)

            if value is None:
                self.log_handler.log(f"[ERROR] Remote read failed for {flat_key}", tag="error")
                # GUI Cleanup on failure
                widget = entry["widget"]
                if isinstance(widget, ttk.Entry):
                    widget.delete(0, tk.END)
                elif hasattr(widget, "var"):
                    widget.var.set("")  # Clear checkbox / dropdown / string
                return False, None
            
            ok, validated_value = validate_param_value(module, param, value)
            if not ok:
                self.log_handler.log(f"[ERROR] Validation failed for {flat_key} -> {value}", tag="error")
                # GUI Cleanup on failure
                widget = entry["widget"]
                if isinstance(widget, ttk.Entry):
                    widget.delete(0, tk.END)
                elif hasattr(widget, "var"):
                    widget.var.set("")  # Clear checkbox / dropdown / string
                
                return False, None

            # Step 4: Update the received value to widget
            # --- Update GUI widget ---
            widget = entry["widget"]
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
                self.log_handler.log(f"[WARN] Unknown widget type for {flat_key}", tag="warn")

            self.log_handler.log(f"[INFO] Read success: {module} -> {param} = {validated_value}", tag="info")

            return True, validated_value

        except Exception as e:
            self.log_handler.log(f"[ERROR] Exception while reading {flat_key}: {e}", tag="error")
            return False, None
    
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
        self.config_dir  = path_handler.get_config_path()
        self._run()

    # -------------------------------------------------------------------
    def _run(self):
        """Prompt user for New/Edit mode and select config file accordingly."""
        title = f"{self.setup_mode.replace('_', ' ').title()} Setup"

        if self.setup_mode == "master" or self.setup_mode == "device":
            question = f"Do you want a NEW {title} Config?\n\nYes = New\nNo  = Edit existing"

        else: # program mode
            question = f"Do you want Program from?\n\nYes = Defaults\nNo  = Device INI"
            
        self.new_setup = messagebox.askyesno(
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

        SetupDialog(
            self.parent,
            self.log_handler,
            self.path_handler,
            self.setup_mode,
            self.cmd_handler,
            setup_path,
            self.new_setup,
        )

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

        self.select_all_state = tk.BooleanVar(value=True)
 
        # Unified data object -------------------------------------------
        self.im = InputManager(config_dir = self.config_dir,
                                log_handler = self.log_handler, path_handler = self.path_handler,
                                setup_mode = self.setup_mode, state_write = self.new_setup)
        
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
                self.im.load_from_master(self.setup_path)
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
        apply_tooltip(btn_save, "Save", PROGAM_KEY_TOOLTIPS)
        
        btn_cancel = ttk.Button(btn_frame, style=WIDGET_STYLE_BUTTON, text="Cancel", width=12, 
                    command=self.window.destroy, cursor="hand2")
        btn_cancel.pack(side="right", padx=(PAD_SIDE, 0))
        apply_tooltip(btn_cancel, "Cancel", PROGAM_KEY_TOOLTIPS)

    # Write/Read/Verify/Cancel Buttons -----------------------------------------
    def _draw_program_footer_buttons(self, main_frame):
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, pady=(PAD_BOTTOM, 0), sticky="ew")
        
        # Select All button at left
        self.btn_select = ttk.Button(btn_frame, text="Deselect All", width=12,
                        command=self.toggle_select_all, cursor="hand2",
                        style=WIDGET_STYLE_BUTTON, takefocus=False)
        self.btn_select.pack(side="left", padx=(0, PAD_SIDE))
        apply_tooltip(self.btn_select, "select_all", PROGAM_KEY_TOOLTIPS)
        
        for label, command in [
            ("Write",           self.write_to_device),
            ("Read",            self.read_from_device),
            ("Write & Verify",  self.write_and_verify_device),
            ("Save Report",     self.save_device_report)
        ]:
            btn = ttk.Button(btn_frame, text=label, width=12, command=command,
                            cursor="hand2", style=WIDGET_STYLE_BUTTON, takefocus=False)
            btn.pack(side="left", padx=(0, PAD_SIDE))
            apply_tooltip(btn, label, PROGAM_KEY_TOOLTIPS)

        # Cancel button at far right
        btn = ttk.Button(btn_frame, text="Cancel", width=12,
                   command=self.window.destroy, cursor="hand2",
                   style=WIDGET_STYLE_BUTTON, takefocus=False)
        btn.pack(side="right", padx=(PAD_SIDE, 0))
        apply_tooltip(btn, "Cancel", PROGAM_KEY_TOOLTIPS)
 
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

    def write_to_device(self):
        """Write selected parameters to the connected device."""

        if not any(entry["select"].get() for entry in self.im.program_widgets.values()):
            self.log_handler.log("No parameters selected to process.", tag="warn")
            messagebox.showwarning("Warning", "No parameters selected to process.")
            return  # or handle gracefully depending on context
        
        serial_no = int(self.im.program_widgets['sys_ser_no']['widget'].get())
        set_sys_value("sys_ser_no", serial_no)
        
        for flat_key, entry in self.im.program_widgets.items():
            if entry["select"].get():
                success = self.im.write_single_param(self.cmd_handler, flat_key, entry)
                self.im.program_widgets[flat_key]["status"] = "OK" if success else "FAIL"
                
    def read_from_device(self):
        """Read selected parameters from the connected device."""

        if not any(entry["select"].get() for entry in self.im.program_widgets.values()):
            self.log_handler.log("No parameters selected to process.", tag="warn")
            messagebox.showwarning("Warning", "No parameters selected to process.")
            return  # or handle gracefully depending on context
        
        serial_no = int(self.im.program_widgets['sys_ser_no']['widget'].get())
        set_sys_value("sys_ser_no", serial_no)
        
        for flat_key, entry in self.im.program_widgets.items():
            if entry["select"].get():
                success = self.im.read_single_param(self.cmd_handler, flat_key, entry)
                self.im.program_widgets[flat_key]["status"] = "OK" if success else "FAIL"

    def write_and_verify_device(self):
        """Perform write + read-back verification for selected parameters."""
        if not any(entry["select"].get() for entry in self.im.program_widgets.values()):
            self.log_handler.log("No parameters selected to process.", tag="warn")
            messagebox.showwarning("Warning", "No parameters selected to process.")
            return

        serial_no = int(self.im.program_widgets['sys_ser_no']['widget'].get())
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
        filename = f"build_{client}_{order_id}_{serial_no}.txt"
        file_path = os.path.join(self.config_dir, filename)

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
        self.load_master_file(self.master_file)

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
        client   = self.client_info.get("client", "unknown").title()
        order_id = self.client_info.get("order_id", "0000")
        created  = datetime.now().strftime("%d %b %Y %H:%M:%S")
        master   = os.path.basename(self.master_file)
        self.export_file = f"summary_{client.lower()}_{order_id}"

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
            client   = self.client_info.get("client", "unknown").title()
            order_id = self.client_info.get("order_id", "0000")

            # Update GUI and log
            self.hdr_label.config(text=f"Loaded Master: {client} - Order ID: {order_id}")
            rel_path = self.path_handler.get_relative_path(master_file)
            self.log_handler.log(f"Loaded Master config: {rel_path}", tag="info")

            # --- Scan device_*.ini files in config directory ---
            device_files_found = {}

            for fname in os.listdir(self.config_dir):
                if fname.startswith("device_") and fname.endswith(".ini"):
                    # Expecting format: device_<client>_<order_id>_<serial>.ini
                    parts = fname.split("_")
                    if len(parts) >= 3:
                        serial = parts[3].split(".")[0]
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

            for sn, entry in sorted(self.device_info.items(), key=lambda x: int(x[0])):
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
                for sn, created in sorted(device_files_found.items(), key=lambda x: int(x[0])):
                    if sn not in existing_serials:
                        self.tree.insert("", "end", values=(sn, "extra", created, "Yes"))
                        self.displayed_serials.add((sn, "extra", created, "Yes"))

        except Exception as e:
            self.log_handler.log(f"Failed to load master file: {e}", tag="error")
            messagebox.showerror("Error", f"Could not load Master file:\n{e}")

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

        try:
            with open(full_path, "w", encoding="utf-8") as f:
                # --- Metadata Header ---
                for line in self.metadata_hdr:
                    f.write(line + "\n")
                f.write("\n")

                f.write("{:<15}{:<20}{:<20}{}\n".format("Serial No.", "Device Status", "Created On", "File"))
                f.write("=" * 70 + "\n")
                for sn, status, created, file in sorted(self.displayed_serials, key=lambda x: int(x[0])):
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

        try:
            with open(full_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # --- Metadata Header ---
                for line in self.metadata_hdr:
                    writer.writerow([line])
                writer.writerow([])

                # --- Table Header and Data Rows ---
                writer.writerow(["Serial No.", "Device Status", "Created On", "File"])
                for sn, status, created, file in sorted(self.displayed_serials, key=lambda x: int(x[0])):
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

        try:
            with PdfPages(full_path) as pdf:
                fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4 portrait in inches
                ax.axis("off")

                # --- Prepare Content ---
                lines = self.metadata_hdr
                lines.append("")
                lines.append("{:<15}{:<20}{:<20}{}".format("Serial No.", "Device Status", "Created On", "File"))
                lines.append("=" * 70)
                for sn, status, created, file in sorted(self.displayed_serials, key=lambda x: int(x[0])):
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
