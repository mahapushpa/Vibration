import timeit
import numpy as np
import numpy.fft as fft
import matplotlib.pyplot as plt

# Number of samplepoints
S = 1024    # Sampling Rate

N = 1024*5  # No of Samples

# Sample spacing
T = 1.0 / S

#-------------------------------------------------------------------------------
# Create the Signalmwith two frequencies
x = T*np.arange(N)
y = np.sin(50.0 * 2.0*np.pi*x) + 1.5*np.sin(80.0 * 2.0*np.pi*x)

figure, (aTime, aFFT) = plt.subplots(nrows = 2, ncols = 1, constrained_layout = True)

aTime.plot(x, y)

#-------------------------------------------------------------------------------
# Take the full fft and take abs to plot it
# record start time
xf1 = 1/(N*T)*np.arange(N//2)
time_start = timeit.default_timer()
yf1 = fft.fft(y)
yf1 = 2.0/N * np.abs(yf1[0:N//2])
# record end time
time_end = timeit.default_timer()
# calculate the duration
time_duration = time_end - time_start
# report the duration
print(f'Method 1 took {time_duration} seconds')

# plt.plot(xf1, yf1)

#-------------------------------------------------------------------------------
# Take ffr real part using np's inbuilt function
# record start time
xf2 = fft.rfftfreq(N, d = 1.0/S)
time_start = timeit.default_timer()
yf2 = np.abs(fft.rfft(y))
# record end time
time_end = timeit.default_timer()
# calculate the duration
time_duration = time_end - time_start
# report the duration
print(f'Method 2 took {time_duration} seconds')

# plt.plot(xf2, yf2)
aFFT.plot(xf2, yf2)

#-------------------------------------------------------------------------------
plt.grid()
plt.show()