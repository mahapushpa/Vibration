## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

# working/ — GSN Node System projects
STM32-based GSN Node System. Laptop side (Python) is used, and it is divided into three
parts: tool, scope and logger. Remote side (STM32L4P5, KEIL MDK, C) is separate
hardware/firmware and is out of scope for this review — do not read or search for
firmware source.

## Structure
- `vibmshared/` — common code (serial/USB CDC transport, protocol parsing,
  config handling) used by all projects below. Treat as the shared API —
  changes here can affect every project.
- `VibMTool/`   — production/setting tool (Project 1)
- `VibMScope/`  — vibration scope, 2-channel, transfer function matters (Project 2)
- `VibMLogger/` — see VibMLogger/CLAUDE.md
- `_miscellaneous/` — not part of any project (old tests, scratch, docs). Ignored.

## Rules
- Don't modify `vibmshared/` without checking usage in all consuming projects.
- Read the relevant project's own CLAUDE.md before working inside it.
- print()+logging duplication is intentional (logs aren't actively monitored in the
  field) — do not "clean up" to logging-only.
  
## Conventions & Decisions (from review sessions)
- report_key_error() (renamed from raise_key_error_msg): conditional raise
  in debug_mode, else logs+returns. Callers check return, not assume raise.
  Confirmed 2026-07-14: raise_key_error_msg and normalize_value1 (both
  pre-rename names flagged in old review .txt notes) are fully gone from
  current vibmshared — zero references repo-wide. Only stale mentions
  remain in graphify-out/ dated snapshots and _miscellaneous/ review notes;
  not live code, no cleanup action needed.
- Call-site audit of set_remote_value/get_remote_value/write_data/
  write_metadata/save_event_data (2026-07-14): VibMTool only calls
  set_remote_value()/get_remote_value() (prd_gui_setup.py:463,504) — both
  signature-compatible with cmd_remote.py. VibMScope only calls
  write_data()/write_metadata()/save_event_data() (maps_signal.py) — all
  signature-compatible with file_save.py. Neither project calls the
  other's functions (expected: VibMTool doesn't do data capture, VibMScope
  doesn't do remote set/get). VibMTool's two call sites don't special-case
  a "WAIT" reply — falls under the last_reply/WAIT gap noted below.
- write_metadata_header() (vibmshared/utils/utils_helpers.py, a free
  function for formatted info blocks, used by maps_transfer.py) is a
  different function from FileSave.write_metadata() (the metadata-file
  writer used by maps_signal.py) — similar names, don't conflate when
  searching or refactoring.
- Icon/logo asset (vibmshared/core/maps_logo.ico) — REVERTED to the original
  256x99 single-entry .ico on 2026-07-15 and left alone deliberately. It is a
  non-square banner ("MAPS" + "Training and Development" tagline) that Windows
  squashes into the square title-bar slot, so it looks blurry/distorted. A
  rebuild as a proper square multi-size .ico (letterboxing the wordmark, from a
  3920x1152 source) was tried and REJECTED: letterboxing a 3.43:1 mark leaves it
  only ~5px tall at 16x16, i.e. technically correct but far less visible than the
  distorted original. If this is revisited, the only option that gives BOTH
  visibility and sharpness is cropping to a square emblem (e.g. the "M") so it
  fills the slot — and any candidate must be judged from a 1:1 actual-size
  preview, never a magnified one.
- print()+logging duplication is intentional (logs aren't watched live) —
  do not "clean up" to logging-only.
- CommandHandler.send_command() session-mode returns 4-item status tuples:
  ("WAIT"/"BUSY"/"FAILED", None, None, None) instead of True/None, so
  callers can always unpack `resp_code, _, _, value = reply`.
- Single in-flight command enforced via cmd_waiting + cmd_sent_time,
  2s timeout (CMD_TIMEOUT_SEC). Result delivered via cmd_handler.last_reply,
  set inside rcv_response() once validated — not a queue.
- GUI wiring (last_reply polling, is_connection_healthy(), status bar
  thread-safety) is deferred — not yet implemented, planned for P2.2.
- P2.2 status (2026-07-14 threading review): update_gui() and status-bar
  calls are correctly confined to the main thread today (queue-based
  handoff from SerialReader, root.after() polling) — no live Tkinter/
  matplotlib-from-background-thread violation found in the running app.
  Simulator.setup_plot()/update_plot() (vibmshared/modules/simulator.py)
  DO call matplotlib from Thread.run(), but only when enable_plotting=True,
  which production code (ConnectionThreadManager.start()) never passes —
  only simulator.py's own __main__ demo does. Guard this if that
  constructor call ever changes.
- FIXED (2026-07-15): last_reply was confirmed unconsumed at the *direct
  call-site* level: grepped vibmscope + vibmtool, zero callers polled
  cmd_handler.last_reply after send_command()/set_remote_value()/
  get_remote_value() returned "WAIT".
  CORRECTION (2026-07-14 VibMTool review): cmd_helpers.py's
  write_single_param_direct()/read_single_param_direct() do NOT have this
  gap — they already poll via a private _wait_for_last_reply() helper
  (WAIT_POLL_INTERVAL_SEC=0.05, capped at CMD_TIMEOUT_SEC) before treating a
  reply as failed/missing. The real gap was in code that duplicated
  cmd_helpers' set/get logic instead of calling it: VibMTool's
  InputManager.write_single_param()/read_single_param()
  (VibMTool/prd_gui_setup.py) reimplemented the same set_remote_value/
  get_remote_value call but without the WAIT-polling wrapper.
  FIX: both functions now delegate the actual transmit/receive to
  cmd_helpers.write_single_param_direct()/read_single_param_direct()
  instead of calling cmd_handler.set_remote_value()/get_remote_value()
  directly — closes the gap and removes the duplicate implementation.
  GUI-specific parts (section→module resolution, widget value extraction,
  widget update after read) stayed local since cmd_helpers has no GUI
  awareness. Was unreachable in practice before the fix (VibMTool never
  enables session mode) so no regression risk from the change itself.
  Re-check VibMScope's own call sites the same way before trusting old
  claims about them — VibMScope doesn't call these InputManager methods
  (it's VibMTool-only code) so it was never affected either way.
- FIXED (2026-07-14): write_module_direct() (vibmshared/modules/cmd_helpers.py)
  previously dropped any CMD_TABLE param whose only fallback value was a
  top-level "default" key (as opposed to "gui"→"default", "allowed",
  "range", or "pattern") — it never checked that key, so the param got
  silently [SKIP]ped. Confirmed concretely via SYS_NAME/SYS_LOC in VibMTool
  (see VibMTool/CLAUDE.md known issues) — both have "gui": None + a
  top-level "default" and could never be written via write_module_direct
  as a result. Patched by adding a `"default" in info` check ahead of the
  allowed/range fallback in Step 2 of write_module_direct().
  Cross-project check before patching: VibMScope's ButtonManager
  (vibmscope/maps_class.py) has `self.create_dropdown_buttons()` commented
  out entirely, and even that method's body never calls
  write_module_direct()/read_module_direct() (only wires a dummy Mode
  dropdown) — so VibMScope has zero call sites for this function today and
  carried no regression risk from this fix. VibMTool's toolbar Set buttons
  (prd_gui_main.py ButtonManager, gated by IS_ENABLED("ENABLE_*_DROPDOWN"))
  are the only live callers and now behave correctly for SYS_NAME/SYS_LOC.
  If VibMScope's dropdown wiring is ever un-commented and starts calling
  write_module_direct()/read_module_direct(), re-check its CMD_TABLE
  entries for the same gui=None + top-level-default shape — the fix
  already covers it, this is just a heads-up, not an open risk.
- send_command()'s two "FAILED" fast-return paths (encode_value failure,
  send_data failure) never clear cmd_waiting, forcing a spurious
  CMD_TIMEOUT_SEC (2s) lockout before the next command can be attempted
  even though the failure was immediate/local.
- cmd_waiting is global (SessionParameters) but cmd_sent_time/last_reply
  are per-CommandHandler-instance. If a new CommandHandler is constructed
  while the global flag is still stuck True, send_command() computes
  `time.time() - self.cmd_sent_time` against a fresh None -> TypeError.
  maps_class.py::session_button() also sets cmd_waiting directly around the
  session-stop handshake, independent of CommandHandler's own bookkeeping —
  the two can conflict (see vibmscope/CLAUDE.md known issue).
- RESOLVED (verified in code 2026-07-15): the two bullets immediately above are
  STALE — kept for history only. Both send_command() FAILED fast-returns now
  clear cmd_waiting (set_session_flag('cmd_waiting', False) before return, P2.2
  Finding 3); the top-of-function guard `if self.cmd_sent_time is not None and
  ...` prevents the `time.time() - None` TypeError and logs+clears a stale
  cross-instance flag (P2.2 Finding 4); and maps_class.py no longer sets
  cmd_waiting manually (only explanatory NOTEs remain at session_button()/
  quit_button()).
- FIXED (2026-07-16): parameters.py:55 WindowParams 'barlett' -> 'bartlett'
  (shared). is_valid() accepted the misspelling and rejected correct
  'bartlett'; scipy get_window('barlett') raises, so selecting it crashed
  SignalProcessor.preprocessing_signal every second. label() at :85 already
  spelled it correctly — the two lists now agree. Cross-project check:
  consumed only by VibMScope's SignalProcessor (via get_sys_value('window')
  validation); VibMTool never reads the 'window' key — no regression risk.
  A legacy sys_config.ini storing 'barlett' now fails is_valid and falls
  through to the default ('hann') instead of crashing scipy — no migration
  shim added.
- FIXED (2026-07-16, shared half of VibMScope [F9]): serial_comm.py
  SerialReader.run() — a full queue_handler (maxsize 8, drained max 4 per
  100 ms tick) silently dropped a whole captured fragment; the drop is now
  logged via safe_log("[WARN] GUI queue full — fragment dropped ..."). This
  only makes the loss observable — the vibmscope-side resync (clear
  buffer+flags when a new second starts over partially-set flags) stays OPEN
  as [F9]'s remaining half. Cross-project check: SerialReader is constructed
  only by ConnectionThreadManager.start(), used only by VibMScope (VibMTool
  is single-threaded, no SerialReader usage).
- DECIDED (2026-07-16, [F2] VibMScope): session-stop and quit while recording
  MUST save partial window data + insert closing time (route through
  close_current_file(), same sequence tf_button Case 1 already uses).
  Rationale: captured vibration data may be unrepeatable — never discard on
  exit. Fix itself is Phase 2, decision recorded now.
- DECIDED (2026-07-16, [T1] VibMTool): on master EDIT-save, device_info is
  merge-regenerated: rebuild the base_serial..base+qty range, carry over
  existing "used, <date>" values for serials still in range, KEEP any "used"
  entries that fall outside a shrunk range (build history is never silently
  discarded), drop only out-of-range "unused" entries. Fix itself is Phase 1,
  decision recorded now.
- FIXED (2026-07-16, Phase 1 [B2], shared): gui_utils.py
  create_dropdown_button() called menu.add_separator() on EVERY loop
  iteration (the `# if i == 1:` gate was commented out), giving every
  dropdown menu a leading separator above its first item. Now `if i > 0:` —
  a separator BETWEEN items only. The per-item `shortcut` field in item_list
  stays accepted-but-unused (menu accelerators are not wired); it's marked
  reserved with an inline comment rather than removed.
  Cross-project check: create_dropdown_button() has NO VibMScope call sites
  — VibMScope's ButtonManager.create_dropdown_buttons() is commented out
  entirely (vibmscope/maps_class.py), so VibMTool is the sole live consumer
  and carried the only regression risk. If VibMScope's dropdown wiring is
  ever un-commented, its menus simply gain the corrected separator layout.
- FIXED (2026-07-16, Phase 1 [B4], shared): status_bar.py StatusBarHandler
  accepted a style_dict param and computed a default_style dict, then
  ignored both — the tk.Label hard-coded **STATUS_LABEL_STYLE. style_dict is
  now actually applied (**style), the dead default_style dict is deleted,
  and the fallback for callers passing nothing is STATUS_LABEL_STYLE (the
  value that was previously hard-coded), so the parameter becomes functional
  with zero visual change.
  Cross-project check: VibMScope constructs StatusBarHandler(self) with NO
  style argument (maps_class.py:53) — it hits the fallback and keeps
  STATUS_LABEL_STYLE exactly as before. VibMTool passes
  style_dict=STATUS_LABEL_STYLE (prd_gui_main.py) — the same dict that was
  hard-coded, so also identical. Both tools render as before; verify by
  launching both.
- FIXED (2026-07-16, Phase 1 [C1]/[C2], shared): config_io.py latent traps.
  (C1) load_file() used a single self.parser built in __init__;
  configparser.read() MERGES into existing state, so a reused ConfigIO
  instance would accumulate sections across calls. load_file() now builds a
  fresh ConfigParser per call and the unused self.parser attribute is
  removed. The dead `if not isinstance(value, str)` warn branch is also
  deleted — configparser values are always str, so it could never fire.
  (C2) save_file() called os.makedirs(os.path.dirname(filepath)) unguarded,
  which raises on a bare filename (dirname == ''); now guarded with
  `if dir_name:`. Both were dormant (all current callers construct fresh
  ConfigIO instances and pass full paths) — fixed to keep them that way.
  Also added: an inline NOTE [T6] in load_file() documenting BY DESIGN that
  ast.literal_eval coerces numeric-looking free text ("1234" -> int, "True"
  -> bool), so consumers of free-text fields must str() before calling any
  str-method. Free-text meta keys are deliberately NOT exempted from
  literal_eval; the guards live at the consumers (VibMTool prd_gui_setup.py,
  see VibMTool/CLAUDE.md [T6]).
  Cross-project check: ConfigIO has NO VibMScope call sites (confirmed in
  both project docs) — VibMTool is the sole consumer. Noted here anyway per
  the shared-fix convention (write_module_direct precedent).

## Review session 2026-07-15 (cleanup + bug fixes — NOT yet committed)
Working-tree changes only; the repo is mid-migration (vibmshared/ untracked),
so git is being handled by the user, not in-session.

- CRITICAL: cmd_remote.py was missing `import time` while send_command() uses
  time.time() (cmd_waiting timeout + cmd_sent_time). Every send_command() would
  raise NameError on its first real call — latent only because the live command
  path had not been exercised end-to-end (sim mode, and VibMTool never enabling
  session mode, hid it). `import time` added; exercise real-hardware send/recv.
- send_command() now guards an unknown module/param: returns
  ("FAILED", None, None, None) and clears cmd_waiting instead of raising a raw
  KeyError from CMD_TABLE[module][param] (which stranded the global flag ->
  spurious 2s BUSY lockout). This just adds a THIRD guard alongside ones already
  in send_command(): both FAILED fast-returns (encode_value/send_data) already
  clear cmd_waiting (P2.2 Finding 3) and the top-of-function guard already
  prevents the `time.time() - None` cross-instance crash (P2.2 Finding 4).
  (An earlier draft of this note wrongly called those two "still open"; verified
  in code they were fixed before this session — see the RESOLVED annotation in
  Conventions & Decisions.)
- rcv_response() now handles a None/empty response before indexing response[0]
  (timeout/closed-port/empty read previously raised TypeError/IndexError inside
  the error-report f-string itself).
- validate_sys_value()/_validate_sys_single_value() (utils/sys_helpers.py):
  remote-key branch used to `return validate_param_value(...)` — a
  (bool, value) TUPLE. Callers test it as a bool and a non-empty tuple is always
  truthy, so ALL remote-key INI validation was silently bypassed. Now returns
  the bool. Out-of-range remote values in a hand-edited sys_config.ini are now
  caught + restored to default on load; all shipped rule-based defaults still
  validate True (checked), so startup is unaffected.
- FileSave (core/file_save.py) called safe_log() in 6 places but never imported
  it -> NameError on any FileSave error path (and save_event_data's success
  log). Import added.
- sys_serial_baudrate default 112500 -> 115200 (common.py; 112500 was a
  non-standard typo, SerialPort already defaulted to 115200). The persisted
  vibmscope/config + vibmtool/config sys_config.ini were also updated; their
  checksums are now stale so those (all-default) files self-regenerate on next
  launch.
- Repaired two broken-but-unused sys_config helpers (kept for next-stage use,
  not removed): sys_reset_to_defaults() now passes default_PathSettings to
  build_defaults() (was no-arg -> TypeError); set_sys_value_default() now writes
  to whichever defaults group holds the key (was a non-existent "Flags" group
  -> KeyError).
- display_helpers.get_display_context() no longer leaks the throwaway Tk() root
  it makes for root=None (old `if root == None: root.destroy()` never fired);
  uses `is None`, destroys only a self-created root.
- Naming/cosmetic: parameters.py get_selected_analysis_type() local `type` ->
  `analysis_type`; maps_transfer getter methods process_info_block/
  analysis_info_block -> get_* (npz string keys unchanged); PROGAM_KEY_TOOLTIPS
  -> PROGRAM_KEY_TOOLTIPS; sys_config log strings (maps_sys.ini ->
  sys_config.ini, missing f-string). See per-project CLAUDE.md for the rest.

## Phase 3 closeout (2026-07-16)
- The 2026-07-16 review backlog is now fully dispositioned across both
  projects (each remaining minor either FIXED or explicitly CLOSED-ACCEPTED
  — see the Phase 3 closeout sections in VibMScope/CLAUDE.md and
  VibMTool/CLAUDE.md). One item remains intentionally OPEN: event-capture
  wiring (parked by owner).
- FIXED (2026-07-16): VibMScope maps_class.py __main__ block — prior
  removal of its test statements left an empty `if __name__ == "__main__":`
  body (SyntaxError, module unimportable). A `raise SystemExit(...)` body
  was added so the file compiles; rework into a real harness later.

