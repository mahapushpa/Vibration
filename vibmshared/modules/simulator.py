import time
import queue
import threading
import numpy as np
import matplotlib.pyplot as plt

from vibmshared.core.parameters import DataHdrParams
from vibmshared.core.sys_config import get_sys_value
from vibmshared.core.common     import set_session_flag, dt_sample, dt_sample_hdr, default_waveform_cfg

FRAGMENT_TYPES = {0x00: "normal", 0x01: "event", 0x02: "saturation"}

#-------------------------------------------------------------------------------
class SimulationPort:
    """Lightweight connection-type marker for simulation mode — mirrors
    SerialPort's role (a cheap handle used for isinstance() checks and the
    'connection' session flag), not the actual data-generating worker.
    The real worker is the separate Simulator(threading.Thread) instance
    that ConnectionThreadManager.start() constructs when a session begins.
    Previously a full Simulator() was built here just for this purpose,
    which meant every session did the (unused) work of reading 4 sys-config
    values, building a waveform_cfg, and allocating full_wave placeholders,
    only to discard the instance immediately."""
    def __init__(self):
        set_session_flag('connection', 'simulation_port')

#-------------------------------------------------------------------------------
class Simulator(threading.Thread):
    def __init__(self, queue_handler = None, signal_handler = None, waveform_cfg = None, enable_plotting = False):
        super().__init__()
        self.queue_handler = queue_handler
        self.signal_handler = signal_handler
        self.running = False
        self.error   = None   # holds last exception message, if any (mirrors SerialReader)

        # System settings
        self.adc_channels = get_sys_value('adc_channels')
        self.sample_rate  = get_sys_value('adc_srate')
        self.no_of_fragments = get_sys_value('sys_no_of_fragments')
        self.samples_in_fragment = get_sys_value('adc_fragment')
        self.fragment_interval = 1.0 / self.no_of_fragments

        # Waveform configuration
        self.waveform_cfg = waveform_cfg or {
            'amplitude': 1000,
            'frequencies': [3 + ch for ch in range(self.adc_channels)],
            'seed': None
        }
        if self.waveform_cfg.get('seed') is not None:
            np.random.seed(self.waveform_cfg['seed'])

        self.full_wave = [None for _ in range(self.adc_channels)]  # Placeholders for full 1s waveforms

        # Plotting
        self.enable_plotting = enable_plotting

        # 1-second rolling buffer size dynamically calculated
        if self.enable_plotting:
            self.buffer_samples = self.sample_rate   # full 1 second buffer
            self.roll_buffers = [np.zeros(self.buffer_samples, dtype=dt_sample) for _ in range(self.adc_channels)]
            self.fig, self.ax = None, None
            self.plot_lines = []
            self.last_plot_time = time.time()

        # Event handling
        self.last_event_time = time.time()

        set_session_flag('connection', 'simulation_port')
        print(f"[SIM2] Init: {self.adc_channels} ch, {self.sample_rate} Hz, {self.no_of_fragments} frg, {self.samples_in_fragment} samp/frg")

    # ---------------------------------------------------------------------------
    def generate_fragment(self, ch, fragment_no):
        """Generate one fragment for a given channel."""
        a = self.waveform_cfg.get('amplitude', 1000)

        # Generate full 1-second signal once when fragment 0
        if fragment_no == 0 or self.full_wave[ch] is None:
            f = self.waveform_cfg['frequencies'][ch % len(self.waveform_cfg['frequencies'])]
            t_full = np.linspace(0, 1, self.sample_rate, endpoint=False)  # 1 second
            wave = a * np.sin(2 * np.pi * f * t_full)
            noise = np.random.normal(0, a * 0.05, size=t_full.shape)
            signal_full = wave + noise
            signal_full = np.clip(signal_full, -32768, 32767).astype(dt_sample)
            self.full_wave[ch] = signal_full
            print(f"[SIM2] Full wave generated for Channel {ch}")

        start_idx = (fragment_no * self.samples_in_fragment) % self.sample_rate
        end_idx = start_idx + self.samples_in_fragment
        signal = self.full_wave[ch][start_idx:end_idx]

        fragment_type_code = 0x00
        current_time = time.time()
        if (current_time - self.last_event_time) > 10.0:
            self.last_event_time = current_time
            signal = self.generate_shock_wave()
            fragment_type_code = np.random.choice([0x01, 0x02])
            print(f"[SIM2] Injected {'EVENT' if fragment_type_code == 0x01 else 'SATURATION'} at Ch{ch}, Frag{fragment_no}")

        header = self.generate_data_hdr(fragment_type=fragment_type_code, event_time=None, channel_no=ch, fragment_no=fragment_no)
        combined = np.concatenate((header, signal))

        return combined, signal

    # ---------------------------------------------------------------------------
    def generate_shock_wave(self):
        """Generate full fragment as shock (damped sine)."""
        t = np.linspace(0, 1, self.samples_in_fragment, endpoint=False)
        shock = np.sin(2 * np.pi * 40 * t) * np.exp(-5 * t)
        shock = shock * (self.waveform_cfg.get('amplitude', 1000)) * 1.5
        
        # Clip to valid int16 range and cast
        shock = np.clip(shock, -32768, 32767).astype(dt_sample)
        return shock
        # return shock.astype(dt_sample)

    # ---------------------------------------------------------------------------
    def generate_data_hdr(self, fragment_type=0x00, event_time=None, channel_no=0, fragment_no=0):
        """Generate header data."""
        hdr_size = get_sys_value('sys_data_hdr_size')
        hdr_data = np.zeros(hdr_size, dtype=dt_sample_hdr)

        remote_time = np.uint32(event_time if get_sys_value('brd_hw_gps') else int(time.time()))
        hdr_data[0] = np.uint16((channel_no << 8) | DataHdrParams.DATA_HDR_ID)
        hdr_data[1] = np.uint16((fragment_type << 8) | fragment_no)
        hdr_data[2] = np.uint16(get_sys_value('sys_ser_no'))
        hdr_data[3] = np.uint16(remote_time & 0xFFFF)
        hdr_data[4] = np.uint16((remote_time >> 16) & 0xFFFF)
        return hdr_data.astype(dt_sample)

    # ---------------------------------------------------------------------------
    def run(self):
        print("[SIM2] Simulator thread started.")
        self.error   = None
        self.running = True

        if self.enable_plotting:
            self.setup_plot()

        while self.running:
            try:
                for frag_no in range(self.no_of_fragments):
                    for ch in range(self.adc_channels):
                        fragment, signal = self.generate_fragment(ch, frag_no)

                        if not self.queue_handler.full():
                            self.queue_handler.put(fragment)

                        if self.enable_plotting:
                            # Update rolling buffer
                            self.update_roll_buffer(ch, signal)

                    # Refresh plot once per second
                    if self.enable_plotting:
                        if time.time() - self.last_plot_time >= 1.0:
                            self.update_plot()
                            self.last_plot_time = time.time()

                    time.sleep(self.fragment_interval)

            except Exception as e:
                print(f"[SIM2-ERROR] Simulator encountered an error: {e}")
                self.error = str(e)
                break

        print("[SIM2] Simulator thread exited.")

    # ---------------------------------------------------------------------------
    def update_roll_buffer(self, ch, new_signal):
        """Shift old samples and append new fragment into rolling buffer."""
        shift_size = self.samples_in_fragment
        # self.roll_buffers[ch][:-shift_size] = self.roll_buffers[ch][shift_size:]
        # self.roll_buffers[ch][-shift_size:] = new_signal

        if shift_size <= 0 or shift_size > self.buffer_samples:
            print(f"[SIM2-WARN] Invalid shift size: {shift_size}")
            return

        self.roll_buffers[ch][:-shift_size] = self.roll_buffers[ch][shift_size:]
        self.roll_buffers[ch][-shift_size:] = new_signal

    # ---------------------------------------------------------------------------
    def setup_plot(self):
        """Initialize live plot."""
        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.plot_lines = []
        for ch in range(self.adc_channels):
            (line,) = self.ax.plot(self.roll_buffers[ch], label=f"Ch{ch}")
            self.plot_lines.append(line)
        self.ax.set_title("Live Channel Data (Simulator - Rolling 1s)")
        self.ax.set_xlabel("Samples (1s window)")
        self.ax.set_ylabel("Amplitude")
        self.ax.grid(True)
        self.ax.legend()
        plt.show()

    def update_plot(self):
        """Update plot with latest rolling buffer."""
        for ch, line in enumerate(self.plot_lines):
            line.set_ydata(self.roll_buffers[ch])
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    # ---------------------------------------------------------------------------
    def stop(self):
        """Stop the simulator thread."""
        print("[SIM2] Stopping Simulator thread...")
        self.running = False
        self.join(timeout=2)
        # No plt.close() to avoid exit exceptions

# -------------------------------------------------------------------------------
# Standalone Test Mode
if __name__ == "__main__":
    from vibmshared.core.sys_config     import sys_config_init
    from vibmshared.core.path_manager   import PathManager, USEFUL_FOLDERS
    path_mgr = PathManager(__file__, USEFUL_FOLDERS)
    sys_config_init(path_mgr)

    q = queue.Queue()

    print("[SIM2] Standalone Simulator mode.")
    sim = Simulator(queue_handler = q, waveform_cfg = default_waveform_cfg, enable_plotting = True)

    sim.start()
    time.sleep(32)  # Run for 32 seconds for demo
    sim.stop()
