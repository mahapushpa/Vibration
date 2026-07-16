# Phase 3 — deferred-minors closeout (both projects), 2026-07-16

Goal: every remaining minor either gets FIXED here or gets an explicit
CLOSED-ACCEPTED doc entry with rationale — so nothing keeps resurfacing in
future reviews. All BEFORE blocks verbatim from current knowledge-box copies.

Decisions embedded — veto before applying:
  (a) SetupManager's mode prompt switches askyesno -> askyesnocancel. This is
      a small BEHAVIOR ADDITION: users gain a real Cancel (and window-X now
      cancels instead of meaning "No/Edit"). It also makes the previously-dead
      None branch live — evidently the original intent.
  (b) Data Setup dropdown rekeys 'd' -> 'u' (Ctrl+U, "Data Set_u_p") now,
      removing the collision note; flag stays disabled.
  (c) vib_features.py (VibMScope) gets the same header + boolean cleanup as
      prd_features.py — same stale "# feature_flags.py" header, same GLB
      pattern, zero external importers of the GLB_ constants (verified).
  (d) ydata_to_unit(): factor recomputed per call + np.clip saturation
      (DECIDED: unit changes permitted in session-OFF only; wrap -> saturate).
  (e) CLOSED-ACCEPTED (doc-only, no code): InputManager/self.im naming,
      MainApp name ambiguity, and the synchronous-command GUI freeze — see
      Cluster D for the exact rationale wording.

================================================================================
CLUSTER A — VibMScope  (maps_class.py, maps_signal.py, vib_features.py)
================================================================================

## A1  X-tick labels: prefer the data's time base (RTC-aware)

**BEFORE**
```python
    def insert_xtick_time_string(self):
        time_str = datetime.now().strftime('%H:%M:%S')
        self.time_xtick_label.extend([time_str])
        self.aTime.set_xticklabels(self.time_xtick_label)
```
**AFTER**
```python
    def insert_xtick_time_string(self):
        # Use the data's own time base: hdr_handler.system_time is sourced
        # from the remote GSN RTC when available (else the laptop clock,
        # upstream in HeaderProcessor) — tick labels now match the recorded
        # timestamps. datetime.now() only before any header has been parsed
        # (system_time still 0). (DECIDED 2026-07-16.)
        system_time = int(getattr(self.hdr_handler, 'system_time', 0) or 0)
        if system_time > 0:
            _, _, time_str = self.hdr_handler.get_time_string(system_time)
        else:
            time_str = datetime.now().strftime('%H:%M:%S')
        self.time_xtick_label.extend([time_str])
        self.aTime.set_xticklabels(self.time_xtick_label)
```
(AppMainFrame holds self.hdr_handler directly (:48); the caller (:130) runs
once per completed second, so system_time is fresh when it matters.)

Verify: with the GSN RTC set differently from the laptop clock, tick labels
follow the RTC and match the record-file Start Time; in sim/pre-data state,
labels show wall-clock time as before.

## A2  ydata_to_unit(): live factor + saturation

Edit 1 — remove the init-time cache (maps_signal.py:57):
**BEFORE**
```python
        self.sensor_factor = get_sensor_unit_factor(get_sys_value('time_yspan'))
```
**AFTER**  (delete the line)

Edit 2 — the method:
**BEFORE**
```python
    def ydata_to_unit(self, ydata):
        """ convert the y axis data based on unit selected."""
        # (dead local 'unit' removed 2026-07-16; sensor_factor is cached at
        # __init__ and np.int16 can wrap for factors > 1 — both still
        # documented as open minors, behavior unchanged here)
        return (np.int16(ydata * self.sensor_factor))
```
**AFTER**
```python
    def ydata_to_unit(self, ydata):
        """ convert the y axis data based on unit selected."""
        # Factor recomputed per call (cheap lookup) so a unit changed while
        # the session is OFF takes effect on the next session — the old
        # __init__-cached factor went stale (DECIDED 2026-07-16: unit changes
        # are permitted in session-off only). np.clip saturates instead of
        # letting np.int16 silently wrap for factors > 1.
        factor = get_sensor_unit_factor(get_sys_value('time_yspan'))
        return np.int16(np.clip(ydata * factor, -32768, 32767))
```

Verify: run a session in MV; stop session; change time_yspan; start session —
scale reflects the new unit without restarting the app. Behavior with an
unchanged unit is identical (same factor, clip is a no-op in normal range).

## A3  Remove the caller-less close_open_files()

**BEFORE**
```python
    #---------------------------------------------------------------------------
    def close_open_files(self):
        """No file handles to close; all file writes are done via 'with open()'."""
        if self.record_filename:
            rel_path = self.path_handler.get_relative_path(self.record_filename)
            print(f"[Recording] Closed file: {rel_path}")
            logging.info(f"[Recording] Closed file: {rel_path}")
            #self.record_filename = None
```
**AFTER**  (delete the whole block — the separator line before the next method
remains, keeping the file's visual structure)

Verify: grep close_open_files across the repo returns nothing; app runs.

## A4  vib_features.py: header + booleans (whole-file replace)

Same transformation as prd_features.py (Cluster B5) — stale "# feature_flags.py"
header and the GLB 1/0 indirection. No file imports GLB_VALID/GLB_INVALID from
either module (verified repo-wide). Full replacement content:
```python
# vib_features.py

FEATURE_FLAGS = {
    "ENABLE_EXTRA_DEVICE"   : False,
    "ENABLE_SETUP_DROPDOWN" : False,

    "ENABLE_BRD_DROPDOWN"   : False,
    "ENABLE_ADC_DROPDOWN"   : False,
    "ENABLE_SYS_DROPDOWN"   : False,

    "ENABLE_BUILD_TOP_BUTTON" : False,

    # Add more as needed
}

# Sanity check
for key, value in FEATURE_FLAGS.items():
    assert isinstance(value, bool), f"Invalid value for {key}: {value}"

# Wrapper function for clean access
def IS_ENABLED(flag_name: str) -> bool:
    """Check if a feature flag is enabled."""
    try:
        return FEATURE_FLAGS[flag_name]
    except KeyError:
        raise KeyError(f"Unknown feature flag: {flag_name}")
```
(All VibMScope flags are currently disabled — values preserved exactly.)

================================================================================
CLUSTER B — VibMTool  (prd_gui_setup.py, prd_gui_main.py, prd_features.py,
vibmtool.py)
================================================================================

## B1  Status bar reflects the real outcome (closes VibMTool minor #1)

Edit 1 — SetupManager.__init__:
**BEFORE**
```python
        self.new_setup = None
        self.config_dir  = path_handler.get_config_path()
        self._run()
```
**AFTER**
```python
        self.new_setup = None
        self.completed = False   # True once the SetupDialog actually opened
        self.config_dir  = path_handler.get_config_path()
        self._run()
```

Edit 2 — SetupManager._run() tail:
**BEFORE**
```python
        SetupDialog(
            self.parent,
            self.log_handler,
            self.path_handler,
            self.setup_mode,
            self.cmd_handler,
            setup_path,
            self.new_setup,
        )
```
**AFTER**
```python
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
```

Edit 3 — SetupDialog.__init__, flag init:
**BEFORE**
```python
        self.config_dir   = path_handler.get_config_path()

        self.select_all_state = tk.BooleanVar(value=True)
```
**AFTER**
```python
        self.config_dir   = path_handler.get_config_path()
        self.opened       = False   # set True once the Toplevel is created

        self.select_all_state = tk.BooleanVar(value=True)
```

Edit 4 — SetupDialog window creation:
**BEFORE**
```python
        # TK window ------------------------------------------------------
        self.window = tk.Toplevel(self.parent)
```
**AFTER**
```python
        # TK window ------------------------------------------------------
        self.window = tk.Toplevel(self.parent)
        self.opened = True
```

Edit 5 — SummaryDialog.__init__ (extends the P0-3 block):
**BEFORE**
```python
        self.export_file = None
        self.displayed_serials = set()   # exists even if load_master_file() fails
        self.start()
```
**AFTER**
```python
        self.export_file = None
        self.displayed_serials = set()   # exists even if load_master_file() fails
        self.completed = False           # True once the master loaded cleanly
        self.start()
```

Edit 6 — SummaryDialog.start():
**BEFORE**
```python
        self._init_ui()
        self.load_master_file(self.master_file)
```
**AFTER**
```python
        self._init_ui()
        self.completed = self.load_master_file(self.master_file)
```

Edit 7 — load_master_file() returns its outcome (tail):
**BEFORE**
```python
                        self.tree.insert("", "end", values=(sn, "extra", created, "Yes"))
                        self.displayed_serials.add((sn, "extra", created, "Yes"))

        except Exception as e:
            self.log_handler.log(f"Failed to load master file: {e}", tag="error")
            messagebox.showerror("Error", f"Could not load Master file:\n{e}")
```
**AFTER**
```python
                        self.tree.insert("", "end", values=(sn, "extra", created, "Yes"))
                        self.displayed_serials.add((sn, "extra", created, "Yes"))

            return True

        except Exception as e:
            self.log_handler.log(f"Failed to load master file: {e}", tag="error")
            messagebox.showerror("Error", f"Could not load Master file:\n{e}")
            return False
```

Edit 8 — the four toolbar buttons (prd_gui_main.py):
**BEFORE**
```python
    def master_setup_button(self):
        try:
            SetupManager(self.root_window, self.log_handler, 
                                self.path_handler, setup_mode = "master")
            
        except Exception as e:
            self.log_handler.log(f"Master Setup Error: {e}", tag = "error")

        reset_status_bar()
        update_status_bar("MASTER", "Data")
```
**AFTER**
```python
    def master_setup_button(self):
        try:
            mgr = SetupManager(self.root_window, self.log_handler, 
                                self.path_handler, setup_mode = "master")
        except Exception as e:
            self.log_handler.log(f"Master Setup Error: {e}", tag = "error")
            return

        if getattr(mgr, 'completed', False):   # not on error/cancel/abort
            reset_status_bar()
            update_status_bar("MASTER", "Data")
```
**BEFORE**
```python
    def device_setup_button(self):
        try:
            SetupManager(self.root_window, self.log_handler, 
                                self.path_handler, setup_mode = "device")

        except Exception as e:
            self.log_handler.log(f"Device Setup Error: {e}", tag = "error")

        reset_status_bar()
        update_status_bar("DEVICE", "Data")
```
**AFTER**
```python
    def device_setup_button(self):
        try:
            mgr = SetupManager(self.root_window, self.log_handler, 
                                self.path_handler, setup_mode = "device")
        except Exception as e:
            self.log_handler.log(f"Device Setup Error: {e}", tag = "error")
            return

        if getattr(mgr, 'completed', False):   # not on error/cancel/abort
            reset_status_bar()
            update_status_bar("DEVICE", "Data")
```
**BEFORE**
```python
    def device_program_button(self):
        try:
            SetupManager(self.root_window, self.log_handler, 
                                self.path_handler, setup_mode = "program",
                                cmd_handler = self.cmd_handler)
        except Exception as e:
            self.log_handler.log(f"Device Build Error: {e}", tag = "error")

        reset_status_bar()
        update_status_bar("BUILD", "Device")
```
**AFTER**
```python
    def device_program_button(self):
        try:
            mgr = SetupManager(self.root_window, self.log_handler, 
                                self.path_handler, setup_mode = "program",
                                cmd_handler = self.cmd_handler)
        except Exception as e:
            self.log_handler.log(f"Device Build Error: {e}", tag = "error")
            return

        if getattr(mgr, 'completed', False):   # not on error/cancel/abort
            reset_status_bar()
            update_status_bar("BUILD", "Device")
```
**BEFORE**
```python
    def summary_button(self):
        try:
            SummaryDialog(self.root_window, self.log_handler, self.path_handler)
        except Exception as e:
            self.log_handler.log(f"Summary Error: {e}", tag = "error")
            
        reset_status_bar()
        update_status_bar("SUMMARY", "Prepared")
```
**AFTER**
```python
    def summary_button(self):
        try:
            dlg = SummaryDialog(self.root_window, self.log_handler, self.path_handler)
        except Exception as e:
            self.log_handler.log(f"Summary Error: {e}", tag = "error")
            return

        if getattr(dlg, 'completed', False):   # only when the master loaded
            reset_status_bar()
            update_status_bar("SUMMARY", "Prepared")
```

Verify: cancel each flow at its first prompt (mode prompt, file dialog, serial
prompt, corrupt master) — status bar stays unchanged; complete each flow —
status text appears as before.

## B2  Real Cancel on the mode prompt (closes the dead-branch item)

**BEFORE**
```python
        self.new_setup = messagebox.askyesno(
            title,
            question,
        )

        if self.new_setup is None:
            self.log_handler.log(f"{title} cancelled.", tag="warn")
            return
```
**AFTER**
```python
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
```
Also update the two question strings to advertise it:
**BEFORE**
```python
            question = f"Do you want a NEW {title} Config?\n\nYes = New\nNo  = Edit existing"
```
**AFTER**
```python
            question = f"Do you want a NEW {title} Config?\n\nYes = New\nNo  = Edit existing\nCancel = Abort"
```
**BEFORE**
```python
            question = f"Do you want Program from?\n\nYes = Defaults\nNo  = Device INI"
```
**AFTER**
```python
            question = f"Do you want Program from?\n\nYes = Defaults\nNo  = Device INI\nCancel = Abort"
```
(Note the behavior change in (a): window-X on this prompt previously meant
"No/Edit"; it now cancels — arguably what a user closing the box expects.)

## B3  Serial autosave -> write-on-change (closes the disk-write item)

Edit 1 — import (prd_gui_setup.py:34):
**BEFORE**
```python
from vibmshared.core.sys_config    import set_sys_value
```
**AFTER**
```python
from vibmshared.core.sys_config    import get_sys_value, set_sys_value
```

Edit 2 — replace ALL THREE occurrences:
**BEFORE** (x3)
```python
        ok, serial_no = self._get_serial_from_widget()
        if not ok:
            return
        set_sys_value("sys_ser_no", serial_no)
```
**AFTER** (x3)
```python
        ok, serial_no = self._get_serial_from_widget()
        if not ok:
            return
        if get_sys_value("sys_ser_no") != serial_no:   # full INI rewrite only on change
            set_sys_value("sys_ser_no", serial_no)
```

## B4  [T6] straggler: guard load_master_file's client fields

**BEFORE**
```python
            client   = self.client_info.get("client", "unknown").title()
            order_id = self.client_info.get("order_id", "0000")
```
**AFTER**
```python
            # str() guard — [T6] gap: this site was missed in the Phase-1
            # consumer fixes; a purely-numeric client name crashed the whole
            # summary load via the outer except.
            client   = str(self.client_info.get("client", "unknown")).title()
            order_id = str(self.client_info.get("order_id", "0000"))
```

## B5  prd_features.py: header + booleans (whole-file replace)

```python
# prd_features.py

FEATURE_FLAGS = {
    "ENABLE_EXTRA_DEVICE"   : False,
    "ENABLE_SETUP_DROPDOWN" : False,

    "ENABLE_BRD_DROPDOWN"   : True,
    "ENABLE_ADC_DROPDOWN"   : True,
    "ENABLE_SYS_DROPDOWN"   : True,

    "ENABLE_BUILD_TOP_BUTTON" : False,

    # Add more as needed
}

# Sanity check
for key, value in FEATURE_FLAGS.items():
    assert isinstance(value, bool), f"Invalid value for {key}: {value}"

# Wrapper function for clean access
def IS_ENABLED(flag_name: str) -> bool:
    """Check if a feature flag is enabled."""
    try:
        return FEATURE_FLAGS[flag_name]
    except KeyError:
        raise KeyError(f"Unknown feature flag: {flag_name}")
```
(Flag VALUES preserved exactly: BRD/ADC/SYS enabled, rest disabled. GLB_VALID/
GLB_INVALID had zero importers outside this file — verified repo-wide.)

## B6  Data Setup dropdown rekey 'd' -> 'u'

**BEFORE**
```python
        if IS_ENABLED("ENABLE_SETUP_DROPDOWN"):
            # NOTE: key 'd' collides with the "Device Setup" button shortcut —
            # rekey this dropdown before ever enabling the flag ([T3] note).
            self.dropdowns['d'] = create_dropdown_button(
                parent=self.toolbar,
                label="Data Setup",
                underline_idx=0,
                key='d', # Ctrl+D		
                item_list=[
                ("Master Setup", 0, self.master_setup_button, 'm'),
                ("Device Setup", 0, self.device_setup_button, 'd'),
                ("Summary",      0, self.summary_button,      's'),   
            ],
            tooltip_msg = "Ctrl+D - Select Data Setup"
            )
```
**AFTER**
```python
        if IS_ENABLED("ENABLE_SETUP_DROPDOWN"):
            # 'u' ("Data Set_u_p"): 'd' collided with the Device Setup button
            # shortcut — rekeyed proactively so enabling the flag is safe.
            self.dropdowns['u'] = create_dropdown_button(
                parent=self.toolbar,
                label="Data Setup",
                underline_idx=8,
                key='u', # Ctrl+U
                item_list=[
                ("Master Setup", 0, self.master_setup_button, 'm'),
                ("Device Setup", 0, self.device_setup_button, 'd'),
                ("Summary",      0, self.summary_button,      's'),   
            ],
            tooltip_msg = "Ctrl+U - Select Data Setup"
            )
```
(If the BEFORE mismatches on the trailing whitespace after `# Ctrl+D`, match
without trailing spaces.)

## B7  state_write -> is_new_setup (3 edits)

**BEFORE** (:95)
```python
                        setup_mode: str = "master", state_write: str = "True"):
```
**AFTER**
```python
                        setup_mode: str = "master", is_new_setup: bool = True):
```
**BEFORE** (:116)
```python
            self.value_state = "normal" if state_write else "readonly"  
```
**AFTER**
```python
            self.value_state = "normal" if is_new_setup else "readonly"  
```
**BEFORE** (:753)
```python
                                setup_mode = self.setup_mode, state_write = self.new_setup)
```
**AFTER**
```python
                                setup_mode = self.setup_mode, is_new_setup = self.new_setup)
```
(Also fixes the latent string-truthiness trap: the old default "True" was a
str, so even "False" would have been truthy.)

## B8  Remove the dead self.running flag (vibmtool.py, 2 deletions)

**BEFORE**
```python
        self.running = True   # Flag to track application state
```
**AFTER**  (delete the line)

**BEFORE**
```python
    def stop(self, *args):
        """Gracefully exit the application."""
        self.running = False

        # Route through quit_button() so the serial port is closed on ALL
```
**AFTER**
```python
    def stop(self, *args):
        """Gracefully exit the application."""

        # Route through quit_button() so the serial port is closed on ALL
```

================================================================================
CLUSTER C — verification sweep
================================================================================
- VibMTool: cancel-paths test (B1 verify above); a full master -> device ->
  build -> summary round trip; three Write clicks with an unchanged serial —
  sys_config.ini mtime changes at most once.
- VibMScope: sim session with recording + TF (regression); A1/A2 verifies.
- Both: launch both tools (feature-flag files import at startup — the assert
  will catch any typo immediately).

================================================================================
CLUSTER D — documentation closeouts
================================================================================

VibMScope/CLAUDE.md:
1. CLOSED (2026-07-16, owner decision): dB-mode FFT axis — FFT dB values are
   always positive at this product's signal levels; the abs() guard already
   prevents axis inversion. No dB-axis rework planned. (Do not re-raise.)
2. FIXED: x-tick labels now follow hdr_handler.system_time (RTC-preferred,
   laptop fallback) — DECIDED 2026-07-16.
3. FIXED: ydata_to_unit per-call factor + int16 saturation; DECIDED: unit
   changes permitted in session-OFF only (record the rule itself).
4. FIXED/REMOVED: close_open_files() deleted (caller-less since [F2]).
5. OPEN (unchanged): maps_class __main__ self-test — pending owner decision
   after discussion (see chat explanation).
6. vib_features.py header + boolean cleanup noted (consistency with
   prd_features.py; zero external GLB_ importers).

VibMTool/CLAUDE.md:
1. FIXED: status bar now reflects real setup/summary outcome (SetupManager
   .completed / SetupDialog.opened / SummaryDialog.completed).
2. FIXED: mode prompt is askyesnocancel — dead None-branch now live, real
   Cancel added (window-X now cancels instead of meaning Edit).
3. FIXED: sys_ser_no written only on change (was a full INI rewrite per click).
4. FIXED: prd_features.py header + booleans; GLB_VALID/GLB_INVALID removed.
5. FIXED: state_write -> is_new_setup (plus the str-default truthiness trap).
6. FIXED: dead self.running removed; Data Setup dropdown rekeyed to Ctrl+U.
7. FIXED ([T6] straggler): load_master_file client/order str() guards.
8. CLOSED-ACCEPTED (2026-07-16, do not re-raise):
   - InputManager / self.im naming: kept — grep-friendly, rename churn across
     every call site outweighs the readability gain.
   - MainApp name ambiguity: kept — ProductMeta window titles and per-tool log
     files already disambiguate at runtime.
   - Synchronous command GUI freeze during long Write & Verify runs: accepted
     architecture limitation of the single-threaded design; revisit only if
     operators report it (cheap mitigation then: busy cursor + update_idletasks
     around the loops, or a worker thread as a larger change).

Root CLAUDE.md: one line noting the 2026-07-16 review backlog is now fully
dispositioned across both projects (fixed or explicitly closed), with the two
intentionally-open items: VibMScope __main__ self-test (pending discussion)
and event-capture wiring (parked by owner).

================================================================================
Claude Code prompt (suggested)
================================================================================
```
Read phase3_fixes.md in the repo root. Apply clusters A, B, D in order (C is
a manual test list). A4 and B5 are whole-file replacements; B3 Edit 2 is a
replace-all (3 identical occurrences); everything else is a targeted edit
whose BEFORE block must match verbatim — if one does not match, STOP and
report it instead of improvising. Make no other changes. Do not run git
commands. When done, list every file touched with a one-line summary and
flag any BEFORE block you could not match.
```
