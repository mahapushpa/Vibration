import numpy as np
from scipy import signal
import matplotlib.pyplot as plt

fs = 10e3
N = fs*10

time = np.arange(N) / float(fs)

rng = np.random.default_rng()
amp = 2 * np.sqrt(2)
noise_power = 0.01 * fs / 2
mod = 500*np.cos(2*np.pi*0.25*time)
carrier = amp * np.sin(2*np.pi*3e3*time + mod)
noise = rng.normal(scale=np.sqrt(noise_power),
                   size=time.shape)
noise *= np.exp(-time/5)
x = carrier + noise

f, t, Zxx = signal.stft(x, fs, nperseg=2000)

plt.pcolormesh(t, f, np.abs(Zxx), vmin=0, vmax=amp)#, shading='gouraud')

plt.title('STFT Magnitude')
plt.ylabel('Frequency [Hz]')
plt.xlabel('Time [sec]')
# plt.show()

E_x = sum(x**2) / fs  # Energy of x
# Calculate a two-sided STFT with PSD scaling:
f, t, Zxx = signal.stft(x, fs, nperseg=1000, return_onesided=False,
                        scaling='psd')
# Integrate numerically over abs(Zxx)**2:
df, dt = f[1] - f[0], t[1] - t[0]
E_Zxx = sum(np.sum(Zxx.real**2 + Zxx.imag**2, axis=0) * df) * dt
# The energy is the same, but the numerical errors are quite large:
np.isclose(E_x, E_Zxx, rtol=1e-2)

plt.show()