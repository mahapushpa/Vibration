# Transfer Function Simulator
import os
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

#-------------------------------------------------------------------------------
from gui_meta import UserMeta
from maps_sysconfig import sys_load_ini, sys_get_value
from maps_helper import write_metadata_header, write_table_block, get_common_metadata, write_channel_metadata_block

#-------------------------------------------------------------------------------
class tf_config:
    settings = {
        'vibrator': {'freq_start': 1.0, 'freq_stop': 100, 'freq_step': 1, 'duration': 1.0},
        'damper':   {'natural_freq': 20.0, 'damping_ratio': 0.4},
        'noise':    {'enabled': False, 'stddev': 0.01},
    }

    @classmethod
    def get(cls, section, key):
        return cls.settings.get(section, {}).get(key)

    @classmethod
    def set(cls, section, key, value):
        if section in cls.settings:
            cls.settings[section][key] = value

#-------------------------------------------------------------------------------
class SimulatorTF:
    def __init__(self):
        self.noise_enabled = tf_config.get('noise', 'enabled')
        self.noise_config = tf_config.settings['noise']
        self.vibrator_config = tf_config.settings['vibrator']
        self.damper_config = tf_config.settings['damper']
        self.sample_rate = 2048

        # Store simulation results
        self.frequencies = []
        self.input_amps = []
        self.output_amps = []
        self.transmissibility = []

#-------------------------------------------------------------------------------
    def simulate_time_data(self):
        print("[INFO] Starting sine sweep simulation...")

        f_start = self.vibrator_config['freq_start']
        f_stop = self.vibrator_config['freq_stop']
        f_step = self.vibrator_config['freq_step']
        duration = self.vibrator_config['duration']

        f_n = self.damper_config['natural_freq']
        zeta = self.damper_config['damping_ratio']

        t = np.linspace(0, duration, int(self.sample_rate * duration), endpoint = False)

        for freq in range(int(f_start), int(f_stop) + 1, int(f_step)):
            self.set_vibrator_frequency(freq)

            input_signal = np.sin(2 * np.pi * freq * t)

            tf = 1 / np.sqrt((1 - (freq / f_n)**2)**2 + (2 * zeta * freq / f_n)**2)
            output_signal = input_signal * tf

            # Optional noise addition
            if self.noise_enabled:
                stddev = self.noise_config.get('stddev', 0.0)
                noise = np.random.normal(0, stddev, size = output_signal.shape)
                output_signal += noise

            input_amp = np.max(np.abs(input_signal))
            output_amp = np.max(np.abs(output_signal))
            tf_ratio = output_amp / input_amp if input_amp != 0 else 0

            self.frequencies.append(freq)
            self.input_amps.append(input_amp)
            self.output_amps.append(output_amp)
            self.transmissibility.append(tf_ratio)

        print("[INFO] Sweep complete. Frequencies simulated:", len(self.frequencies))

#-------------------------------------------------------------------------------
    def plot_tf(self, use_db = False, show_summary = True):
        """Plot transmissibility curve with optional summary box."""
        print("[INFO] Generating plot...")
        freqs = np.array(self.frequencies)
        transmissibility = np.array(self.transmissibility)

        if use_db:
            tf_plot = 20 * np.log10(transmissibility + 1e-12)  # Avoid log(0)
            ylabel  = 'Transmissibility (dB)'
        else:
            tf_plot = transmissibility 
            ylabel  = 'Transmissibility (linear)'

        plt.figure(figsize = (10, 5))
        plt.plot(freqs, tf_plot)
        plt.title('Transmissibility vs Frequency')
        plt.xlabel('Frequency (Hz)')
        plt.ylabel(ylabel)
        plt.grid(True)

        # Calculate important parameters if requested
        if show_summary:
            # Find resonance frequency (maximum transmissibility point)
            idx_max = np.argmax(transmissibility)
            f_resonant = freqs[idx_max]
            t_max = transmissibility[idx_max]

            # Find isolation start frequency (where TF drops below 1)
            idx_iso = np.where(transmissibility < 1.0)[0]
            f_iso = freqs[idx_iso[0]] if idx_iso.size > 0 else None

            # Build summary text
            info_box = (
                f"Resonant Freq    : {f_resonant:.2f} Hz\n"
                f"Peak at Resonant : {t_max:.2f}    \n"
                f"Isolation Begins : {f_iso:.2f} Hz"
            )

            plt.gca().text(0.99, 0.98, info_box, transform = plt.gca().transAxes,
                           verticalalignment = 'top', horizontalalignment = 'right',
                           bbox = dict(facecolor = 'white', edgecolor = 'gray', boxstyle = 'round,pad = 0.2'),
                           fontsize = 9, family = 'monospace')

        plt.tight_layout()
        plt.show()

#-------------------------------------------------------------------------------
    def set_vibrator_frequency(self, freq):
        # print(f"[STEP] Set vibrator to {freq} Hz")  # Stub for hardware integration
        pass

#-------------------------------------------------------------------------------
    def get_tf_metadata(self):
        return {
            'Duration': f"{self.vibrator_config['duration']} sec per frequency",
            'Freq Start': f"{self.vibrator_config['freq_start']} Hz",
            'Freq Stop': f"{self.vibrator_config['freq_stop']} Hz",
            'Step Size': f"{self.vibrator_config['freq_step']} Hz",
            'Natural Freq': f"{self.damper_config['natural_freq']} Hz",
            'Damping': f"{self.damper_config['damping_ratio']}"
        }

#-------------------------------------------------------------------------------
    def save_tf_data(self, export_csv = False):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = "csv" if export_csv else "txt"
        filename = os.path.join(sys_get_value('data_path'), f"tf_{timestamp}.{ext}")
        print(f"[INFO] Saving TF data to {filename}")

        os.makedirs(os.path.dirname(filename), exist_ok = True)
        with open(filename, 'w', encoding = 'utf-8') as f:
            # UserMeta header
            user_meta = UserMeta(config_path="./config")
            f.write(user_meta.get_header_block() + "\n")
            # Data header
            common_meta = get_common_metadata()
            write_metadata_header(f, "Data Information", common_meta)

            # Transfer Function  header
            tf_meta = self.get_tf_metadata()
            write_metadata_header(f, "Transmissibility Information", tf_meta)

            write_channel_metadata_block(f, csv_mode = export_csv)

            headers = ["Freq", "Chn(1)", "Chn(2)", "TF(Ch2/Ch1)"]
            rows = list(zip(self.frequencies, self.input_amps, self.output_amps, self.transmissibility))
            write_table_block(f, rows, headers, csv_mode = export_csv)

        print("[INFO] File saved successfully.")

#-------------------------------------------------------------------------------
if __name__ == '__main__':
    sys_load_ini()

    # tf_config.set('noise', 'enabled', True)
    sim = SimulatorTF()
    sim.simulate_time_data()
    # sim.save_tf_data(export_csv = True)
    sim.save_tf_data(export_csv = False)
    sim.plot_tf(use_db = True, show_summary = True)  # Set use_db=False for linear plot
