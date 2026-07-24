import logging
from vibmshared.core.sys_config      import get_sys_value, set_sys_value
from vibmshared.utils.utils_helpers  import validate_sample_rate, play_audio, safe_log
from vibmshared.modules.cmd_helpers  import read_single_param_direct, write_single_param_direct

#-------------------------------------------------------------------------------
def sync_to_remote(cmd_handler):
    """Initializes and synchronizes system parameters with remote device."""
    logging.info("Synchronizing with Remote...")

    # --- Sample Rate ---
    is_valid, sample_rate = read_single_param_direct(cmd_handler, None, 'ADC', 'SRATE')
    if not is_valid:
        safe_log(None, f"Sample rate is out of bounds, got {sample_rate}", tag = "error", do_print = True)
        raise ValueError(f"Sample rate is out of bounds, got {sample_rate}")

    already_pow2, corrected_rate = validate_sample_rate(sample_rate)
    if not already_pow2:
        safe_log(None, f"Sample rate is not 2^n, setting {corrected_rate}", tag = "warning", do_print = True)
        success = write_single_param_direct(cmd_handler, None, 'ADC', 'SRATE', corrected_rate)

        if not success:
            raise ValueError("Failed to set sampling rate at remote")
        sample_rate = corrected_rate

    if get_sys_value('adc_srate') != sample_rate:
        set_sys_value('adc_srate', sample_rate)

    # --- Channels ---
    is_valid, channels = read_single_param_direct(cmd_handler, None, 'ADC', 'CHANNEL')
    if not is_valid:
        safe_log(None, f"Channels are out of bounds, got {channels}", tag = "error", do_print = True)
        raise ValueError(f"Channels are out of bounds, got {channels}")

    if get_sys_value('adc_channels') != channels:
        set_sys_value('adc_channels', channels)

    # --- Fragment Size ---
    is_valid, fragment_size = read_single_param_direct(cmd_handler, None, 'ADC', 'FRAGMENT')
    if not is_valid:
        safe_log(None, f"Invalid fragment size: {fragment_size}", tag = "error", do_print = True)
        raise ValueError(f"Invalid fragment size: {fragment_size}")

    if get_sys_value('adc_fragment') != fragment_size:
        set_sys_value('adc_fragment', fragment_size)

    # --- Derived ---
    no_of_fragments = sample_rate // fragment_size
    if get_sys_value('sys_no_of_fragments') != no_of_fragments:
        set_sys_value('sys_no_of_fragments', no_of_fragments)

    rcv_data_in_bytes = (fragment_size + get_sys_value('sys_data_hdr_size')) * 2
    if get_sys_value('sys_rcv_data_size') != rcv_data_in_bytes:
        set_sys_value('sys_rcv_data_size', rcv_data_in_bytes)

    # --- Final Log and Confirmation ---
    play_audio('gui')
    safe_log(None, "System initialised with :", do_print = True)
    safe_log(None, f"Input Channels : {channels}", do_print = True)
    safe_log(None, f"Sampling Rate  : {sample_rate} Hz", do_print = True)

    return True

#-------------------------------------------------------------------------------
    