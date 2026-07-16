# VibMTool — Configuration Setting and Reading Tool

Purpose: configuration setting and reading tool for GSN Node unit
over CDC/USB, used either at factory or in field.

## Entry point
- `vibmtool.py` — application start, GUI init, connects to shared transport layer.

## Structure
- Source files at project root — GUI + tool-specific logic
- `config/` — device/tool config files (defaults + user-saved changes; in review scope)
- `data/`   — generated at runtime, ignored (see .claudeignore)
- `logs/`   — generated at runtime, ignored (see .claudeignore)

## Uses from vibmshared
- Transport (CDC/USB), protocol parsing
- CommandHandler.set_remote_value() / get_remote_value()
  (vibmshared/modules/cmd_remote.py) for parameter set/read —
  see prd_gui_setup.py:463 and :504
- utils_helpers.validate_param_value() for value validation before
  send and after read (prd_gui_setup.py write_single_param /
  read_single_param)
- cmd_helpers.write_module_direct() / read_module_direct() — used by the
  toolbar Board/ADC/System "Set"/"Get" dropdown buttons (prd_gui_main.py
  ButtonManager), separate from the Setup Dialog's per-field path above.
- core: sys_config (get/set_sys_value, sys_config_init), common
  (get_session_flag), serial_comm (SerialPort), path_manager (PathManager),
  product_meta (ProductMeta); modules.simulator (SimulationPort —
  constructed when simulation_mode is on; sets
  'connection'='simulation_port' session flag); utils: gui_utils (wildcard import), status_bar,
  display_helpers (get_display_context), config_io (ConfigIO).
- Full call-site audit done 2026-07-14 (review session) — all of the above
  confirmed signature-compatible with current vibmshared.
- VibMTool is single-threaded (no SerialReader/ConnectionThreadManager
  usage) and never calls set_session_flag('session', True) — the WAIT/
  session-mode code paths below are unreachable from VibMTool today.

## Known issues
- FIXED (2026-07-15): write_module_direct() (vibmshared/modules/cmd_helpers.py)
  could never write SYS_NAME or SYS_LOC — for CMD_TABLE params with
  "gui": None it only checked info["allowed"]/["range"]/["pattern"] for a
  fallback value, never the top-level "default" key that SYS_NAME/SYS_LOC
  use (cmd_remote.py ~L83-87). Since both params also have gui=None
  they're excluded from the Setup Dialog's widget list too
  (_draw_simple_block skips params without gui_def), so the "System Set"
  toolbar button was the only path that could write them, and it silently
  [SKIP]ped both every time. Root cause was in vibmshared (cmd_helpers.py)
  — fixed there (see root CLAUDE.md Conventions & Decisions), verified
  VibMScope had zero call sites for write_module_direct() so no
  cross-project regression risk. Both params now write correctly via the
  toolbar "System Set" button.
- FIXED (2026-07-15): SummaryDialog.load_master_file() (prd_gui_setup.py)
  parsed device_<client>_<order>_<serial>.ini filenames via
  fname.split("_") and read parts[3] as the serial number. The `client`
  field was a free-text Entry with no character validation, so a client
  name containing "_" (e.g. "ABC_Corp") shifted the split and corrupted
  the serial read back — wrong/garbled serials and mismatched file-found
  status in the Summary report.
  FIX: kept client/order free-text (no input restriction — chosen over
  validating input, so operators aren't limited in what they can type).
  load_master_file() now extracts the serial via an anchored regex
  (`^device_.*_(\d+)\.ini$`) on the trailing numeric group instead of a
  fixed split position — correct regardless of how many underscores
  appear in client/order. Separately, save_to_ini() and the two other
  filename-construction sites (build-verification report, summary export)
  now sanitize client/order for genuinely filesystem-illegal characters
  (path separators, `:*?"<>|`, control chars) via a shared
  _sanitize_filename_part() helper — underscores are deliberately left
  alone. Also fixed in the same pass: the old `len(parts) >= 3` guard
  didn't match the `parts[3]` access it guarded, so a malformed filename
  (exactly 3 underscore-separated parts) could raise an uncaught
  IndexError and abort the entire Summary load instead of skipping just
  that one file; now logged and skipped per-file.
- FIXED (2026-07-15): set_remote_value()/get_remote_value() call sites
  (prd_gui_setup.py, inside InputManager.write_single_param/
  read_single_param) didn't special-case a "WAIT" reply (session mode) —
  it was treated the same as an outright failure (write) or fed as the
  literal string "WAIT" into validate_param_value() and logged as a
  validation failure (read). This duplicated — incompletely — the
  WAIT-polling logic that already existed and worked correctly in
  vibmshared/modules/cmd_helpers.py's write_single_param_direct()/
  read_single_param_direct() (used by the toolbar dropdown path, not the
  Setup Dialog path).
  FIX: both InputManager methods now delegate the actual transmit/receive
  to cmd_helpers.write_single_param_direct()/read_single_param_direct()
  instead of calling cmd_handler.set_remote_value()/get_remote_value()
  directly. GUI-specific parts (section→module resolution, widget value
  extraction, widget update after read) stayed local. Was unreachable in
  practice before the fix (VibMTool never enables session mode), so no
  behavioral regression from consolidating — this closes the latent trap
  and removes the duplicate implementation. See root CLAUDE.md
  Conventions & Decisions for the cross-file version of this note.
- FIXED (2026-07-15, found during the WAIT-gap consolidation above, not in
  the original review): write_from_device()/read_from_device()
  (prd_gui_setup.py, the plain toolbar Write/Read buttons — as opposed to
  Write & Verify) assigned the raw (bool, value) tuple returned by
  write_single_param()/read_single_param() directly to `success`, without
  unpacking. A non-empty tuple is always truthy, so
  `"OK" if success else "FAIL"` evaluated to "OK" unconditionally — the
  status column never showed "FAIL", even on an outright write/read
  failure. Only write_and_verify_device() unpacked the tuple correctly
  and was unaffected. Fixed both call sites to `success, _ = ...`.
- write_single_param()/read_single_param() docstrings said "Returns: True
  if write succeeded, False otherwise" but the actual return type is a
  2-tuple (bool, value) — FIXED (2026-07-15) alongside the WAIT-gap
  consolidation above; docstrings now say
  "(True, validated_value) / (False, None)".
- Two `log_handler.log()` error calls in InputManager.write_single_param()
  (prd_gui_setup.py, the "module not found"/"param not found" branches)
  omitted `tag="error"` — FIXED (2026-07-15) alongside the WAIT-gap
  consolidation above; now use safe_log(..., tag="error") consistently
  with the rest of the function.

### Still open (not fixed this session — cosmetic/naming, no correctness impact)
- SetupManager._run() (prd_gui_setup.py) checks
  `if self.new_setup is None:` after messagebox.askyesno(...), but
  askyesno always returns True/False, never None — dead branch.
- set_sys_value("sys_ser_no", serial_no) is called with default
  autosave=True on every Write/Read/Verify click, causing a full
  sys_config.ini rewrite (with checksum recompute) each time. Functionally
  fine, just an avoidable disk write per click if it ever becomes a
  bottleneck.
- prd_features.py — file header comment says `# feature_flags.py` (stale,
  from before a rename); actual filename is prd_features.py.
- GLB_VALID/GLB_INVALID constants (prd_features.py) are just 1/0 standing
  in for booleans — indirection with no apparent benefit.
- InputManager is a generic name for what is specifically the
  Master/Device/Program setup-INI data model; self.im (SetupDialog's
  InputManager instance) is a terse abbreviation that hurts readability
  at call sites.
- state_write parameter on InputManager.__init__ is actually a "New
  setup?" boolean forwarded from askyesno, not a "state" string; a name
  like writable or is_new would better match its use.
- MainApp (vibmtool.py) is generic enough to be ambiguous in shared
  logs/tracebacks alongside VibMScope's own MainApp.
- self.running flag in MainApp (vibmtool.py) is set in __init__/stop()
  but never read anywhere — dead attribute.
- Every command (Read/Write/Verify) blocks the Tk main loop synchronously
  (CommandHandler.send_command → receive_data(..., timeout=CMD_TIMEOUT_SEC),
  2s). A "Write & Verify" over ~30 parameters with several timeouts could
  freeze the GUI for tens of seconds with no busy indicator — architecture
  limitation, not a bug, not addressed this session.

## Review session 2026-07-15 (fixes)
- prd_gui_setup.py: InputManager.load_from_ini() device branch no longer
  crashes when the device INI has no 'source' key — the default was {} (dict),
  which threw TypeError in os.path.join(). Now reads '' and degrades gracefully
  (warns, skips master mark-back) for missing/blank/nonexistent source.
- prd_gui_meta.py + prd_gui_setup.py: PROGAM_KEY_TOOLTIPS ->
  PROGRAM_KEY_TOOLTIPS typo; SECTION_MASTER_SKIP = {} (dict) -> set() to match
  the sibling section-skip sets.
- Shared-code fixes this session that affect VibMTool at runtime (detail in
  root + vibmshared CLAUDE.md): cmd_remote.py missing `import time` added —
  this is the live Write/Read/Verify path, which would otherwise NameError;
  send_command() unknown-module guard; validate_sys_value() bool fix;
  sys_serial_baudrate -> 115200.

## Known issues (review 2026-07-16 — Claude findings, all OPEN, no code changed yet)

IDs [T1]..[T9] + minor block, roughly in suggested fix order. Items marked
(shared) live in vibmshared and belong in the root CLAUDE.md — listed here
because VibMTool is the affected (often sole) consumer. Verified NOT issues
during this pass, for the record: write_module_direct()'s `info["default"][0]`
indexing is correct (SYS_NAME/SYS_LOC defaults are one-element lists in
CMD_TABLE), and get_relative_path(None) is safe (except-branch returns the
input unchanged).

- FIXED (2026-07-16) [T1]: build_device_list() — merge-regenerate, never
  discard build history. prd_gui_setup.py _on_save() previously wiped all
  device usage tracking: build_device_list() is called for setup_mode
  'master' unconditionally (new AND edit); it did device_info.clear() and
  refilled every serial as "unused". Opening an existing master and saving
  ANY change erased every "used, <date>" mark that
  mark_serial_used_in_master() maintains — Summary then showed every
  previously-built device as "YES[Error]" (file exists for an 'unused'
  serial). FIX (per DECIDED 2026-07-16, root CLAUDE.md): build_device_list()
  now merges instead of clearing — serials still in range keep their
  existing "used, <date>" value, "used" entries falling OUT of a shrunk
  range are KEPT (build history is never silently discarded), and only
  out-of-range "unused" entries are dropped. _on_save() stays unchanged:
  with merge semantics, calling it on both new and edit is now correct
  (qty/base edits take effect, marks survive). Also quietly fixes the
  old-master-without-device_info KeyError edge (.get(..., {}) + section
  reassignment).

- FIXED (2026-07-16) [T2]: guarded serial helper + three call sites.
  write_to_device() / read_from_device() / write_and_verify_device() all did
  `int(self.im.program_widgets['sys_ser_no']['widget'].get())` unguarded.
  Empty or non-numeric serial text raised ValueError inside the Tk
  callback: no messagebox, no log entry — the button just "did nothing"
  with a console traceback. It also skipped SERIAL_RANGE validation
  entirely (the range check existed only in load_from_master()'s prompt
  path). FIX: new SetupDialog._get_serial_from_widget() helper (try/int,
  SERIAL_RANGE check, error box + red log line on failure, returns
  (ok, int)); all three buttons now call it and return early when not ok.
  Still open, unchanged in scope: the unconditional set_sys_value autosave
  per click (see the cosmetic still-open entry above) and the fact that the
  serial is read even when sys_ser_no isn't selected.

- FIXED (2026-07-16) [T3]: store the dropdowns, rebind System to Ctrl+Y.
  Dropdown keyboard shortcuts were advertised but never bound, and Ctrl+S
  opened Summary instead of the System menu: create_dropdown_buttons()
  (prd_gui_main.py) discarded the returned (menu_button, menu), so
  self.dropdowns stayed empty forever, making bind_all()'s dropdown loop
  dead code and leaving set_button_state()/get_button_state()/
  reset_all_buttons() unable to affect dropdowns.
  FIX (decisions from the Phase 1 pack): (a) all four create_dropdown_button()
  returns are now stored in self.dropdowns, keyed by shortcut — bind_all()
  needed no change and now binds Ctrl+B / Ctrl+A / Ctrl+Y to popup_menu;
  (b) the System dropdown moved from 's' to 'y' (Ctrl+Y, underline_idx=1
  on "SYstem") because Ctrl+S stays with the already-live Summary button;
  its tooltip now reads "Ctrl+Y - Select System"; (c) the shape mismatch is
  resolved in favour of the (menu_button, menu) tuple that bind_all()
  expects — set_button_state()/get_button_state() now unwrap it via
  `if isinstance(btn, tuple): btn = btn[0]`. The Data Setup dropdown is
  stored under 'd', which collides with the "Device Setup" simple-button
  shortcut; an inline NOTE flags that it must be rekeyed before
  ENABLE_SETUP_DROPDOWN is ever turned on (the flag is off today).

- FIXED (2026-07-16) [T4]: load_from_master() signals failure; SetupDialog
  aborts. Cancelling (or failing) the serial-number prompt still opened the
  Device-from-Master dialog on pure defaults: load_from_master() returned
  early on cancel / out-of-range / non-integer, but SetupDialog didn't know
  — it drew the window on load_from_defaults() data and logged "Loaded
  Device Config from: <master>" even though the master was never applied.
  Saving then produced a defaults-only
  device_<client>_<order>_<gui-default>.ini that looked legitimate.
  FIX: load_from_master() is now `-> bool` — returns False on the cancel
  and invalid-serial paths and from the exception handler, True on the
  success tail; SetupDialog's device+new branch checks the return, logs
  "<prefix> setup aborted — master not applied." (warn) and returns. The
  early return happens BEFORE tk.Toplevel is created, so no window appears
  and SetupManager's constructor simply finishes.

- FIXED (2026-07-16) [T5]: prd_gui_setup.py SummaryDialog —
  self.displayed_serials was first created at :1184, inside
  load_master_file()'s try, AFTER the ConfigIO load. If the master failed
  to parse, the error box showed but the window stayed open with all three
  export buttons live; clicking any of them hit
  `if not self.displayed_serials` -> uncaught AttributeError. Fixed:
  self.displayed_serials = set() is now initialized in __init__ (exports
  then correctly report "No data to export").

- FIXED, consumer half (2026-07-16) [T6]: (shared:
  vibmshared/utils/config_io.py, VibMTool is the only consumer)
  ConfigIO.load_file() runs ast.literal_eval on EVERY value, so a
  purely-numeric client name ("1234") comes back as int, "True" as bool.
  save_to_ini() then called client.lower() (BEFORE its try block) ->
  AttributeError surfaced as a cryptic error box;
  SummaryDialog.generate_metadata_header() does client.title() and is
  called OUTSIDE export_text()'s try -> uncaught crash. order_id already
  round-trips as int (202506) and survived only because nothing calls a
  str method on it.
  FIX (A5, the cheapest of the two options): str() guards at the consumers
  — save_to_ini()'s client/order reads and generate_metadata_header()'s
  client/order_id reads are now wrapped in str(). The root cause
  (literal_eval coercion) is DOCUMENTED-BY-DESIGN in config_io.load_file()
  via an inline NOTE [T6] rather than changed — free-text meta keys are
  NOT exempted from literal_eval. No further change planned unless a new
  consumer of these free-text fields appears; if one does, it must str()
  before calling any str-method. Note load_master_file() has its own
  `.title()` on client that was deliberately left out of scope by the
  pack — it sits INSIDE that function's try, so it degrades to the
  existing error box rather than crashing uncaught.

- FIXED (2026-07-16) [T7]: the two dead "status" stores are DELETED. The
  "OK"/"FAIL" stored into program_widgets[flat_key]["status"] by
  write_to_device()/read_from_device() was a dead store: nothing read that
  key anywhere (the build report consumes only verification_results; there
  is no GUI status column). DECIDED in the Phase 1 pack: delete rather than
  surface — per-param outcomes already go to the log via
  write_single_param()/read_single_param(), and the report consumes
  verification_results only. Both stores are now replaced by a comment
  recording that. Plain Write/Read outcomes remain visible only in the
  scrolling log, which is the accepted behaviour.

- FIXED (2026-07-16) [T8]: stop() now routes through quit_button().
  vibmtool.py stop() previously never closed the serial port. Window-X /
  SIGINT / SIGTERM all route to stop(), which only did root.quit(); the
  port close lived solely in ButtonManager.quit_button() (Ctrl+Q path).
  VibMScope routes its stop() through quit_button(); VibMTool didn't —
  inconsistent, port stayed open until process teardown. Fixed: stop() now
  delegates to self.main_frame.buttons.quit_button().

- FIXED (2026-07-16) [T9]: two stale entries in this file itself (doc
  drift, not code) are corrected: (a) "Uses from vibmshared" described
  modules.simulator Simulator as "constructed, never .start()ed" for the
  connection-flag side effect — current code constructs SimulationPort(),
  and that bullet now reads "modules.simulator (SimulationPort —
  constructed when simulation_mode is on; sets
  'connection'='simulation_port' session flag)"; (b) the still-open item
  "vibmtool.py:46 stale commented-out import" is deleted — that comment no
  longer exists in current source (line 46 is now the SimulationPort
  import).

- Minor block (2026-07-16), grouped — all FIXED in Phase 1 except the one
  marked STILL OPEN at the end:
  * FIXED (A6) prd_gui_setup.py mark_serial_used_in_master() — key matching
    was verbatim widget text: a serial typed as " 105" or "0105" ADDED a
    stray device_info key instead of flipping "105"'s status. Now
    strip()ped and, when all-digits, normalized via str(int(...)) so the
    register stays keyed consistently with build_device_list()'s str(sn).
    NOT addressed (unchanged, accepted): the function still re-saves the
    ENTIRE master file (as re-parsed through literal_eval) as a side effect
    of saving a device.
  * FIXED (B3) gui_utils.py apply_tooltip() lowercases the button label as
    the dict key — "Write & Verify" / "Save Report" didn't match "verify" /
    "save" in PROGRAM_KEY_TOOLTIPS, so those tooltip strings were dead.
    Resolved by renaming the dict keys to match the labels (the first of
    the two options): "verify" -> "write & verify", plus a new "save report"
    entry. "save" stays — the Save button in _draw_footer_buttons uses it.
    (shared function, vibmtool-owned dict)
  * FIXED (B2) (shared) gui_utils.py create_dropdown_button() called
    menu.add_separator() on EVERY iteration (`# if i == 1:` commented out)
    — leading separator in every dropdown menu. Now `if i > 0:`, i.e. a
    separator BETWEEN items only. The per-item `shortcut` field in
    item_list remains accepted and unused; it's now marked reserved with an
    inline comment rather than removed (menu accelerators not wired).
  * FIXED (B4) (shared) status_bar.py StatusBarHandler — the style_dict
    param and the computed default_style were never used; the label
    hard-coded STATUS_LABEL_STYLE, making VibMTool's
    style_dict=STATUS_LABEL_STYLE argument a no-op. style_dict is now
    actually applied (`**style`), the dead default_style dict is deleted,
    and the fallback is STATUS_LABEL_STYLE — so both tools render exactly
    as before (VibMScope passes no style; VibMTool passes the same dict
    that was previously hard-coded).
  * FIXED (A7) prd_gui_setup.py SummaryDialog — sorted(..., key=lambda x:
    int(x[0])) (load_master_file and the three exports) meant ONE
    hand-edited non-numeric device_info key aborted the entire summary
    load/export. New module-level _serial_sort_key() sorts numeric serials
    numerically and pushes non-numeric keys after them alphabetically, so a
    bad key no longer aborts anything. Applied at all five sites, including
    the ENABLE_EXTRA_DEVICE branch (flag off today).
  * FIXED (A8) prd_gui_setup.py — Summary/build exports wrote fixed names
    into config_dir with no overwrite prompt (save_to_ini() asks; exports
    and save_device_report() didn't). New module-level _confirm_overwrite()
    guards all four sites (export_text/export_csv/export_pdf/
    save_device_report), matching save_to_ini()'s existing prompt.
  * FIXED (C1/C2) (shared) config_io.py latent traps: load_file() now builds
    a FRESH configparser per call (the single self.parser instance
    accumulated sections across calls if one ConfigIO was ever reused — all
    callers construct fresh instances, so this was dormant) and the unused
    self.parser attribute is removed; the dead `if not isinstance(value,
    str)` warn branch is deleted (configparser values are always str);
    save_file() now guards makedirs against a bare filename
    (`if dir_name:`), which previously crashed on os.makedirs('').
  * STILL OPEN — deferred, needs SetupManager outcome reporting:
    prd_gui_main.py toolbar setup buttons update the status bar
    unconditionally after their try/except — "MASTER Data" / "BUILD
    Device" etc. display even when the dialog raised or the user cancelled
    at the first prompt. Not fixed in Phase 1: it needs SetupManager to
    report an outcome back to the caller; small plumbing, do it alongside
    any future SetupManager work.

- Cross-file note (2026-07-16): shared-layer halves above to copy to the
  root CLAUDE.md rather than track here: [T3] create_dropdown_button()
  never binding its `key` param, [T6] ConfigIO literal_eval type-churn,
  plus the minor-block items marked (shared): dropdown leading
  separator / unused per-item shortcut, StatusBarHandler dead style_dict,
  ConfigIO latent traps.

## Phase 3 closeout (2026-07-16 — deferred-minors dispositioned)
1. FIXED: status bar now reflects real setup/summary outcome (SetupManager
   .completed / SetupDialog.opened / SummaryDialog.completed) — the
   toolbar buttons update the status bar only on completion, not on
   error/cancel/abort. Closes the "STILL OPEN" minor above.
2. FIXED: mode prompt is askyesnocancel — dead None-branch now live, real
   Cancel added (window-X now cancels instead of meaning No/Edit); the two
   question strings advertise "Cancel = Abort".
3. FIXED: sys_ser_no written only on change (get_sys_value guard) — was a
   full INI rewrite per Write/Read/Verify click.
4. FIXED: prd_features.py header + booleans; GLB_VALID/GLB_INVALID removed.
5. FIXED: state_write -> is_new_setup (plus the str-default "True"
   truthiness trap: bool default now).
6. FIXED: dead self.running removed (vibmtool.py); Data Setup dropdown
   rekeyed 'd' -> 'u' (Ctrl+U, "Data Set_u_p"), collision note dropped;
   flag stays disabled.
7. FIXED ([T6] straggler): load_master_file() client/order_id str() guards
   — the site missed by the Phase-1 consumer fixes.
8. CLOSED-ACCEPTED (2026-07-16, do not re-raise):
   - InputManager / self.im naming: kept — grep-friendly, rename churn
     across every call site outweighs the readability gain.
   - MainApp name ambiguity: kept — ProductMeta window titles and per-tool
     log files already disambiguate at runtime.
   - Synchronous command GUI freeze during long Write & Verify runs:
     accepted architecture limitation of the single-threaded design;
     revisit only if operators report it (cheap mitigation then: busy
     cursor + update_idletasks around the loops, or a worker thread as a
     larger change).
