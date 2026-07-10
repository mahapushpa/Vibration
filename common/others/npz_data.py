import numpy as np
data = np.load("tf_250516_151231.npz", allow_pickle = True)
print(data.files)               # To see all keys: e.g. 'signal', 'metadata'
print(data['signal'].shape)     # Verify array shape (channels, samples)
print(data['metadata'].item())  # If metadata is stored as dict

with open("npz_dump.txt", "w") as f:
    for key in data.files:
        f.write(f"{key}:\n{data[key]}\n\n")
