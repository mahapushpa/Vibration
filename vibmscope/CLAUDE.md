# VibMScope — Vibration Transfer Measurement System using Transfer Function

Purpose: Measurement of effectiveness of vibration isolation system used for optical breadboard
system. It captures data from two geophones, one kept at ground and other on table, over
CDC/USB.

## Entry point
- `vibmscope.py` — application start, GUI init, connects to shared transport layer.

## Structure
- Source files at project root — GUI + tool-specific logic
- `config/` — device/tool config files (defaults + user-saved changes; in review scope)
- `data/`   — generated at runtime, ignored (see .claudeignore)
- `logs/`   — generated at runtime, ignored (see .claudeignore)

## Uses from vibmshared
- Transport (CDC/USB), protocol parsing
- FileSave.save_event_data() / write_metadata() / write_data()
  (vibmshared/core/file_save.py) for recording & event-capture I/O —
  see maps_signal.py: save_centered_event() + prepare_event_file_param()
  (event capture, still UNWIRED — next stage), open_new_record_file(),
  save_full_window_data(), save_partial_window_data()
- utils_helpers.write_metadata_header() / write_channel_metadata_block()
  / write_table_block() for transfer-function info blocks in
  maps_transfer.py (a different function from FileSave.write_metadata()
  above — don't conflate)

## Known issues (updated 2026-07-15)

- FIXED (2026-07-15): The session-stop serial race described below is
  already resolved in current code — no longer an open issue, keeping
  this entry for history.
  Both session_button() and quit_button() (maps_class.py) call
  self.stop_cb() BEFORE the blocking send_session_cmd(value=0), not
  after. self.stop_cb() is ConnectionThreadManager.stop() (serial_comm.py),
  which calls connection_thread.stop() then .join(timeout=2) — i.e. it
  actually blocks until the background SerialReader thread exits (or
  logs a warning if it doesn't within 2s) before returning. Confirmed at
  maps_class.py:487 (session_button) and maps_class.py:650 (quit_button);
  both call sites carry inline comments citing "P2.2 Finding 2". No code
  change was needed — only this doc was stale.
  ---
  Original (now-stale) description, kept for context:
  maps_class.py::session_button() stop path is racy on the serial port
  (found in 2026-07-14 threading review): it deliberately flips
  session=False before send_session_cmd(value=0) so the stop command
  goes through CommandHandler's synchronous branch, but
  ConnectionThreadManager.stop() (self.stop_cb()) only runs *after* that
  blocking send/receive completes.

- FIXED (2026-07-15): vibmscope.py:84 — `sys, exc = create_tf_parameters(...)`
  inside MainApp.__init__ shadowed the module-level sys import for the
  rest of the method, so the earlier sys.exit(0) (line 73, "remote not
  responded" path) raised UnboundLocalError instead of exiting cleanly.
  Renamed local var to tf_system; sys.exit(0) now works.

- FIXED (2026-07-15): maps_class.py:686 — reset_button() looked for
  "maps_sys.ini"; sys_config.py's real INI_FILE constant is
  "sys_config.ini" (sys_config.py:37,229). The "Clear Setting" button
  was a permanent no-op. Now imports and uses INI_FILE directly (path,
  dialog text, and log messages all updated). Also note: sys_config.py's
  own log messages at lines 414/436 still print the stale
  "maps_sys.ini" string — cosmetic, log-only, not fixed (out of scope,
  didn't touch sys_config.py).

- FIXED (2026-07-15): maps_transfer.py — user_info_block fallback
  (`data.get('user_info_block', "User Information: N/A").item()`)
  called .item() on the fallback string when the npz key was missing,
  crashing instead of degrading gracefully. Now checks key presence
  first via `'user_info_block' in data` and only calls .item() on the
  actual npz entry.

- FIXED (2026-07-15): maps_transfer.py — extract_signals() (now
  TFSignalIO.parse_txt_export()) didn't guard against a missing "Chn("
  header line; data_start_idx stayed None and `lines[None:]` silently
  sliced the entire file, producing a confusing ValueError deep in
  int() parsing on malformed TXT input. Now raises a clear ValueError
  immediately when the header marker isn't found.

- FIXED (2026-07-15): maps_class.py:324,342 — `ax.set_yticklabels = dq(...)`
  assigned a deque over the method instead of calling it; custom Y tick
  labels never applied, and set_yticklabels became uncallable on that
  Axes afterward. Fixed both (Time Domain + Frequency Domain) to
  actually call the method. Fixing the call surfaced a second, previously-
  masked bug: Frequency Domain's tick positions/ylim run 0..y_span, but
  the label values were computed for -y_span..y_span (copy-pasted from
  the Time Domain block) — corrected to 0..y_span to match its own ticks.

- FIXED (2026-07-15): maps_transfer.py — SimulatorTF.simulate_time_data()
  never trimmed `input_signal` to `n_fft` before `output = input_signal *
  tf_vector`, causing a shape-mismatch crash whenever sample_rate*duration
  wasn't already a power of 2 (e.g. default sim duration 32.0s @ some
  sample rates). Now trims input_signal in place immediately after n_fft
  is computed, so it matches tf_vector's length.

- Naming cleanup (2026-07-15): removed unused `read_single_param_direct`
  import in maps_class.py; renamed `save_to_pdf_sceen` -> `save_to_pdf_screen`
  (maps_transfer.py, definition + one call site). clear_signal_buffers()/
  init_signals_buffers() naming resolved by [you] directly, not touched here.

- Architecture (2026-07-15): maps_transfer.py's `insert_plot_ax_pdf` and
  `insert_plot_ax_screen` (two ~150-line near-duplicates, tuned
  differently on purpose — screen is dynamically resized, PDF targets
  fixed A4) merged into one `insert_plot_ax(..., output_type)` + a
  `PLOT_STYLE` table (screen/pdf keys covering font sizes, per-channel
  vs. combined info-box layout, box position/color). No visual/behavioral
  change confirmed — every literal diffed against the originals.

- Architecture (2026-07-15): TFProcessor (was one ~700-line class mixing
  parsing/npz-IO/curve-fitting/plotting) split into:
  TFCurveFitter (FFT->TF computation, order estimation, 2nd-order curve
  fit — no file/plot dependency), TFSignalIO (TXT parsing, npz save/load,
  text/CSV export — no plotting dependency), TFReportPlotter (screen +
  PDF rendering — needs only a fitter + system reference). TFProcessor
  is now a thin orchestrator composing these three, with its public API
  (constructor, .extract_signals(), .process_npz_data(), .data_path,
  .config_path, .input_signals/.output_signals) unchanged — verified
  against every external call site in maps_class.py/vibmscope.py, none
  needed changes. format_data_info_metadata() also hoisted out of the
  class to a standalone module-level function (it never used self).
  End-to-end smoke-tested (simulate -> npz save/load -> FFT/TF compute
  -> CSV/TXT export -> PDF render) against a mocked vibmshared.

## Review session 2026-07-15 (fixes + event-capture prep)
- vibmscope.py: stop() now cancels the scheduled update_gui by its after() id
  (self._after_id) — the old after_cancel(self.update_gui) passed the bound
  method and never actually cancelled anything.
- maps_signal.py event-capture functions (still UNWIRED, planned next stage)
  reviewed, fixed and renamed:
    * get_event_file_name() -> prepare_event_file_param() (sets the event file
      name, type and start time); event_centered() -> save_centered_event().
    * [A] save_centered_event() returns early unless self.event_detected (no
      counter creep / no save with a stale/None filename).
    * [D] prepare_event_file_param() triggers only on fragment_type in
      ("event","saturation") — the old `!= "normal"` also matched "unknown"
      (HeaderProcessor's corrupted-type fallback).
    * [E] event_start_time = int(system_time) - PRE_EVENT_SECOND (guards a
      np.uint32 RTC value from underflow-wrap).
    * [C] CONFIRMED intended: event state is reset BEFORE the save; a failed
      save drops the event (buffer has scrolled, nothing to keep) — do NOT
      change to reset-after-success.
    * [H] header "Start Date/Time" (system_time - PRE_EVENT_SECOND) and the
      extracted-sample window line up when the event is at the window middle
      (design intent). system_time prefers the remote GSN RTC, else laptop clock.
      (An earlier "asymmetric/off-by" note was a misread — removed.)
    * [B] OPEN: save_centered_event()'s return is tri-valued (True=saved /
      False=save-failed / None=idle-or-not-centred). Fine for once-per-second
      polling; only split None into explicit sentinels if the next-stage driver
      must tell "idle" from "counting". Decide with that driver.
- parameters.py: PlotParams.get_event_span() simplified to a symmetric form
  (mid = span//2; return (mid-pre, mid+pre+1)); identical output for the 5 s
  window and all odd windows. get_selected_analysis_type() local `type` renamed
  to `analysis_type`.
- maps_transfer.py: getter methods process_info_block()/analysis_info_block()
  -> get_process_info_block()/get_analysis_info_block() (npz dict-string keys
  'process_info_block'/'analysis_info_block' UNCHANGED — persisted format);
  docstring/comment fixes (find_sys_parameters return doc, damping clamp comment
  0.6->0.8, estimate_system_order None-branch note).
- maps_transfer.py insert_product_logo(): left UNCHANGED — it still reads
  ProductMeta.get_icon() at zoom=0.50. A switch to a separate hi-res PNG
  (get_logo()) was tried on 2026-07-15 and reverted with the icon rework, so the
  report header and the title bar stay on one uniform artwork. See root
  CLAUDE.md Conventions before revisiting.

## Known issues (review 2026-07-15 — Claude findings, all OPEN, no code changed yet)

IDs [F1]..[F9] + minor block, roughly in suggested fix order. Items marked
(shared) live in vibmshared and belong in the root CLAUDE.md — listed here
because VibMScope is the affected consumer.

- FIXED (2026-07-16) [F1]: maps_signal.py:479 — data_capture()'s timeout
  partial-return path evaluated `len(data) if data else 0` on a numpy
  array; any partial buffer with >1 sample word raised "truth value of an
  array is ambiguous" inside the print, jumped to the except at :487,
  logged the misleading "Communication Lost from Device", and returned None
  — the salvaged partial data was silently discarded on every real
  timeout. Fixed: 'if data' -> 'if data is not None'.

- OPEN [F2] (2026-07-15): maps_class.py session_button():476 +
  quit_button():674 — both use close_open_files() (message-only) instead
  of close_current_file() (partial save + STOP_DATE/STOP_TIME token
  replacement). quit_button() additionally never stops recording at all.
  The normal cleanup path (insert_new_data's prev_record branch ->
  close_current_file) can't fire either, because session stop kills the
  reader thread first. Net effect: stopping the session (or quitting)
  while recording loses the final partial window AND leaves literal
  "{ STOP_DATE }"/"{ STOP_TIME }" placeholders in the file — which then
  crashes parse_txt_export's strptime if that file is later fed to the
  TF pipeline. tf_button() Case 1 (:549-553) already does the correct
  sequence (record_button -> prev_record False -> close_current_file);
  align the other two with it.

- OPEN [F3] (2026-07-15): maps_transfer.py:505-508 — save_tf_pdf()'s
  metadata loop pairs the labels crosswise: input_info_block (signal
  source/type/freq) prints under "System Model Information" and
  tf_info_block (order/damping/natural freq) under "Input Signal
  Information". PDF only — save_to_text_csv (:396-397) has them right.

- OPEN [F4] (2026-07-15): maps_transfer.py:62 —
  format_data_info_metadata()'s post_keys lists "Captured Duration" but
  get_data_info_block() (:842) emits the key as "Duration"; the
  `if key in meta` gate silently drops capture duration from EVERY
  formatted output (PDF metadata block, TXT, CSV). Pick one key name.

- OPEN [F5] (2026-07-15): Ctrl+C is double-bound. ButtonManager binds
  <Control-c>/<Control-C> -> reset_button ("Clear Setting", key 'c')
  via bind_shortcut_pair (root.bind, bindtag "."), while vibmscope.py:
  121-122 binds the same chord -> MainApp.stop() via bind_all (bindtag
  "all"). Tkinter fires BOTH (no "break" returned), so one Ctrl+C press
  opens the reset-confirm dialog and simultaneously begins app shutdown.
  Decide the owner: either move "Clear Setting" off 'c', or drop the
  bind_all quit binding (Ctrl+Q -> quit_button already exists).

- OPEN [F6] (2026-07-15): maps_transfer.py TFCurveFitter — double
  dB->linear conversion when use_db=True: find_sys_parameters() (:197)
  converts tf_mag to linear, then calls estimate_system_order(), which
  converts AGAIN (:149, same self.use_db flag). 10**(linear/20)
  flattens typical TF values to ~1.0-1.4, so peak counting runs on
  near-flat data and the estimated order is wrong whenever
  use_yscale_db is enabled. Latent while use_db stays False. Fix: have
  find_sys_parameters pass already-linear data with a flag, or make
  estimate_system_order take pre-linearized input only.

- OPEN [F7] (2026-07-15): maps_transfer.py parse_txt_export():324,328 —
  assumes integer (CNT) data: `int(v.strip())` + dtype=np.int16. But
  FileSave.write_data writes '%8.3f' floats whenever time_yspan != 'CNT',
  so running Transmissibility on an MV/VEL/ACC recording crashes with a
  bare ValueError from int('  123.456'). Either parse via float() (and
  drop the int16 cast), or reject/convert non-CNT recordings up front
  with a clear message. (Root cause spans the shared writer's format
  choice — coordinate with vibmshared if the fix changes write_data.)

- OPEN [F8] (2026-07-15): maps_signal.py record_handling() — hour
  rollover off-by-one. On rollover, save_partial_window_data() slices
  the most recent record_second_counter seconds of t_ydata, which at
  that moment already includes the just-completed NEW-hour second
  (insert_new_data extends t_ydata before calling record_handling). So
  the new hour's first second is written into the OLD hour's file, the
  oldest pending old-hour second falls out of the slice, and the new
  file's counter is not initialized to 1 the way the first-time branch
  is (:144 "First second already captured"). ~1 s misfiled/lost at every
  hour boundary. Fix sketch: in the rollover branch, save the partial
  EXCLUDING the current second, then set record_second_counter = 1
  after open_new_record_file().

- OPEN [F9] (2026-07-15): incomplete-second desync after a dropped
  fragment. (shared half FIXED 2026-07-16: drop is now logged; vibmscope
  resync half still OPEN) SerialReader.run() silently drops a captured
  fragment when queue_handler (maxsize 8) is full. (vibmscope half)
  insert_new_data() has no timeout/reset for an incomplete second, so
  the stale fragment_received flags then combine with the NEXT second's
  fragments — one plot/record cycle mixes data from two different
  seconds before flags realign. Mitigation on the vibmscope side:
  detect a new second starting while flags are partially set (e.g.
  fragment 0 / timestamp change) and clear buffer+flags, plus log the
  drop on the shared side.

- OPEN, minor (2026-07-15), grouped — no correctness impact today or
  edge-case-only; batch when touching the relevant file:
  * maps_class.py update_frequency_axes(): hard-codes yFmin=0 but
    compute_transform in dB mode can return negative values; a quiet
    signal yields set_ylim(0, <=0) — inverted/degenerate axis. Only
    reachable with fft_yspan='dB'.
  * maps_transfer.py get_process_info_block():885 reports a power-of-2
    n_fft in "FFT Config", but compute_tf_from_signals() FFTs the full
    raw length — report vs computation disagree for live (non-sim)
    captures. (Sim input is pre-trimmed, so consistent there.)
  * maps_transfer.py:1088 (__main__ only) — `sys, exc =
    create_tf_parameters(...)` shadows the module-level sys import;
    same pattern already fixed in vibmscope.py:84. Latent (nothing uses
    sys afterwards); rename to tf_system for consistency.
  * maps_signal.py ydata_to_unit():392 — local `unit` fetched but never
    used; sensor_factor is cached once in __init__ (stale if the unit
    could ever change at runtime); np.int16(ydata * factor) silently
    wraps on overflow for factors > 1.
  * maps_class.py __main__ self-test block is stale: AppMainFrame(root,
    None, None, None, None, dummy_signal) — constructor takes 9 params;
    Signal() with no handlers also can't survive get_sys_value without
    config init. TypeErrors immediately if run.
  * maps_transfer.py load_npz() never closes the NpzFile — np.load
    keeps the handle open; on Windows this locks the .npz, which
    matters because tf_button/export_button check/skip on existing
    files.
  * maps_class.py reset_button():707 — os._exit(0) skips serial-port
    close/thread cleanup (session is guaranteed off by the guard, but
    the port may still be open).
  * maps_class.py insert_xtick_time_string():224 — tick labels use the
    laptop datetime.now() while data timestamps prefer the remote GSN
    RTC; labels can drift from the data's own time base. Confirm if
    intended before "fixing".
  * maps_transfer.py estimate_system_order():168 — returns
    max(2*peaks, 1): an odd "order 1" floor, inconsistent with the
    2nd-order model it feeds (and its own "2 x peaks" doc). 2 would be
    the coherent minimum.

- Cross-file note (2026-07-15): two findings from this pass live in
  vibmshared and should be copied to the root CLAUDE.md, not tracked
  here: (a) parameters.py:55 WindowParams.windows typo 'barlett' —
  is_valid() accepts the misspelling, rejects correct 'bartlett', and
  scipy get_window('barlett') raises, so selecting it crashes
  SignalProcessor.preprocessing_signal every second (dormant: default
  is 'hann'; label() at :85 spells it correctly — the two lists
  disagree) [FIXED 2026-07-16: 'barlett' -> 'bartlett', see root CLAUDE.md];
  (b) serial_comm.py SerialReader queue-full silent drop —
  the shared half of [F9] above.

## Phase 3 closeout (2026-07-16 — deferred-minors dispositioned)
1. CLOSED (2026-07-16, owner decision): dB-mode FFT axis — FFT dB values are
   always positive at this product's signal levels; the abs() guard already
   prevents axis inversion. No dB-axis rework planned. (Do not re-raise.)
2. FIXED: x-tick labels now follow hdr_handler.system_time (RTC-preferred,
   laptop fallback) — DECIDED 2026-07-16. (maps_class.py
   insert_xtick_time_string())
3. FIXED: ydata_to_unit() per-call factor + int16 saturation (np.clip);
   DECIDED: unit changes permitted in session-OFF only (the rule itself is
   the record). (maps_signal.py)
4. FIXED/REMOVED: close_open_files() deleted (caller-less since [F2]).
   (maps_signal.py)
5. FIXED (2026-07-16): maps_class __main__ self-test — the old testing
   statements were removed on prior suggestion, leaving an empty
   `if __name__ == "__main__":` body (a hard SyntaxError that made the
   module unimportable). Added a `raise SystemExit(...)` statement as the
   block body so the file compiles and, if run directly, prints a clear
   "run vibmscope.py instead" message. Rework into a real harness later.
6. vib_features.py header + boolean cleanup noted (consistency with
   prd_features.py; zero external GLB_ importers — GLB_VALID/GLB_INVALID
   removed).
