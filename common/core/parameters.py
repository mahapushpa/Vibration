# ------------------------------------------------------------------------------
from common.utils.utils_helpers  import get_channel_sensor_unit

#-------------------------------------------------------------------------------
class FilterParams:
    """Support multiple selected digital filters with their parameters."""
    filters = {
        'notch'     : {'frequency'        : 50.0,  'quality_factor'   : 30.0},
        'lowpass'   : {'cutoff_frequency' : 300.0, 'order'            : 5},
        'highpass'  : {'cutoff_frequency' : 1.0,   'order'            : 5},
    }
    
    @classmethod
    def is_valid(cls, key, value):
        if key == 'filter':
            return value in cls.filters
        return False
    
    @classmethod
    def get_selected(cls):
        from common.core.sys_config import SystemConfig
        val = SystemConfig.current.get('filter', [])
        if not isinstance(val, list):
            print(f"[WARN] FilterParams: 'filter' is not a list: {val}")
            return []

        valid = []
        for f in val:
            if f in cls.filters:
                valid.append(f)
            else:
                print(f"[WARN] FilterParams: Unknown filter '{f}' will be ignored.")
        return valid

    @classmethod
    def set_selected(cls, selected_filters):
        from common.core.sys_config import SystemConfig
        if not isinstance(selected_filters, list):
            print(f"[WARN] FilterParams.set_selected expects a list, got {type(selected_filters)}")
            return

        filtered = [f for f in selected_filters if f in cls.filters.keys()]

        SystemConfig.current['filter'] = filtered
        SystemConfig.save(meta_action="last_edit_save_on")
        print(f"[INFO] FilterParams: updated filters to {filtered}")

    @classmethod
    def is_enabled(cls, filter_name):
        return filter_name in cls.get_selected()

#-------------------------------------------------------------------------------
class WindowParams:
    """Available window functions for FFT processing."""
    windows = ['rect', 'hann', 'hamming', 'blackman', 'barlett']

    @classmethod
    def is_valid(cls, key, value):
        if key == 'window':
            return value in cls.windows
        return False
    
    @classmethod
    def get_selected(cls):
        from common.core.sys_config import SystemConfig
        return SystemConfig.current.get('window', 'rect')

    @classmethod
    def set_selected(cls, name):
        from common.core.sys_config import SystemConfig
        if name not in cls.windows:
            raise ValueError(f"Invalid window: {name}")
        SystemConfig.current['window'] = name

    @classmethod
    def is_enabled(cls, name):
        return name == cls.get_selected()

    @classmethod
    def label(cls, name):
        return {
            'hann'     : 'Hann Window',
            'hamming'  : 'Hamming Window',
            'blackman' : 'Blackman Window',
            'bartlett' : 'Bartlett Window',
            'rect'     : 'Rectangular (no window, default)',
        }.get(name, name)

#-------------------------------------------------------------------------------
class TransformParams:
    """Signal transforms available for processing (e.g., FFT)."""
    types = ['FFT', 'SFFT']

    @classmethod
    def is_valid(cls, key, value):
        if key == 'transform':
            return value in cls.types
        return False
        
    @classmethod
    def get_selected(cls):
        from common.core.sys_config import SystemConfig
        return SystemConfig.current.get('transform', 'FFT')  # default: 'FFT'

    @classmethod
    def set_selected(cls, name):
        from common.core.sys_config import SystemConfig
        if name not in cls.types:
            raise ValueError(f"Invalid transform type: {name}")
        SystemConfig.current['transform'] = name

    @classmethod
    def is_enabled(cls, name):
        return name == cls.get_selected()

    @classmethod
    def get_description(cls):
        return {
            'FFT' :  'Fast Fourier Transform',
            'SFFT':  'Short-Time Fourier Transform',
        }.get(cls.get_selected(), 'Unknown')

#-------------------------------------------------------------------------------
class TFParams:
    """Transmissibility plotting and analysis parameters.
    - Analysis Types: 'DT' (Displacement), 'FT' (Force)
    - Analysis Methods: 'FFT', 'PSD', 'PEAK', 'RMS'
    """
    ANALYSIS_TYPES   = ['DT', 'FT']          # Transmissibility models
    ANALYSIS_METHODS = ['FFT', 'PSD', 'PEAK', 'RMS']
    types_methods    = ANALYSIS_TYPES + ANALYSIS_METHODS # Union of types and methods

    transmissibility_analysis_type_desc = {
        'DT': 'Displacement Transmissibility', # when base structure is excited
        'FT': 'Force Transmissibility',        # when object/payload is excited
        None: 'N/A'
    }

    transmissibility_analysis_method_dec = {
        'FFT': 'FFT-Based',     # Transmissibility calculated based on fft
        'PSD': 'PSD-Based',     # Transmissibility calculated based on psd
        'PEAK': 'Peak-Based',   # Transmissibility calculated based on peak amplitude
        'RMS':  'RMS-Based',    # Transmissibility calculated based on rms amplitude
        None: 'N/A'
    }

    y_axis_labels = {
        'DT' : "Transmissibility",
        'FT' : "Transmissibility",
        None : "Amplitude Ratio(Output/Input)"
    }

    y_axis_labels_db = {
        'DT': "Transmissibility [dB]",
        'FT': "Transmissibility [dB]",
        None: "Amplitude Ratio [dB]"
    }

    plot_titles = {
        'DT': "Displacement Transmissibility",
        'FT': "Force Transmissibility",
        None: "Amplitude Ratio(Output/Input)"
    }

    @classmethod
    def is_valid(cls, key, value):
        if key == 'analysis_type':
            return value in cls.ANALYSIS_TYPES
        elif key == 'analysis_method':
            return value in cls.ANALYSIS_METHODS
        return False

    @classmethod
    def get_selected_analysis_type(cls):
        from common.core.sys_config import SystemConfig
        type = SystemConfig.current.get('analysis_type', 'Unknown')
        if type == 'Unknown':
            type = 'DT' 
            print(f"[WARN] Unknown analysis_type, using default: {type}")
        return type

    @classmethod
    def set_selected_analysis_type(cls, name):
        from common.core.sys_config import SystemConfig
        if name not in cls.ANALYSIS_TYPES:
            raise ValueError(f"Invalid analysis type: {name}")
        SystemConfig.current['analysis_type'] = name

    @classmethod
    def is_enabled_analysis_type(cls, name):
        return name == cls.get_selected_analysis_type()
    
    @classmethod
    def get_selected_analysis_method(cls):
        from common.core.sys_config import SystemConfig
        method = SystemConfig.current.get('analysis_method', 'Unknown')
        if method == 'Unknown':
            method = 'FFT' 
            print(f"[WARN] Unknown analysis_method, using default: {method}")
        return method

    @classmethod
    def set_selected_analysis_method(cls, name):
        from common.core.sys_config import SystemConfig
        if name not in cls.ANALYSIS_METHODS:
            raise ValueError(f"Invalid analysis method: {name}")
        SystemConfig.current['analysis_method'] = name

    @classmethod
    def is_enabled_analysis_method(cls, name):
        return name == cls.get_selected_analysis_method()
    
    @classmethod
    def get_selected(cls):
        return cls.get_selected_analysis_type(), cls.get_selected_analysis_method()

    @classmethod
    def get_analysis_method_desc(cls, model_key):
        return cls.transmissibility_analysis_method_dec.get(model_key, 'Unknown')
    @classmethod
    def get_analysis_type_desc(cls, model_key):
        return cls.transmissibility_analysis_type_desc.get(model_key, 'Unknown')
    @classmethod
    
    def get_y_axis_label(cls, model_key, use_db):
        return (cls.y_axis_labels_db if use_db else cls.y_axis_labels).get(model_key, "Amplitude Ratio")
    @classmethod
    def get_plot_title(cls, model_key):
        return cls.plot_titles.get(model_key, "Output/Input vs Frequency")

#-------------------------------------------------------------------------------
class PlotParams:
    PRE_EVENT_SECOND = 1

    timeXParams = {
        'span_sec'  : 5,  # seconds_in_window
        'label'     : 'Time (s)',
    }
    timeYParams = {
        'default': 'CNT',
        'CNT': {'min': -3500, 'max': 3500, 'label': 'Counts',  'ceil': 250},
        'MV':  {'min': -500,  'max': 500,  'label': '±mVolt',  'ceil': 100},
        'VEL': {'min': -20,   'max': 20,   'label': 'mm/Sec',  'ceil': 4},
        'ACC': {'min': -10,   'max': 10,   'label': 'mm²/Sec', 'ceil': 2},
    }

    fftXParams = {
        'min_hz': 0,
        'max_hz': 500,
        'label': 'Frequency (Hz)',
    }

    fftYParams = {
        'default': 'linear',
        'dB':     {'min': 0, 'max': 100, 'label': 'dB',          'ceil': 10},
        'linear': {'min': 0, 'max': 1.0, 'label': '|Amplitude|', 'ceil': 0.1},
    }

    axisDiv = {
        'timeXMjrDiv': 5,   'timeXMnrDiv': 5,
        'timeYMjrDiv': 10,  'timeYMnrDiv': 2,
        'freqXMjrDiv': 100, 'freqXMnrDiv': 5,
        'freqYMjrDiv': 10,  'freqYMnrDiv': 2,
    }

    @classmethod
    def is_valid(cls, key, value):
        if key   == 'time_xspan':
            return value in cls.timeXParams
        elif key == 'time_yspan':
            return value in cls.timeYParams
        elif key == 'fft_yspan' :
            return value in cls.fftYParams
        return False
    
    # ---------------- Time Axis ----------------
    @classmethod
    def get_time_axis_config(cls):
        from common.core.sys_config import SystemConfig
        key = SystemConfig.current.get('time_yspan', cls.timeYParams['default'])
        return cls.timeYParams[key] # Returns full dict like {'min':..., 'max':...}
    
    @classmethod
    def get_time_axis_limits(cls):
        cfg = cls.get_time_axis_config()
        return cfg.get('min'), cfg.get('max')

    @classmethod
    def get_time_axis_value(cls, key):
        return cls.get_time_axis_config().get(key)

    @classmethod
    def get_time_x_span(cls):
        return cls.timeXParams.get('span_sec', 5)

    @classmethod
    def get_time_x_label(cls):
        return cls.timeXParams.get('label', 'Time (s)')

    @staticmethod
    def get_time_y_label():
        from common.core.sys_config import get_sys_value
        unit = get_sys_value('time_yspan')
        if unit not in ('CNT', 'MV'):
            unit = get_channel_sensor_unit(0)  # Channel 0 as reference
        return f"Signal [{unit}]"

    # ---------------- FFT Axis ----------------
    @classmethod
    def get_fft_axis_config(cls):
        from common.core.sys_config import SystemConfig
        key = SystemConfig.current.get('fft_yspan', cls.fftYParams['default'])
        return cls.fftYParams[key]
    
    @classmethod
    def get_fft_axis_limits(cls):
        cfg = cls.get_fft_axis_config()
        return cfg.get('min'), cfg.get('max')

    @classmethod
    def get_fft_axis_value(cls, key):
        return cls.get_fft_axis_config().get(key)

    @classmethod
    def get_fft_x_label(cls):
        return cls.fftXParams.get('label', 'Frequency')

    @classmethod
    def get_fft_y_label(cls):
        return cls.get_fft_axis_config().get('label', '')
    
    # ---------------- Axis Division ----------------
    @classmethod
    def get_axis_division_value(cls, key):
        return cls.axisDiv[key]

    @classmethod
    def get_event_centre(cls):
        return (cls.get_time_x_span() + 1) // 2

    @classmethod
    def is_event_centre(cls, counter):
        return counter >= cls.get_event_centre()

    @classmethod
    def get_event_span(cls):
        centre = cls.get_event_centre()
        pre = cls.PRE_EVENT_SECOND
        return (centre - pre - 1, centre + pre)

    @classmethod
    def get_event_sample_range(cls):
        from common.core.sys_config import get_sys_value
        start, end = cls.get_event_span()
        sps = get_sys_value('adc_srate')
        return (start * sps, end * sps) # tuples

    @classmethod
    def get_event_sample_slice(cls):
        start, end = cls.get_event_sample_range()
        return slice(start, end) # sliced object

#-------------------------------------------------------------------------------
class DataHdrParams:
    DATA_HDR_ID   = 0x15

    # Index positions (for future use)
    DATA_HDR_IDX  = 0
    DATA_STS_IDX  = 1
    DATA_CHN_IDX  = 2
    DATA_FRG_IDX  = 3
    DATA_SER_IDX  = 2
    DATA_TIM_IDX  = 3

    # in words, 10 bytes
    DATA_HDR_LEN  = 0x05 

    # Data type rcvd in fragment
    DATA_NORMAL = 0x00
    DATA_EVENT  = 0x01
    DATA_SAT    = 0x02

#-------------------------------------------------------------------------------
class CmdHdrParams:
    CMD_HDR_ID       = 0x14
    CMD_HDR_ID_TYPE_IDX = 0 # word two bytes - hdr_id and cmd type
    CMD_HDR_LEN_IDX  = 1    # number of bytes excluding the Cmd Header
    CMD_HDR_SER_IDX  = 2
    CMD_HDR_CRC_IDX  = 3

    CMD_HDR_LEN      = 0x04     # in words, 8 bytes
