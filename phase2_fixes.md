# Phase 2 — VibMScope, 2026-07-16

All BEFORE blocks are verbatim from the current (post-Phase-1) knowledge-box
copies. Apply per cluster; each cluster is one coherent commit candidate.

Decisions embedded — veto before applying if you disagree:
  (a) [F5] "Clear Setting" moves to Ctrl+L (underline the 'l' in "Clear");
      BOTH Ctrl+C quit bindings in vibmscope.py are deleted. Quit remains on
      Ctrl+Q, the window X button, and SIGINT/SIGTERM. Ctrl+C is left free
      (conventional copy), matching VibMTool's convention.
  (b) [F7] parse_txt_export switches to float() parsing with float32 arrays:
      CNT (integer) recordings parse bit-identically; MV/VEL/ACC recordings
      (written as %8.3f) now work instead of crashing. NPZ files created from
      TXT will store float32 signals instead of int16 (slightly larger).
  (c) reset_button routes through quit_button() instead of os._exit(0), so
      the serial port closes on reset-exit too.
  (d) estimate_system_order minimum returns 2 (was 1) — coherent with the
      2nd-order model it feeds.
  (e) quit_button's old Step 4 close_open_files() call is removed (the new
      Step 0 does the real close); session_button's call is replaced by
      close_current_file(). close_open_files() then has NO remaining callers
      — kept for now with that fact noted in the doc; delete later if agreed.
  (f) One finding is DOWNGRADED, not fixed: the "dB-mode inverted FFT axis"
      minor was wrong in one detail — the abs() in update_frequency_axes
      already prevents axis inversion. Actual behavior: all-negative dB data
      plots off-axis (invisible) rather than crashing. Proper dB-axis support
      (negative y-min) is a design change — documented and deferred, no code
      change in this pack.

================================================================================
CLUSTER A — maps_class.py + vibmscope.py   ([F2] [F5] + minors)
================================================================================

## A1  [F2]  session_button(): save partial data + STOP tokens on session stop

**BEFORE**
```python
            # Stop Recording if Active
            if get_session_flag('record'):
                self.record_button()  # ensure record stops
                set_session_flag('record', False)
                self.signal_handler.close_open_files()
```

**AFTER**
```python
            # Stop Recording if Active
            if get_session_flag('record'):
                self.record_button()  # ensure record stops
                set_session_flag('record', False)
                set_session_flag('prev_record', False)
                # [F2] close_current_file(): saves the pending partial window
                # and writes the STOP_DATE/STOP_TIME tokens (DECIDED
                # 2026-07-16: captured data may be unrepeatable — never
                # discard on stop). The old close_open_files() saved nothing
                # and left literal "{ STOP_DATE }" placeholders, which then
                # crashed parse_txt_export() on this file. Same sequence
                # tf_button Case 1 already uses.
                self.signal_handler.close_current_file()
```

## A2  [F2]  quit_button(): stop recording properly; remove the no-op Step 4

Edit 1 — insert Step 0 (BEFORE block is the function's opening lines):
```python
        reset_status_bar()
        connection = get_session_flag('connection')
        ser_port   = getattr(self.con_handler, 'serial_port', None)
        
        # Step 1: Stop Session First, if it is on
```
**AFTER**
```python
        reset_status_bar()
        connection = get_session_flag('connection')
        ser_port   = getattr(self.con_handler, 'serial_port', None)

        # Step 0: Stop recording first (if active) and close the file WITH
        # pending partial data + STOP tokens ([F2], DECIDED 2026-07-16).
        # Previously quit never stopped recording at all and Step 4's
        # close_open_files() saved nothing.
        if get_session_flag('record'):
            self.record_button()
            set_session_flag('record', False)
            set_session_flag('prev_record', False)
            self.signal_handler.close_current_file()

        # Step 1: Stop Session First, if it is on
```

Edit 2 — Step 4:
**BEFORE**
```python
        # Step 4: Close the open files, while quting the program
        self.signal_handler.close_open_files()
        
        # Step 5: Quit the Tkinter mainloop (without destroying Tk explicitly)
```
**AFTER**
```python
        # Step 4: (removed) file closing now happens in Step 0 via
        # close_current_file() — the old close_open_files() call here wrote
        # nothing and only printed a duplicate "Closed file" message ([F2]).

        # Step 5: Quit the Tkinter mainloop (without destroying Tk explicitly)
```

Verify [F2]: start session -> start recording -> wait ~7 s (one full window +
partial) -> Session Off. Open the record file: data rows beyond the last full
window are present, and the header shows real Stop Date/Time (no "{ STOP_DATE }"
tokens). Repeat quitting via Quit System and via window X while recording.
Then run Transmissibility on that file — parses cleanly.

## A3  [F5]  Clear Setting -> Ctrl+L; delete the Ctrl+C quit bindings

maps_class.py button_definitions:
**BEFORE**
```python
            ("Clear Setting",    0, self.reset_button,   'c', False),  # Ctrl+c
```
**AFTER**
```python
            ("Clear Setting",    1, self.reset_button,   'l', False),  # Ctrl+L ('c' freed — was double-bound with app quit [F5])
```

vibmscope.py:
**BEFORE**
```python
        # Bind Ctrl+C/c in GUI to close the window
        self.root.bind_all("<Control-c>", lambda e: self.stop())
        self.root.bind_all("<Control-C>", lambda e: self.stop())
```
**AFTER**
```python
        # [F5] Ctrl+C bindings removed: they double-fired with the toolbar
        # "Clear Setting" shortcut (root and 'all' bindtags both ran — reset
        # dialog AND app shutdown from one keypress). Quit remains on Ctrl+Q,
        # the window X, and SIGINT/SIGTERM; Ctrl+C is left free for
        # conventional copy, matching VibMTool.
```

Verify: Ctrl+L opens the reset-confirm dialog (and nothing else); Ctrl+C does
nothing app-level; Ctrl+Q still quits; the button label underlines the 'l'.

## A4  (minor)  reset_button(): clean exit instead of os._exit

**BEFORE**
```python
            self.root_window.destroy()  # clean Tk exit
            os._exit(0)  # hard exit to ensure full shutdown
```
**AFTER**
```python
            # Close port/thread and quit the mainloop properly — os._exit()
            # skipped serial-port cleanup (minor, 2026-07-16). Session is
            # guaranteed off here (guard above), so quit_button's Step 0/1
            # are no-ops and it just closes the port and quits.
            self.quit_button()
            self.root_window.destroy()  # clean Tk exit
```

Verify: with port connected and session OFF, Clear Setting -> confirm: console
shows "Serial port closed." before exit; app terminates normally.

## A5  (minor)  annotate the stale __main__ self-test

**BEFORE**
```python
if __name__ == "__main__":
    logging.basicConfig(level = logging.DEBUG)
    root = tk.Tk()
```
**AFTER**
```python
if __name__ == "__main__":
    # NOTE (2026-07-16): stale self-test — AppMainFrame now takes 9 args and
    # Signal() needs initialized handlers/config; this block TypeErrors if
    # run. Kept as a placeholder; rework or delete when a real harness exists.
    logging.basicConfig(level = logging.DEBUG)
    root = tk.Tk()
```

================================================================================
CLUSTER B — maps_signal.py   ([F8] [F9] + minor)
================================================================================

## B1  [F8]  hour-rollover off-by-one

Edit 1 — record_handling() rollover branch:
**BEFORE**
```python
        elif self.record_start_hour != current_hour:  # Hour Rollover
            self.close_current_file()
            self.open_new_record_file(file_str, date_str, time_str, current_hour)
```
**AFTER**
```python
        elif self.record_start_hour != current_hour:  # Hour Rollover
            # [F8] The just-completed second already sits in t_ydata and
            # belongs to the NEW hour: close the old file EXCLUDING it, then
            # count it as the new file's first second — mirroring the
            # first-time branch above. Previously that second was written
            # into the OLD hour's file while the oldest pending old-hour
            # second fell out of the partial slice (~1 s misfiled per hour).
            self.close_current_file(exclude_latest_second = True)
            self.open_new_record_file(file_str, date_str, time_str, current_hour)
            self.record_second_counter = 1  # current (new-hour) second already captured
```

Edit 2 — close_current_file() signature passthrough:
**BEFORE**
```python
    def close_current_file(self):
        """Dummy closer now that we use 'with open()' for all writes. It is just message function now"""
        if self.record_filename:
            self.save_partial_window_data()
```
**AFTER**
```python
    def close_current_file(self, exclude_latest_second = False):
        """Save pending partial data (optionally excluding the newest second —
        hour-rollover path, [F8]), write the STOP tokens, and log the close."""
        if self.record_filename:
            self.save_partial_window_data(exclude_latest_second)
```

Edit 3 — save_partial_window_data():
**BEFORE**
```python
    def save_partial_window_data(self):
        if self.record_second_counter > 0:
            partial_samples = get_sys_value('adc_srate') * self.record_second_counter
            trimmed_data = [np.array(ch)[-partial_samples:] for ch in self.t_ydata]
```
**AFTER**
```python
    def save_partial_window_data(self, exclude_latest_second = False):
        if self.record_second_counter > 0:
            srate = get_sys_value('adc_srate')
            partial_samples = srate * self.record_second_counter
            if exclude_latest_second:
                # [F8] hour rollover: the newest second in t_ydata belongs to
                # the NEW hour — write only the pending old-hour seconds
                # (the `counter` seconds immediately BEFORE the newest one).
                trimmed_data = [np.array(ch)[-(partial_samples + srate):-srate] for ch in self.t_ydata]
            else:
                trimmed_data = [np.array(ch)[-partial_samples:] for ch in self.t_ydata]
```

(Counter bookkeeping stays consistent: at rollover, record_second_counter
holds only the pending old-hour seconds — it hasn't been incremented for the
new-hour second — so counter+1 <= window span and the slice is always in
range. save_partial resets it to 0 as before; the rollover branch then sets
it to 1 for the new file.)

Verify [F8] (bench trick): temporarily make extract_hour() return the MINUTE
(`int(time_str.split(":")[1])`) so "hourly" rollover happens every minute;
record across two boundaries; check per-file sample counts: each file's rows =
(seconds it owned) x srate with no duplicated/missing second at the boundary;
REVERT the extract_hour change afterwards.

## B2  [F9]  dropped-fragment resync guard (vibmscope half)

**BEFORE**
```python
        self.fragment_buffer[ch, start:end] = ydata[:self.samples_in_fragment] # avoid extra
        # safe_log(None, f"[Insert] CH = {ch}, FRAG = {frag_no}, start = {start}, end = {end}", tag = "debug", do_print = True)

        self.fragment_received[ch, frag_no] = True
```
**AFTER**
```python
        # [F9] Dropped-fragment resync: if this (ch, fragment) slot is already
        # marked received but the second never completed, at least one other
        # fragment was lost upstream (queue-full drop — see the serial_comm
        # WARN added in Phase 0). Discard the stale, incomplete second and
        # start re-assembling from this fragment, instead of silently mixing
        # two different seconds in one plot/record cycle.
        if self.fragment_received[ch, frag_no]:
            safe_log(None, "[Signal] Incomplete second discarded (dropped fragment detected) — resyncing",
                     tag = "warning", do_print = True)
            self.fragment_received[:, :] = False

        self.fragment_buffer[ch, start:end] = ydata[:self.samples_in_fragment] # avoid extra
        # safe_log(None, f"[Insert] CH = {ch}, FRAG = {frag_no}, start = {start}, end = {end}", tag = "debug", do_print = True)

        self.fragment_received[ch, frag_no] = True
```

(A duplicated fragment triggers the same resync — acceptable: either anomaly
means the current second's assembly is unreliable, and recovery is one second
in both cases.)

Verify [F9]: temporarily set the queue maxsize to 2 (serial_comm) to force
drops; expect paired logs — the Phase-0 "[WARN] GUI queue full" followed by
"[Signal] Incomplete second discarded ... resyncing" — and the plot recovering
each time instead of showing one garbled second. Revert the maxsize.

## B3  (minor)  ydata_to_unit(): remove dead local

**BEFORE**
```python
        unit = get_sys_value('time_yspan')
        return (np.int16(ydata * self.sensor_factor))
```
**AFTER**
```python
        # (dead local 'unit' removed 2026-07-16; sensor_factor is cached at
        # __init__ and np.int16 can wrap for factors > 1 — both still
        # documented as open minors, behavior unchanged here)
        return (np.int16(ydata * self.sensor_factor))
```

================================================================================
CLUSTER C — maps_transfer.py   ([F3] [F4] [F6] [F7] + minors)
================================================================================

## C1  [F3]  PDF metadata labels un-crossed

**BEFORE**
```python
        for label, meta in [("Data Capture Information", data_info_block),
                            ("System Model Information", input_info_block),
                            ("Input Signal Information", tf_info_block),
                            ("Processing Information", process_info_block)]:
```
**AFTER**
```python
        # [F3] labels were crossed vs save_to_text_csv(): input_info_block IS
        # "Input Signal Information" (source/type/freq), tf_info_block IS
        # "System Model Information" (order/damping/natural freq).
        for label, meta in [("Data Capture Information", data_info_block),
                            ("Input Signal Information", input_info_block),
                            ("System Model Information", tf_info_block),
                            ("Processing Information", process_info_block)]:
```

## C2  [F4]  post_keys "Captured Duration" -> "Duration"

**BEFORE**
```python
    post_keys = [
        "Captured Duration",
        "Ref Channel"
    ]
```
**AFTER**
```python
    post_keys = [
        "Duration",       # [F4] producer key is "Duration" (get_data_info_block
                          # :842) — "Captured Duration" never matched, so the
                          # duration was silently dropped from PDF/TXT/CSV
        "Ref Channel"
    ]
```

(Fix is on the consumer side deliberately: the npz-persisted data_info_block
keeps its existing "Duration" key — old saved captures render correctly.)

## C3  [F6]  double dB->linear conversion in the fit path

**BEFORE**
```python
        if self.use_db:
            tf_mag = 10 ** (tf_mag / 20)

        try:
            order = self.estimate_system_order(freqs, tf_mag)
```
**AFTER**
```python
        try:
            # [F6] estimate_system_order() applies its OWN dB->linear
            # conversion (same self.use_db flag) — pass it the raw values and
            # convert only afterwards, for the curve fit. Previously both
            # converted, so in dB mode the order estimator saw
            # 10**(linear/20): near-flat data, wrong peak count.
            order = self.estimate_system_order(freqs, tf_mag)

            if self.use_db:
                tf_mag = 10 ** (tf_mag / 20)
```

## C4  [F7]  parse_txt_export: accept non-CNT (float) recordings

**BEFORE**
```python
        for line in lines[data_start_idx:]:
            line = line.strip()
            if line:
                values = [int(v.strip()) for v in line.split(",")]
                data_lines.append(values)

        # Full array: shape = (n_samples, n_channels)
        full_data = np.array(data_lines, dtype = np.int16)
```
**AFTER**
```python
        for line in lines[data_start_idx:]:
            line = line.strip()
            if line:
                # [F7] float(): recordings made with time_yspan != 'CNT' are
                # written as '%8.3f' floats — int() crashed on them with a
                # bare ValueError. CNT files parse identically via float().
                values = [float(v.strip()) for v in line.split(",")]
                data_lines.append(values)

        # Full array: shape = (n_samples, n_channels). float32 carries int16
        # CNT values exactly and holds the 3-decimal unit-converted values.
        full_data = np.array(data_lines, dtype = np.float32)
```

Verify [F3/F4/F6/F7]: record a short session in a non-CNT unit, stop, run
Transmissibility — parses without error; PDF report shows source/type/freq
under "Input Signal Information", order/damping under "System Model
Information", and a "Duration" row present; TXT/CSV exports show the same
Duration row. For [F6], set use_yscale_db True on a sim run — estimated order
matches the non-dB run of the same data.

## C5  (minor)  load_npz(): release the file handle (whole-method replace)

**BEFORE**
```python
    def load_npz(self, filename_npz):
        """Load a saved .npz capture, returning raw blocks + signals.
        Missing user_info_block degrades to a plain string instead of raising."""
        data = np.load(filename_npz, allow_pickle = True)

        timestamp = data.get('timestamp')
        if 'user_info_block' in data:
            user_info_block = data['user_info_block'].item()
        else:
            user_info_block = "User Information: N/A"

        return {
            'timestamp':            timestamp,
            'user_info_block':      user_info_block,
            'data_info_block':      data['data_info_block'].item(),
            'input_info_block':     data['input_info_block'].item(),
            'tf_info_block':        data['tf_info_block'].item(),
            'process_info_block':   data['process_info_block'].item(),
            'analysis_info_block':  data['analysis_info_block'].item(),
            'input_signals':        data['input_signals'],
            'output_signals':       data['output_signals'],
        }
```
**AFTER**
```python
    def load_npz(self, filename_npz):
        """Load a saved .npz capture, returning raw blocks + signals.
        Missing user_info_block degrades to a plain string instead of raising.
        with-block: np.load keeps the NpzFile handle open otherwise, which
        locks the .npz on Windows (matters for tf/export existing-file checks)."""
        with np.load(filename_npz, allow_pickle = True) as data:

            timestamp = data.get('timestamp')
            if 'user_info_block' in data:
                user_info_block = data['user_info_block'].item()
            else:
                user_info_block = "User Information: N/A"

            return {
                'timestamp':            timestamp,
                'user_info_block':      user_info_block,
                'data_info_block':      data['data_info_block'].item(),
                'input_info_block':     data['input_info_block'].item(),
                'tf_info_block':        data['tf_info_block'].item(),
                'process_info_block':   data['process_info_block'].item(),
                'analysis_info_block':  data['analysis_info_block'].item(),
                'input_signals':        data['input_signals'],
                'output_signals':       data['output_signals'],
            }
```
(All arrays are fully materialized inside the with-block before return.)

## C6  (minor)  get_process_info_block(): report the ACTUAL FFT length

**BEFORE**
```python
        raw_len = len(self.input_signals)
        n_fft   = 2 ** int(np.floor(np.log2(raw_len)))
```
**AFTER**
```python
        raw_len = len(self.input_signals)
        # Report the ACTUAL FFT length: compute_tf_from_signals() uses the
        # full raw length, not a power-of-2 trim (sim data is pre-trimmed so
        # both agreed there; live TXT captures previously misreported).
        n_fft   = raw_len
```

## C7  (minor)  estimate_system_order(): coherent minimum

Edit 1 — docstring:
**BEFORE**
```python
            estimated_order (int) = 2 x number of valid peaks (minimum 1)
```
**AFTER**
```python
            estimated_order (int) = 2 x number of valid peaks (minimum 2)
```

Edit 2 — return:
**BEFORE**
```python
        num_resonances = len(peaks)
        return max(2 * num_resonances, 1)  # Ensure minimum order = 1
```
**AFTER**
```python
        num_resonances = len(peaks)
        return max(2 * num_resonances, 2)  # minimum order 2 — matches the 2nd-order model this feeds
```

## C8  (minor)  __main__: same sys-shadowing pattern fixed elsewhere

**BEFORE**
```python
    sys, exc = create_tf_parameters(simulation = get_sys_value("simulation_mode"), n_receivers = n_receivers)

    tf  = TFProcessor(system = sys, excitation = exc, display_config = display_config)
    sim = SimulatorTF(system = sys, excitation = exc, tf = tf)
```
**AFTER**
```python
    tf_system, exc = create_tf_parameters(simulation = get_sys_value("simulation_mode"), n_receivers = n_receivers)

    tf  = TFProcessor(system = tf_system, excitation = exc, display_config = display_config)
    sim = SimulatorTF(system = tf_system, excitation = exc, tf = tf)
```

================================================================================
CLUSTER D — documentation (VibMScope/CLAUDE.md + root)
================================================================================

1. Flips to FIXED (2026-07-16): [F2] [F3] [F4] [F5] [F6] [F7] [F8]; [F9] is
   now FULLY fixed (Phase-0 shared logging half + this resync half) — collapse
   the split annotation into one FIXED entry covering both halves.
2. Minor-block updates: mark fixed — reset_button os._exit, ydata_to_unit dead
   local, load_npz handle, n_fft report, order minimum, __main__ shadowing,
   and note the annotated (not reworked) __main__ self-test.
3. CORRECTION to the dB-ylim minor (keep OPEN, reworded): the abs() in
   update_frequency_axes prevents axis inversion — the original "inverted/
   degenerate axis" claim was wrong in that detail. Actual behavior:
   all-negative dB data plots off-axis (invisible). Proper dB-axis support
   (negative y-min, dB-aware ceiling) is a design change — deferred.
4. Still OPEN, unchanged: insert_xtick_time_string laptop-clock tick labels
   (confirm design intent before changing); sensor_factor init-time caching +
   np.int16 overflow-wrap in ydata_to_unit (behavioral change — decide with a
   unit-handling rework).
5. New note: close_open_files() now has ZERO callers after [F2] (both former
   call sites replaced by close_current_file()); kept for now — delete in a
   future cleanup if agreed.
6. [F5] decision record for Conventions: Ctrl+C is reserved for conventional
   copy in BOTH tools (VibMTool precedent); destructive/system actions must
   not bind it. Clear Setting = Ctrl+L.
7. Root CLAUDE.md: no shared files touched in this phase — note that Phase 2
   completes the 2026-07-16 review backlog for VibMScope except the two
   deferred minors in (3)/(4).

================================================================================
Claude Code prompt (suggested)
================================================================================
```
Read phase2_fixes.md in the repo root. Apply clusters A, B, C, D in order.
Every BEFORE block must match the target file verbatim; if a block does not
match, STOP and report the mismatch instead of improvising. C5 is a
whole-method replacement; everything else is a targeted edit. Make no other
changes: no reformatting, no refactoring, no extra fixes. Do not run git
commands. When done, list every file touched with a one-line summary per
change, and flag any BEFORE block you could not match.
```

Test notes (beyond per-fix verifies):
- [F8]'s bench trick (minute-based rollover) and [F9]'s queue-shrink are
  TEMPORARY edits — revert both before committing.
- Regression sweep after the pack: sim session -> record -> TF -> PDF + TXT +
  CSV export -> npz reload -> TF again; then the same on hardware if handy.

After this phase: re-sync the knowledge box (watch that vibmtool.py stays in
this time), and the 2026-07-16 review backlog is closed except the explicitly
deferred items. Remaining known-open work from the original docs (pre-review):
event-capture wiring in maps_signal.py — item [B]'s tri-valued return decision
is already documented for when that driver is written.
