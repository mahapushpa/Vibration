import numpy as np
import numpy.fft as fft
import matplotlib.pyplot as plt
from cmath import rect

def fourier_series(x, y, wn, n = None):
    # get FFT
    myfft = fft.fft(y, n)

    # kill higher freqs above wavenumber wn
    myfft[wn:-wn] = 0

    # make new series
    y2 = fft.ifft(myfft)

    fig, (inp, out) = plt.subplots(nrows = 1, ncols = 2, constrained_layout = True)
    inp.plot(x, y), out.plot(x, y2)   

    plt.show()


def tf_fftway(x, y1, y2, wn, n = None):

    # get FFT
    fft1 = np.fft.fft(y1)
    fft2 = np.fft.fft(y2)
    amp1 = np.abs(fft1)
    amp2 = np.abs(fft2)
    

    ang1 = np.angle(fft1)
    ang2 = np.angle(fft2)

    amp = amp2/amp1
    ang = ang2-ang1

    nprect = np.vectorize(rect)
    c = nprect(amp, np.deg2rad(ang))

    # make new series
    y3 = np.fft.ifft(c)

    fig, out = plt.subplots(nrows = 3, ncols = 1, constrained_layout = True)
    out[0].plot(x, y1)
    out[1].plot(x, y2)
    out[2].plot(x, y3)   

    plt.show()

if __name__=='__main__':

    x = np.array([float(i) for i in range(0, 360)])

    y1 = np.sin(2*np.pi/360*x) + np.sin(2*2*np.pi/360*x) + 5
    # fourier_series(x, y1, 3, 360)

    y2 = np.sin(2*np.pi/360*x) + np.sin(2*2*np.pi/360*x) + 3
    tf_fftway(x, y1, y2, 3, 360)