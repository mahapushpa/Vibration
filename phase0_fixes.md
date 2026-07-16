# Phase 0 — zero-risk fixes (both projects), 2026-07-16

Five independent, low-risk changes. Each section: exact BEFORE/AFTER text
(verbatim from the current knowledge-box copies), why, how to verify, and the
CLAUDE.md line to flip once applied. The two vibmshared changes (P0-2, P0-5)
follow the repo convention: cross-project call-site check is recorded inline.

---

## P0-1  [F1]  maps_signal.py (~line 479) — numpy truthiness crash on timeout partial return

**BEFORE**
```python
                        print(f"[WARNING] Timeout reached, returning partial buffer: {len(data) if data else 0} sample words")
```

**AFTER**
```python
                        print(f"[WARNING] Timeout reached, returning partial buffer: {len(data) if data is not None else 0} sample words")
```

Why: `data` is a numpy array here; truth-testing a multi-element array raises
ValueError inside the f-string, jumps to the outer except, logs the misleading
"Communication Lost from Device", and returns None — discarding the salvaged
partial buffer on every real timeout.

Verify: force a timeout with >1 sample word buffered (unplug mid-fragment, or
sim with a stalled sender). Expect the WARNING line with a correct count and
partial data returned; no "Communication Lost" message.

Doc flip (VibMScope CLAUDE.md): change `OPEN [F1]` to
`FIXED (2026-07-16) [F1]: ... Fixed: 'if data' -> 'if data is not None'.`

---

## P0-2  (shared) parameters.py:55 — 'barlett' typo in WindowParams.windows

**BEFORE**
```python
    windows = ['rect', 'hann', 'hamming', 'blackman', 'barlett']
```

**AFTER**
```python
    windows = ['rect', 'hann', 'hamming', 'blackman', 'bartlett']
```

Why: `is_valid()` accepted the misspelling and rejected the correct
'bartlett'; scipy `get_window('barlett')` raises, so selecting it crashed
`SignalProcessor.preprocessing_signal` every second. `label()` at :85 already
spells it correctly — the two lists now agree.

Cross-project check (repo convention for vibmshared edits): WindowParams is
consumed by VibMScope's SignalProcessor (via get_sys_value('window')
validation); VibMTool never reads the 'window' key — no VibMTool call sites,
no regression risk there.

Legacy-config note: a user sys_config.ini that already stored 'barlett' will
now FAIL is_valid and fall through to sys_config's invalid-value handling
(default 'hann') instead of crashing scipy at runtime — strictly an
improvement; no migration shim added.

Verify: select 'bartlett' from the window list (or set it in sys_config.ini);
FFT plot updates without the per-second "[EXCEPTION] Plot update failed".

Doc flip: root CLAUDE.md (shared) — new
`FIXED (2026-07-16): parameters.py:55 WindowParams 'barlett' -> 'bartlett' ...`
and remove/annotate the cross-file note item in VibMScope's draft block.

---

## P0-3  [T5]  prd_gui_setup.py SummaryDialog.__init__ (~line 1038) — displayed_serials init

**BEFORE**
```python
        self.metadata_hdr = []
        self.client_info = {}
        self.export_file = None
        self.start()
```

**AFTER**
```python
        self.metadata_hdr = []
        self.client_info = {}
        self.export_file = None
        self.displayed_serials = set()   # exists even if load_master_file() fails
        self.start()
```

Why: `displayed_serials` was first assigned deep inside load_master_file()'s
try; a master that fails to parse left the window open with live export
buttons whose first line (`if not self.displayed_serials`) raised an uncaught
AttributeError. With the init, exports correctly report "No data to export".

Verify: point Summary at a deliberately corrupted master_*.ini, then click
Export Text — expect the "No data to export" warning box, no traceback.

Doc flip (VibMTool CLAUDE.md): `OPEN [T5]` ->
`FIXED (2026-07-16) [T5]: ... initialized in __init__.`

---

## P0-4  [T8]  vibmtool.py MainApp.stop() (~line 110) — close serial port on all exit paths

**BEFORE**
```python
    def stop(self, *args):
        """Gracefully exit the application."""
        self.running = False

        # Just quit, don't destroy or sys.exit()
        print("Application closed successfully.")
        logging.info("Application closed successfully.")
        self.root.quit()  # Quit Tkinter's main loop and exit naturally
```

**AFTER**
```python
    def stop(self, *args):
        """Gracefully exit the application."""
        self.running = False

        # Route through quit_button() so the serial port is closed on ALL
        # exit paths (window X, SIGINT/SIGTERM), not just Ctrl+Q — same
        # pattern as VibMScope's stop(). quit_button() closes the port,
        # quits the mainloop, and prints/logs "Application closed
        # successfully." itself.
        self.main_frame.buttons.quit_button()
```

Why: previously only Ctrl+Q (quit_button) closed the port; window-X and
signal paths left it open until process teardown. Safe because the
SIGINT/SIGTERM handlers and the WM_DELETE_WINDOW protocol are all registered
AFTER self.main_frame is constructed, so main_frame.buttons always exists
when stop() can fire. quit_button()'s port close is already wrapped in
try/except, and parent_frame.quit() ends the same mainloop root.quit() did.

Verify: connect on real hardware (or check with a port monitor), close via
the window X — expect "Serial port closed." on the console, then the closed
message; port handle released immediately.

Doc flip (VibMTool CLAUDE.md): `OPEN [T8]` ->
`FIXED (2026-07-16) [T8]: stop() now routes through quit_button().`

---

## P0-5  (shared, [F9] logging half)  serial_comm.py SerialReader.run() (~line 102) — log dropped fragments

**BEFORE**
```python
                if self.serial_port.inWaiting() > 0:
                    data = self.signal_handler.data_capture(self.serial_port)
                    if data is not None and len(data) > 0 and not self.queue_handler.full():
                        self.queue_handler.put(data)
```

**AFTER**
```python
                if self.serial_port.inWaiting() > 0:
                    data = self.signal_handler.data_capture(self.serial_port)
                    if data is not None and len(data) > 0:
                        if not self.queue_handler.full():
                            self.queue_handler.put(data)
                        else:
                            # Fragment silently vanishing here is the root of the
                            # one-second plot/record desync (VibMScope CLAUDE.md
                            # [F9]) — at minimum make the drop visible. The
                            # consumer-side resync guard is a separate, later fix.
                            safe_log(None, "[WARN] GUI queue full — fragment dropped; "
                                           "plot/record may desync for ~1s",
                                           tag = "warn", do_print = True)
```

Why: a full queue (maxsize 8, drained max 4 per 100 ms tick) silently dropped
a whole fragment; downstream, insert_new_data's stale fragment_received flags
then mix two different seconds for one cycle. This change only makes the drop
observable — the vibmscope-side resync (clear buffer+flags when a new second
starts over partially-set flags) stays OPEN as [F9]'s remaining half.

Cross-project check: SerialReader is constructed only by
ConnectionThreadManager.start(), used only by VibMScope (VibMTool is
single-threaded, no SerialReader usage — confirmed in VibMTool CLAUDE.md
"Uses from vibmshared"). safe_log is already imported and used with
log_handler=None in this file's except block, same call shape.

Verify: temporarily shrink the queue maxsize (or raise fragments/sec in sim)
until saturation; expect the WARN line instead of silent loss.

Doc flip (VibMScope CLAUDE.md [F9]): keep OPEN but annotate:
`(shared half FIXED 2026-07-16: drop is now logged; vibmscope resync half
still OPEN)` — and mirror the shared-half note in root CLAUDE.md.

---

## Decision records (paste into docs alongside the flips)

Root or project CLAUDE.md "Conventions & Decisions":

```
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
```

## Apply order & sync

1. Apply P0-1..P0-5 in Claude Code (any order — fully independent).
2. Run the five verifications (P0-2 and P0-5 are the vibmshared ones — their
   cross-project checks are recorded above per repo convention).
3. Flip the five doc entries + paste the two decision records.
4. Re-sync the knowledge box once, after the whole phase.

Next after this: Phase 1 (VibMTool to completion), starting with [T1] using
the merge-preserving design above, then [T2].
