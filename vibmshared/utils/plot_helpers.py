import numpy as np
from matplotlib.ticker import AutoMinorLocator, FormatStrFormatter

#-------------------------------------------------------------------------------
# from plot_helpers import set_clean_axis_ticks_labels
# # Apply to any axis for automacally sets the ticks and labels:
# set_clean_axis_ticks_labels(ax, (min_val, max_val), axis='x', num_ticks=10)
# set_clean_axis_ticks_labels(ax, (min_db, max_db),   axis='y', num_ticks=5)
def set_clean_axis_ticks_labels(ax, data_range, axis = 'y', num_ticks = 5, step_hint = None, num_minor = None):
#-------------------------------------------------------------------------------
    def round_up(val, step):
        result = np.ceil(val / step) * step
        if np.isclose(result, val):
            result += step
        return result

#-------------------------------------------------------------------------------
    def round_down(val, step):
        result = np.floor(val / step) * step
        if np.isclose(result, val):
            result -= step
        return result

#-------------------------------------------------------------------------------
    def compute_step(val_min, val_max, divisions):
        raw_step = (val_max - val_min) / max(divisions, 1)
        base = 10 ** np.floor(np.log10(raw_step))
        for factor in [1, 2, 5, 10]:
            step = base * factor
            if step >= raw_step:
                return step
        return step  # fallback

#-------------------------------------------------------------------------------
    def auto_minor_ticks(range_val):
        if range_val > 50:
            return 5
        elif range_val > 10:
            return 4
        elif range_val > 1:
            return 2
        else:
            return 1

    val_min, val_max = data_range

    # Step size
    step = step_hint if step_hint is not None else compute_step(val_min, val_max, num_ticks)

    if axis == 'y':
        max_val = round_up(val_max, step)
    else:
        max_val = val_max

    min_val = round_down(val_min, step)
    ticks = np.arange(min_val, max_val + step, step)

    # Axis-specific handlers
    if axis == 'x':
        axis_obj = ax.xaxis
        set_lim = ax.set_xlim
        set_ticks = ax.set_xticks
        set_ticklabels = ax.set_xticklabels
        # format_str = '%.0f'                     
        format_str = '%.1f' if step < 1 else '%d'
        
    else:
        axis_obj = ax.yaxis
        set_lim = ax.set_ylim
        set_ticks = ax.set_yticks
        set_ticklabels = ax.set_yticklabels
        format_str = '%.1f' if step < 1 else '%.0f'

    set_lim(min_val, max_val)
    set_ticks(ticks)
    set_ticklabels([format_str % t for t in ticks])
    axis_obj.set_major_formatter(FormatStrFormatter(format_str))

    # Minor ticks
    range_val = max_val - min_val
    if num_minor is None:
        num_minor = auto_minor_ticks(range_val)
    axis_obj.set_minor_locator(AutoMinorLocator(num_minor))

    return {
        'limits': (min_val, max_val),
        'major_ticks': ticks,
        'step': step,
        'minor_ticks': num_minor
    }

