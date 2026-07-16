"""
display_context.py

This module provides DPI-aware font and layout helpers for use in both
Tkinter-based GUIs and matplotlib plots.

Functions:
    - get_display_context: Gather screen and DPI information.
    - get_fontsize: Compute a scaled font size from a base point size.
    - font_ui_tk: Generate a Tkinter-compatible font tuple, DPI-scaled.
    - font_ui_mpl: Generate a matplotlib font dictionary, DPI-scaled.
    - scale_box_fontsize: Scale text box font size relative to screen height.

Designed for environments with display scaling (Windows, Linux, macOS).

Usage:
    from display_context import get_display_context, font_ui_tk, font_ui_mpl

Usage Examples:
    ctx = get_display_context()
    label.config(font=font_ui_tk(11, ctx, bold=True))
    ax.set_title("Secondary", **font_ui_mpl(11, ctx, bold=True))
"""

import logging
import platform

#-------------------------------------------------------------------------------
def set_dpi_awareness():
    """
    Enables DPI awareness across platforms for consistent rendering.

    - On Windows:
        * Sets per-monitor DPI awareness (Level 2)
        * Optionally applies Tkinter scaling fallback via tk_root
    - On Linux/macOS: no action needed
    """
    import sys

    if sys.platform == "win32":
        import ctypes
        try:
            # from ctypes import windll
            try: # >= win 8.1
                # 1 = Primary Monitor
                # 2 = Per-monitor DPI aware (best for multi-monitor setups)
                ctypes.windll.shcore.SetProcessDpiAwareness(0) # Reset to clean system DPI context, it must
                ctypes.windll.shcore.SetProcessDpiAwareness(1) # Apply desired DPI behavior (primary monitor)
            except: # win 8.0 or less
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception as e:
            print(f"[WARN] Could not set DPI awareness on Windows: {e}")

#-------------------------------------------------------------------------------
def get_display_dpi():
    """
    Detect display scaling factor.

    Returns:
        float: Scaling factor (e.g., 1.5 for 150%). Defaults to 1.0 on non-Windows.
    """
    try:
        if platform.system() == 'Windows':
            # Set process DPI awareness (if not already done)
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # DPI awareness: system aware
            user32 = ctypes.windll.user32
            dc = user32.GetDC(0)
            LOGPIXELSX = 88
            dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, LOGPIXELSX)
            user32.ReleaseDC(0, dc)
            return dpi
        else:
            return 96
    except Exception:
        return 96

#-------------------------------------------------------------------------------
def get_display_context(root = None, use_usable_area = True):
    """
    Get window dimensions, DPI and scaling.

    Parameters:
    - use_usable_area (bool): If True, uses visible screen area (excludes taskbars).
    - scale_fonts (bool): Whether to include font scaling factor.

    Returns:
        dict:
            - 'dpi': float
			- 'scaling': float
            - 'screen_width_in': float
            - 'screen_height_in': float
            - 'screen_width_pixel': int
            - 'screen_height_pixel': int
    # On Windows, usable area excludes taskbars; on Linux/macOS, effect may vary

    Example:
        ctx = get_display_context()
    """
    created_root = False
    if root is None:
        import tkinter as tk
        root = tk.Tk()
        created_root = True

        root.withdraw()
        root.update_idletasks()
        root.state('zoomed')
        root.update()

    width_px = root.winfo_width()   if use_usable_area else root.winfo_screenwidth()
    height_px = root.winfo_height() if use_usable_area else root.winfo_screenheight()

    try:
      dpi = root.winfo_fpixels('1i')
    except:
      dpi = 96

    # Destroy only the throwaway root we created here — never a caller's root.
    if created_root:
        root.destroy()

    width_in  = width_px / dpi
    height_in = height_px / dpi

    dpi = get_display_dpi()

    return {
        'dpi': dpi,
        'scaling': dpi/96,
        'width_pixel' : width_in  * dpi,
        'height_pixel': height_in * dpi,
        'width_in' : width_in,
        'height_in': height_in,
    }

#-------------------------------------------------------------------------------
def get_fontsize(base_pt, ctx = None, for_screen = True):
    dpi = ctx.get("dpi", 96) if ctx else 96
    if ctx is None:
        logging.warning("Display context not provided; using default DPI = 96.")
    return int(round(base_pt * (dpi / 96))) if for_screen else base_pt

def get_scaled_font(size_pt, ctx=None, ui='tk'):
    """
    Return a DPI-scaled font string or dict for Tkinter or Matplotlib.

    Parameters:
        size_pt (int or float): Base point size (e.g., 10, 12, etc.)
        ctx (dict): Display context dictionary from `get_display_context()`
        ui (str): 'tk' for Tkinter font string, 'mpl' for Matplotlib font dict

    Returns:
        str | dict: Tkinter font as "Arial {size}" or Matplotlib font dict
    Uses or Example:
    For Tkinter Label - 
    ctx = get_display_context()
    label = tk.Label(parent, text="Status", font=get_scaled_font(10, ctx, ui='tk'))
    For Matplotlib Axis - 
    ctx = get_display_context()
    ax.set_title("TF Plot", fontdict=get_scaled_font(14, ctx, ui='mpl'))

    """
    dpi = ctx.get("dpi", 96) if ctx else 96
    scaled_size = int(round(size_pt * (dpi / 96)))

    if ui == 'tk':
        return f"Arial {scaled_size}"
    elif ui == 'mpl':
        return {"family": "Arial", "size": scaled_size}
    else:
        raise ValueError(f"Unknown UI type: {ui}. Use 'tk' or 'mpl'.")

#-------------------------------------------------------------------------------
def font_ui_tk(size_pt, ctx, font_name = "Segoe UI", bold = False):
    """
    Return a DPI-scaled Tkinter-compatible font tuple.

    Parameters:
    - size_pt (float): base font size in points
    - ctx (dict): display context, must include 'dpi'
    - font_name (str): font family name (e.g., "Segoe UI")
    - bold (bool): whether the font is bold

    Returns:
    - tuple: (family: str, size: int, weight: str) suitable for Tkinter widgets
    Example:
        label.config(font=font_ui_tk(11, ctx, bold=True))
    """    
    size = int(round(get_fontsize(size_pt, ctx)))
    weight = "bold" if bold else "normal"
    return (font_name, size, weight)

#-------------------------------------------------------------------------------
def font_ui_mpl(size_pt, ctx, font_name = "Segoe UI", bold = False):
    """
    Matplotlib-compatible font dict, scaled for DPI.
    Returns:
        dict: {fontsize: int, fontweight: str, family: str}
    Example:
        ax.set_title("Secondary", **font_ui_mpl(11, ctx, bold=True))
    """
    return {
        "fontsize": int(round(get_fontsize(size_pt, ctx))),
        "fontweight": "bold" if bold else "normal",
        "family": font_name
    }

#-------------------------------------------------------------------------------
def estimate_textbox_height_rel_ax(block, fontsize_pt, fig_height_in, fig_dpi, ax):
    """
    Box Height Calculation Example (for dynamic layout in draw loop)

    Includes:
    - Line count
    - Padding from boxstyle
    - Border stroke thickness (approx. 2px)

    This is used to decrement y_cursor accurately in axes-relative units.
    """
    # Text structure
    lines = block.count('\n') + 1
    pad_fraction = 0.2
    stroke_px = 6 # typical stroke height of border

    total_pt = lines * fontsize_pt + 2 * pad_fraction * fontsize_pt
    total_in = (total_pt + stroke_px)/72.0
    total_px = total_in * fig_dpi * get_display_dpi()/96  # scale factor

    fig_height_px = fig_height_in * fig_dpi
    ax_frac = ax.get_position().height
    ax_height_px = fig_height_px * ax_frac
    # Convert to relative axes coordinate height
    ratio = total_px / ax_height_px
    return ratio  # axes-relative

#-------------------------------------------------------------------------------
def scale_box_fontsize(fig, ctx, max_size = 11.0, min_size = 6.0):
    """
    Dynamically scale font size for text boxes based on figure height vs screen height.

    Parameters:
        fig (matplotlib.figure.Figure): target figure
        ctx (dict): context with 'screen_height_pixel'
        max_size (float): upper limit font size
        min_size (float): lower limit font size

    Returns:
        float: scaled font size in pt
    Example:
        size = scale_box_fontsize(fig, ctx)
    """
    scaling = ctx.get('scaling')
    return max(min_size, min(max_size, scaling * max_size))
