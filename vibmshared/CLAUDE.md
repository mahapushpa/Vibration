# vibmshared — Common Source Files

Purpose: Shared code used by all three GSN Node projects (VibMTool, VibMScope,
VibMLogger). Treat as the shared API — changes here can affect every project.

## Structure
- `core/`    — core functions usable across any source file
- `modules/` — module-specific files: CDC/USB, Simulation, GPRS, WiFi, etc.
- `utils/`   — utility functions

## Used by
- `../VibMTool/`
- `../VibMScope/`
- `../VibMLogger/`

## Known issues
- cmd_waiting/cmd_sent_time/last_reply threading gaps in
  modules/cmd_remote.py — see root CLAUDE.md Conventions & Decisions
  (2026-07-14 threading review) for details: unconsumed WAIT/last_reply
  path, FAILED paths not clearing cmd_waiting, and global-flag vs
  per-instance state mismatch.
- Simulator.setup_plot()/update_plot() (modules/simulator.py) call
  matplotlib directly from Thread.run() — unsafe with TkAgg if
  enable_plotting=True is ever passed from GUI-driven code. Currently only
  reachable from the module's own __main__ demo; ConnectionThreadManager
  never enables it. Keep it that way, or move plotting off the thread.

## Review session 2026-07-15 (fixes — see root CLAUDE.md for full detail)
- modules/cmd_remote.py: added missing `import time` (send_command() would
  otherwise NameError on time.time() — CRITICAL); send_command() guards an
  unknown module/param and clears cmd_waiting; rcv_response() guards a
  None/empty response before indexing response[0].
- utils/sys_helpers.py: validate_sys_value() remote-key branch now returns a
  bool (was returning validate_param_value()'s truthy (bool, value) tuple, so
  all remote-key config validation was silently bypassed).
- core/file_save.py: added the missing `safe_log` import.
- core/sys_config.py: repaired sys_reset_to_defaults()/set_sys_value_default()
  (both broken but unused; kept for next-stage use).
- core/common.py: sys_serial_baudrate 112500 -> 115200.
- utils/display_helpers.py: get_display_context() no longer leaks a throwaway
  Tk() root when called with root=None.
- modules/cmd_helpers.py: removed dead param_bytes packing in
  write_module_direct()'s pattern branch (behaviour unchanged).
- core/product_meta.py: an icon/logo rework (a get_logo() PNG for rendering,
  split from the get_icon() .ico) was tried on 2026-07-15 and fully REVERTED at
  the user's request — product_meta.py and the maps_logo.ico asset are back to
  their original state, and there is no maps_logo.png. See root CLAUDE.md
  Conventions for why (letterboxing the wordmark made the title-bar icon less
  visible, not more) before attempting anything here again.