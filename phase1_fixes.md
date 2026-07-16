# Phase 1 — VibMTool to completion, 2026-07-16

All BEFORE blocks are verbatim from the current (post-Phase-0) knowledge-box
copies. Apply per cluster; each cluster is one coherent commit candidate.

Three decisions embedded here — veto before applying if you disagree:
  (a) [T3] System dropdown rebinds to Ctrl+Y (underline the 'y' in "System");
      Ctrl+S stays with Summary, which is already live and bound.
  (b) [T7] the dead "status" stores are DELETED (per-param outcomes already
      go to the log; the report consumes verification_results only).
  (c) prd_gui_meta: tooltip key "verify" is renamed to "write & verify" and a
      new "save report" entry is added; "save" stays (Save button uses it).

================================================================================
CLUSTER A — prd_gui_setup.py  ([T1] [T2] [T4] [T7] [T6-consumers] + minors)
================================================================================

## A1  [T1]  build_device_list() — merge-regenerate, never discard build history

**BEFORE**
```python
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
```

**AFTER**
```python
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
```

Note: `_on_save()` stays unchanged — with merge semantics, calling
build_device_list() on BOTH new and edit is now correct (qty/base edits take
effect, marks survive). Also quietly fixes the old-master-without-device_info
KeyError edge (`.get(..., {})` + section reassignment).

Verify: (1) create master (qty 5), build devices for 2 serials, edit master
(change a board rev), save — the 2 stay "used, <date>". (2) Edit again with
total_qty 5→3 such that a used serial falls out of range — it must remain in
the file. (3) Summary shows no YES[Error] for built units.

## A2  [T2]  guarded serial helper + three call sites

**Add method to SetupDialog** (place directly after `toggle_select_all`, before
`write_to_device`):
```python
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
```

**Replace ALL THREE occurrences** (write_to_device, read_from_device,
write_and_verify_device — identical text each time):

BEFORE (x3)
```python
        serial_no = int(self.im.program_widgets['sys_ser_no']['widget'].get())
        set_sys_value("sys_ser_no", serial_no)
```
AFTER (x3)
```python
        ok, serial_no = self._get_serial_from_widget()
        if not ok:
            return
        set_sys_value("sys_ser_no", serial_no)
```

(The unconditional set_sys_value autosave stays — that's the separate,
already-documented still-open cosmetic item; scope not expanded here.)

Verify: blank the Serial No field, click Write — expect an error box + red log
line, no console traceback. Enter 99999 — same. Enter valid — proceeds.

## A3  [T4]  load_from_master() signals failure; SetupDialog aborts

Four targeted edits in load_from_master():

1. Signature:
BEFORE  `    def load_from_master(self, full_path: str) -> None:`
AFTER   `    def load_from_master(self, full_path: str) -> bool:`

2. Cancel path:
BEFORE
```python
        if not self.serial_no:
            self.log_handler.log("No serial number entered. Operation cancelled.", tag="warn")
            return
```
AFTER
```python
        if not self.serial_no:
            self.log_handler.log("No serial number entered. Operation cancelled.", tag="warn")
            return False
```

3. Invalid path:
BEFORE
```python
        except ValueError:
            messagebox.showerror("Invalid Input", f"Serial number must be an integer in range {SERIAL_RANGE}")
            return
```
AFTER
```python
        except ValueError:
            messagebox.showerror("Invalid Input", f"Serial number must be an integer in range {SERIAL_RANGE}")
            return False
```

4. Success/exception tail:
BEFORE
```python
            self.inputs["client_info"]['created_on'] = datetime.now().strftime("%d %b %Y")
            self.inputs['client_info']['source'] = self.path_handler.get_file_name_only(full_path)

        except Exception as e:
            self.log_handler.log(f"Error loading Master config: {e}", tag="error")
            messagebox.showerror("Error", f"Failed to load Master config: {e}")
            return
```
AFTER
```python
            self.inputs["client_info"]['created_on'] = datetime.now().strftime("%d %b %Y")
            self.inputs['client_info']['source'] = self.path_handler.get_file_name_only(full_path)
            return True

        except Exception as e:
            self.log_handler.log(f"Error loading Master config: {e}", tag="error")
            messagebox.showerror("Error", f"Failed to load Master config: {e}")
            return False
```

And the SetupDialog device+new branch:

BEFORE
```python
            if self.new_setup: # from Master, default also needed to populated missing keys
                self.im.load_from_defaults()
                self.im.load_from_master(self.setup_path)
                self.log_handler.log(f"Loaded {prefix} Config from: {rel_path}", tag='info')
```
AFTER
```python
            if self.new_setup: # from Master, default also needed to populated missing keys
                self.im.load_from_defaults()
                if not self.im.load_from_master(self.setup_path):
                    # Serial prompt cancelled/invalid or master unreadable —
                    # abort instead of opening the dialog on pure defaults and
                    # logging a misleading "Loaded" message ([T4]).
                    self.log_handler.log(f"{prefix} setup aborted — master not applied.", tag="warn")
                    return
                self.log_handler.log(f"Loaded {prefix} Config from: {rel_path}", tag='info')
```

(The early return happens BEFORE `tk.Toplevel` is created, so no window
appears; SetupManager's constructor simply finishes.)

Verify: Device Setup -> New -> pick master -> Cancel at the serial prompt.
Expect the "aborted" warn log and NO dialog window. Same for serial "abc".

## A4  [T7]  delete the two dead "status" stores

BEFORE (in write_to_device)
```python
                success, _ = self.im.write_single_param(self.cmd_handler, flat_key, entry)
                self.im.program_widgets[flat_key]["status"] = "OK" if success else "FAIL"
```
AFTER
```python
                success, _ = self.im.write_single_param(self.cmd_handler, flat_key, entry)
                # per-param outcome already logged by write_single_param;
                # the old ["status"] store here was write-only ([T7])
```

BEFORE (in read_from_device)
```python
                success, _ = self.im.read_single_param(self.cmd_handler, flat_key, entry)
                self.im.program_widgets[flat_key]["status"] = "OK" if success else "FAIL"
```
AFTER
```python
                success, _ = self.im.read_single_param(self.cmd_handler, flat_key, entry)
                # per-param outcome already logged by read_single_param;
                # the old ["status"] store here was write-only ([T7])
```

## A5  [T6-consumers]  str() guards on literal_eval'd free text

BEFORE (save_to_ini)
```python
        client = self.inputs["client_info"].get('client', 'unknown')
        order  = self.inputs["client_info"].get('order_id', '0000')
```
AFTER
```python
        # str(): ConfigIO literal_eval turns purely-numeric client/order into
        # int (and "True" into bool); .lower()/.title() then crash ([T6]).
        client = str(self.inputs["client_info"].get('client', 'unknown'))
        order  = str(self.inputs["client_info"].get('order_id', '0000'))
```

BEFORE (generate_metadata_header)
```python
        client   = self.client_info.get("client", "unknown").title()
        order_id = self.client_info.get("order_id", "0000")
```
AFTER
```python
        # str() guards — see [T6]; this runs OUTSIDE export_text's try, so an
        # AttributeError here was previously uncaught.
        client   = str(self.client_info.get("client", "unknown")).title()
        order_id = str(self.client_info.get("order_id", "0000"))
```

Verify: create a master with client "1234", save, reopen, save again — no
error box. Run Summary on it and export — header shows "1234", no traceback.

## A6  (minor) mark_serial_used_in_master() — normalize the serial key

BEFORE
```python
        serial = self.inputs.get("system_info", {}).get("sys_ser_no")
        if not serial:
```
AFTER
```python
        raw = self.inputs.get("system_info", {}).get("sys_ser_no")
        serial = "" if raw is None else str(raw).strip()
        if serial.isdigit():
            serial = str(int(serial))   # normalize " 105"/"0105" -> "105"
        if not serial:
```

(Keeps the register keyed consistently with build_device_list's str(sn) keys;
a padded/spaced entry no longer creates a stray duplicate row.)

## A7  (minor) numeric-safe sorting in SummaryDialog

**Add module-level helper** (directly after the DEVICE_FILENAME_RE definition):
```python
def _serial_sort_key(sn):
    """Numeric serials sort numerically; non-numeric keys sort after them,
    alphabetically — one bad hand-edited key no longer aborts the whole
    summary load/export."""
    s = str(sn).strip()
    return (0, int(s), "") if s.isdigit() else (1, 0, s)
```

BEFORE (one occurrence, load_master_file)
```python
            for sn, entry in sorted(self.device_info.items(), key=lambda x: int(x[0])):
```
AFTER
```python
            for sn, entry in sorted(self.device_info.items(), key=lambda x: _serial_sort_key(x[0])):
```

BEFORE (THREE identical occurrences: export_text, export_csv, export_pdf —
replace all three)
```python
                for sn, status, created, file in sorted(self.displayed_serials, key=lambda x: int(x[0])):
```
AFTER
```python
                for sn, status, created, file in sorted(self.displayed_serials, key=lambda x: _serial_sort_key(x[0])):
```

Also in load_master_file (ENABLE_EXTRA_DEVICE branch), if present:
`sorted(device_files_found.items(), key=lambda x: int(x[0]))` ->
`key=lambda x: _serial_sort_key(x[0])` (same rationale; flag is off today).

## A8  (minor) overwrite prompts for exports + build report

**Add module-level helper** (next to _serial_sort_key):
```python
def _confirm_overwrite(path) -> bool:
    """Ask before overwriting an existing export/report file — save_to_ini()
    already asks; the fixed-name exports silently clobbered."""
    if os.path.exists(path):
        return messagebox.askyesno(
            "Overwrite File?",
            f"A file already exists:\n{os.path.basename(path)}\n\nDo you want to overwrite it?")
    return True
```

Then insert the guard after each full-path construction (4 sites):

export_text — BEFORE
```python
        file_name = f"{self.export_file}.txt"
        full_path = os.path.join(self.config_dir, file_name)
```
AFTER
```python
        file_name = f"{self.export_file}.txt"
        full_path = os.path.join(self.config_dir, file_name)
        if not _confirm_overwrite(full_path):
            return
```

export_csv: same pattern with `f"{self.export_file}.csv"`.
export_pdf: same pattern with `f"{self.export_file}.pdf"`.

save_device_report — BEFORE
```python
        filename = f"build_{_sanitize_filename_part(client)}_{_sanitize_filename_part(order_id)}_{serial_no}.txt"
        file_path = os.path.join(self.config_dir, filename)
```
AFTER
```python
        filename = f"build_{_sanitize_filename_part(client)}_{_sanitize_filename_part(order_id)}_{serial_no}.txt"
        file_path = os.path.join(self.config_dir, filename)
        if not _confirm_overwrite(file_path):
            return
```

================================================================================
CLUSTER B — [T3] + GUI minors  (prd_gui_main.py, gui_utils.py, prd_gui_meta.py,
status_bar.py)
================================================================================

## B1  [T3]  store the dropdowns, rebind System to Ctrl+Y

prd_gui_main.py — four edits in create_dropdown_buttons(). Each BEFORE block
includes the IS_ENABLED line so the (otherwise identical) call lines are
unambiguous:

1) BEFORE
```python
        if IS_ENABLED("ENABLE_SETUP_DROPDOWN"):
            create_dropdown_button(
```
AFTER
```python
        if IS_ENABLED("ENABLE_SETUP_DROPDOWN"):
            # NOTE: key 'd' collides with the "Device Setup" button shortcut —
            # rekey this dropdown before ever enabling the flag ([T3] note).
            self.dropdowns['d'] = create_dropdown_button(
```

2) BEFORE
```python
        if IS_ENABLED("ENABLE_BRD_DROPDOWN"):
            create_dropdown_button(
```
AFTER
```python
        if IS_ENABLED("ENABLE_BRD_DROPDOWN"):
            self.dropdowns['b'] = create_dropdown_button(
```

3) BEFORE
```python
        if IS_ENABLED("ENABLE_ADC_DROPDOWN"):
            create_dropdown_button(
```
AFTER
```python
        if IS_ENABLED("ENABLE_ADC_DROPDOWN"):
            self.dropdowns['a'] = create_dropdown_button(
```

4) System block — key change 's' -> 'y' (Ctrl+S stays with Summary), underline
the 'y':
BEFORE
```python
        if IS_ENABLED("ENABLE_SYS_DROPDOWN"):
            create_dropdown_button(
                parent=self.toolbar,
                label="System",
                underline_idx=0,
                key='s', # Ctrl+S		
                item_list=[
                ("System Set", 7, self.sys_set_button, 's'),
                ("System Get", 7, self.sys_get_button, 'g'),
            ],
            tooltip_msg="Ctrl+S - Select System"
            )
```
AFTER
```python
        if IS_ENABLED("ENABLE_SYS_DROPDOWN"):
            # Ctrl+S belongs to the Summary button; 'y' (SYstem) is free ([T3])
            self.dropdowns['y'] = create_dropdown_button(
                parent=self.toolbar,
                label="System",
                underline_idx=1,
                key='y', # Ctrl+Y
                item_list=[
                ("System Set", 7, self.sys_set_button, 's'),
                ("System Get", 7, self.sys_get_button, 'g'),
            ],
            tooltip_msg="Ctrl+Y - Select System"
            )
```
(NOTE: the BEFORE block above contains trailing whitespace after `# Ctrl+S`
in the original — if the exact match fails, match without trailing spaces.)

bind_all() needs no change — its existing dropdown loop now finally runs over
the populated dict and binds Ctrl+B / Ctrl+A / Ctrl+Y to popup_menu.

5) set_button_state / get_button_state — handle the (menu_button, menu) tuple:

BEFORE
```python
        btn = self.buttons.get(key.lower()) or self.dropdowns.get(key.lower())
        if btn:
            if enabled:
                btn.config(state='normal', fg='black')
            else:
                btn.config(state='disabled', fg='gray')
```
AFTER
```python
        btn = self.buttons.get(key.lower()) or self.dropdowns.get(key.lower())
        if isinstance(btn, tuple):      # dropdowns store (menu_button, menu)
            btn = btn[0]
        if btn:
            if enabled:
                btn.config(state='normal', fg='black')
            else:
                btn.config(state='disabled', fg='gray')
```

BEFORE
```python
        btn = self.buttons.get(key.lower()) or self.dropdowns.get(key.lower())
        return btn['state'] == 'normal' if btn else None
```
AFTER
```python
        btn = self.buttons.get(key.lower()) or self.dropdowns.get(key.lower())
        if isinstance(btn, tuple):      # dropdowns store (menu_button, menu)
            btn = btn[0]
        return btn['state'] == 'normal' if btn else None
```

Verify: Ctrl+B / Ctrl+A / Ctrl+Y each pop their menu under the button; Ctrl+S
opens Summary; hover tooltips read Ctrl+B / Ctrl+A / Ctrl+Y correctly;
reset_all_buttons(False) greys the dropdowns too (Quit stays enabled).

## B2  (shared, minor) gui_utils.py — separator between items only

Cross-project check: create_dropdown_button has no VibMScope call sites
(VibMScope's create_dropdown_buttons is commented out entirely) — VibMTool is
the sole live consumer.

BEFORE
```python
    for i, (item_label, underline, callback, shortcut) in enumerate(item_list):
        # if i == 1:
        menu.add_separator()
        menu.add_command(label=item_label, underline=underline, command=wrap_with_beep(callback))
```
AFTER
```python
    for i, (item_label, underline, callback, shortcut) in enumerate(item_list):
        if i > 0:   # separator BETWEEN items only (was a leading separator on every item)
            menu.add_separator()
        menu.add_command(label=item_label, underline=underline, command=wrap_with_beep(callback))
        # 'shortcut' field is reserved/unused for now (menu accelerators not wired)
```

## B3  (minor) prd_gui_meta.py — tooltip keys match button labels

BEFORE
```python
PROGRAM_KEY_TOOLTIPS = {
    "write":  "Send selected settings to the connected device",
    "read":   "Read selected parameters from the device",
    "verify": "Compare INI values and device values for validation",
    "save":   "Save current settings to a new INI file",
    "select_all": "Select and deselect all Params",
    "cancel": "Cancel the Operation and exit",
}
```
AFTER
```python
# keys must equal lower-cased button labels (apply_tooltip lowercases the
# label to look up here) — "verify"/"save report" previously never matched.
PROGRAM_KEY_TOOLTIPS = {
    "write":          "Send selected settings to the connected device",
    "read":           "Read selected parameters from the device",
    "write & verify": "Compare INI values and device values for validation",
    "save":           "Save current settings to a new INI file",
    "save report":    "Save the Build Verification Report to a text file",
    "select_all":     "Select and deselect all Params",
    "cancel":         "Cancel the Operation and exit",
}
```

## B4  (shared, minor) status_bar.py — make style_dict real, zero visual change

Cross-project check (per repo convention): VibMScope constructs
StatusBarHandler(self) with NO style argument (maps_class.py:53) — with the
fallback below it keeps STATUS_LABEL_STYLE exactly as today. VibMTool passes
style_dict=STATUS_LABEL_STYLE — also identical. The change only makes the
parameter functional and deletes the dead default_style dict.

BEFORE
```python
        self.status_var = tk.StringVar()
        self._parts = {}

        default_style = {
            'font': ("Arial", 11),
            'fg': "black",
            'bg': "lightgrey",
            'anchor': "w",
            'bd': 1,
            'padx': 4,
            'pady': 6,
            'height': 1,
            'relief': "groove",
            'highlightthickness': 1,
        }
        style = style_dict or default_style

        self.status_bar = tk.Label(
            parent_frame, text="", textvariable=self.status_var, **STATUS_LABEL_STYLE
        )
```
AFTER
```python
        self.status_var = tk.StringVar()
        self._parts = {}

        # style_dict is now actually applied; default preserves the previous
        # hard-coded appearance for callers that pass nothing (VibMScope).
        style = style_dict or STATUS_LABEL_STYLE

        self.status_bar = tk.Label(
            parent_frame, text="", textvariable=self.status_var, **style
        )
```

Verify: launch BOTH tools — status bars look identical to before.

Deferred (stays a documented minor, not fixed here): toolbar setup buttons
updating the status bar even on error/cancel — needs SetupManager to report
an outcome; small plumbing, do alongside any future SetupManager work.

================================================================================
CLUSTER C — config_io.py latent traps  (shared; VibMTool sole consumer)
================================================================================

## C1  load_file: fresh parser per call + remove dead warn branch

BEFORE
```python
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Config file not found: {filepath}")

        self.parser.read(filepath)
        data_dict = {}

        for section in self.parser.sections():
            data_dict[section] = {}
            for key, value in self.parser.items(section):
                try:
                    parsed_val = ast.literal_eval(value)
                    data_dict[section][key] = parsed_val
                except Exception as e:
                    if not isinstance(value, str):
                        self.log_handler.log(
                            f"[{section}] {key} = '{value}' could not be parsed: {e} — using raw string.",
                            tag='warn'
                        )
                    data_dict[section][key] = value  # Fallback to raw string
```
AFTER
```python
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Config file not found: {filepath}")

        # Fresh parser per load: configparser.read() MERGES into existing
        # state, so the old shared self.parser accumulated sections across
        # calls if one ConfigIO instance was ever reused.
        parser = configparser.ConfigParser()
        parser.read(filepath)
        data_dict = {}

        for section in parser.sections():
            data_dict[section] = {}
            for key, value in parser.items(section):
                try:
                    # NOTE [T6]: literal_eval coerces numeric-looking free
                    # text ("1234" -> int, "True" -> bool); consumers of
                    # free-text fields must str() before str-methods.
                    parsed_val = ast.literal_eval(value)
                    data_dict[section][key] = parsed_val
                except Exception:
                    # normal path for plain text values (configparser values
                    # are always str — the old isinstance warn was dead code)
                    data_dict[section][key] = value  # Fallback to raw string
```

Also remove the now-unused instance parser:
BEFORE
```python
        self.path_handler = path_handler
        self.log_handler  = log_handler
        self.parser = configparser.ConfigParser()
```
AFTER
```python
        self.path_handler = path_handler
        self.log_handler  = log_handler
```

## C2  save_file: guard makedirs against bare filenames

BEFORE
```python
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as configfile:
            parser.write(configfile)
```
AFTER
```python
        dir_name = os.path.dirname(filepath)
        if dir_name:   # bare filename -> current dir; makedirs('') would raise
            os.makedirs(dir_name, exist_ok=True)
        with open(filepath, 'w') as configfile:
            parser.write(configfile)
```

Cross-project check: ConfigIO has no VibMScope call sites (confirmed in both
project docs); root CLAUDE.md gets the shared-fix note anyway per convention.

Verify: full round-trip — load master, save device, mark-back, Summary,
exports — all behave as before; no functional change expected from C1/C2.

================================================================================
CLUSTER D — documentation
================================================================================

1. VibMTool/CLAUDE.md flips: [T1] [T2] [T4] [T7] -> FIXED (2026-07-16) with
   one-line "what changed" each (use the section titles above); minor-block
   items A6/A7/A8/B1..B4/C1/C2 -> mark fixed inside the grouped minor bullet;
   the deferred status-bar-on-error item stays open with a "deferred, needs
   SetupManager outcome reporting" note.
2. [T9] doc drift, same file: (a) "Uses from vibmshared" — replace the
   Simulator bullet with: "modules.simulator (SimulationPort — constructed
   when simulation_mode is on; sets 'connection'='simulation_port' session
   flag)"; (b) delete the still-open item about the stale commented import at
   vibmtool.py:46 (comment no longer exists). Then mark [T9] itself FIXED.
3. Root CLAUDE.md: shared-fix notes for B2 (gui_utils dropdown separator),
   B4 (StatusBarHandler style_dict now applied — call-site check: VibMScope
   passes no style, appearance unchanged), C1/C2 (ConfigIO fresh parser,
   makedirs guard) — each with the cross-project check line, matching the
   write_module_direct precedent.
4. [T6] in VibMTool/CLAUDE.md: mark the consumer half FIXED (A5) and note the
   root cause (literal_eval coercion) is documented-by-design in config_io
   with the inline NOTE — no further change planned unless a new consumer
   appears.

================================================================================
Claude Code prompt (suggested)
================================================================================
```
Read phase1_fixes.md in the repo root. Apply clusters A, B, C, D in order.
Every BEFORE block must match the target file verbatim (one BEFORE in A2 and
one in A4 occur multiple times — the pack says which are replace-all); if a
block does not match, STOP and report the mismatch instead of improvising.
Make no other changes: no reformatting, no refactoring, no extra fixes.
Do not run git commands. When done, list every file touched with a one-line
summary per change, and flag any BEFORE block you could not match.
```

Reminder: vibmtool.py went missing from the knowledge box in the last sync
(and cmd_remote.py appeared) — re-add it when you re-sync after this phase.

Next: Phase 2 (VibMScope) — [F2] first, using the DECIDED save-partial rule.
