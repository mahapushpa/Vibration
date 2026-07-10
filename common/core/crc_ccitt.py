#-------------------------------------------------------------------------------
class CRC_CCITT:
    """
    Implements the CRC-CCITT (XModem) 16-bit checksum algorithm.
    Polynomial: 0x1021, Initial value: 0xFFFF, Final XOR: 0x0000
    Used for validating data integrity in serial communication.
    """
    POLYNOMIAL          = 0x1021
    FINAL_XOR_VALUE     = 0x0000
    INITIAL_REMAINDER   = 0xFFFF

    def __init__(self):
        self._tab = [self._initial(i) for i in range(256)]

    def _initial(self, c):
        """Precomputes CRC lookup value for a single byte."""
        crc = 0
        c = c << 8
        for _ in range(8):
            if (crc ^ c) & 0x8000:
                crc = (crc << 1) ^ self.POLYNOMIAL
            else:
                crc = crc << 1
            c = c << 1
        return crc & 0xFFFF

    def _update_crc(self, crc, c):
        """Updates CRC with next byte using lookup table."""
        tmp = (crc >> 8) ^ (c & 0xFF)
        crc = ((crc << 8) ^ self._tab[tmp & 0xFF]) & 0xFFFF
        return crc

    def compute_crc(self, data, length = None):
        """
        Compute CRC for a given bytes-like object.
        If length is specified, only the first N bytes are used.
        """
        crc = self.INITIAL_REMAINDER
        end = len(data) if length is None else length

        for i in range(min(end, len(data))):
            crc = self._update_crc(crc, data[i])

        return crc ^ self.FINAL_XOR_VALUE

    def compute_crc_from_string(self, input_string, length=None):
        """
        Compute CRC from a UTF-8 string.
        """
        return self.compute_crc(input_string.encode(), length)

#-------------------------------------------------------------------------------
# Self-test cases
if __name__ == "__main__":
    crc_calculator = CRC_CCITT()

    # Test with the known test string "123456789"
    test_string = "123456789"
    expected_crc = 0x29B1
    computed_crc = crc_calculator.compute_crc_from_string(test_string)

    print(f"Test String: {test_string}")
    print(f"Expected CRC: 0x{expected_crc:04X}")
    print(f"Computed CRC: 0x{computed_crc:04X}")
    print(f"Test {'PASSED' if computed_crc == expected_crc else 'FAILED'}")

    # Test with a byte array (hex values)
    test_bytes = bytes([0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39])
    computed_crc_bytes = crc_calculator.compute_crc(test_bytes)
    print(f"Hex Sequence : {test_bytes.hex().upper()}")
    print(f"Expected CRC: 0x{expected_crc:04X}")
    print(f"Computed CRC: 0x{computed_crc_bytes:04X}")
    print(f"Test {'PASSED' if computed_crc_bytes == expected_crc else 'FAILED'}")
