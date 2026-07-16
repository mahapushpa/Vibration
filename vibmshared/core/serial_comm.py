import serial
import logging
import traceback
import threading
import time

#------------------------------------------------------------------------------
from vibmshared.modules.simulator   import Simulator, SimulationPort
from vibmshared.core.common         import set_session_flag
from vibmshared.utils.utils_helpers import safe_log

#------------------------------------------------------------------------------
class ConnectionThreadManager:
    def __init__(self, queue_handler, signal_handler, con_handler):
        self.queue_handler  = queue_handler
        self.signal_handler = signal_handler
        self.con_handler    = con_handler
        
        self.connection_thread = None
        
#------------------------------------------------------------------------------
    def is_connection_healthy(self) -> bool:
            """
            Returns True if no thread is running yet, or the thread is alive.
            Returns False if the thread has stopped on its own (unexpectedly) —
            check get_connection_error() for the reason.
            """
            if self.connection_thread is None:
                return True
            return self.connection_thread.is_alive()

    def get_connection_error(self):
        """Returns the last error message if the connection thread died
        unexpectedly, or None if it hasn't errored (or hasn't started)."""
        if self.connection_thread is None:
            return None
        return getattr(self.connection_thread, "error", None)

#------------------------------------------------------------------------------
    def start(self):
        while not self.queue_handler.empty():
            self.queue_handler.get()

        if self.connection_thread is None or not self.connection_thread.is_alive():
            self.signal_handler.clear_signal_buffers()

            if isinstance(self.con_handler, SerialPort):
                self.connection_thread = SerialReader(self.queue_handler, self.signal_handler, self.con_handler.serial_port)
                logging.info("Serial port thread started.")
            elif isinstance(self.con_handler, SimulationPort):
                self.connection_thread = Simulator(self.queue_handler, self.signal_handler)
                logging.info("Simulator port thread started.")
            else:
                raise ValueError(f"Unknown connection handler type: {type(self.con_handler)}")

            self.connection_thread.start()

#------------------------------------------------------------------------------
    def stop(self):
        while not self.queue_handler.empty():
            self.queue_handler.get()

        if self.connection_thread:
            self.connection_thread.stop()
            self.connection_thread.join(timeout = 2)
            if self.connection_thread.is_alive():
                logging.warning("Thread did not exit cleanly.")

            if isinstance(self.con_handler, SerialPort):
                logging.info("Serial port thread stopped.")
            elif isinstance(self.con_handler, SimulationPort):
                logging.info("Simulator port thread stopped.")
            else:
                raise ValueError(f"Unknown connection handler type: {type(self.con_handler)}")
                            
            self.connection_thread = None

#-------------------------------------------------------------------------------
class SerialReader(threading.Thread):
    """
    Threaded serial data reader.
    Continuously reads from the serial port and pushes valid ADC data to the queue.
    """
    def __init__(self, queue_handler, signal_handler, serial_port):
        super().__init__(daemon = True)  # Daemon thread, will stop with the program
        self.serial_port    = serial_port
        self.queue_handler  = queue_handler
        self.signal_handler = signal_handler
        self.running = False
        self.error   = None   # holds last exception message, if any
        
    def run(self):
        self.error   = None
        self.running = True
        
        logging.info("Serial thread started.")        

        while self.running:
            try:
                if self.serial_port.inWaiting() > 0:
                    data = self.signal_handler.data_capture(self.serial_port)
                    if data is not None and len(data) > 0:
                        if not self.queue_handler.full():
                            self.queue_handler.put(data)
                        else:
                            # Fragment silently vanishing here is the root of the
                            # one-second plot/record desync (VibMScope CLAUDE.md
                            # [F9]) — at minimum make the drop visible. The
                            # consumer-side resync guard is a separate, later fix.
                            safe_log(None, "[WARN] GUI queue full — fragment dropped; "
                                           "plot/record may desync for ~1s",
                                           tag = "warn", do_print = True)
                else:
                    time.sleep(0.002)  # avoid busy-waiting when no data is pending

            except Exception as e:
                self.running = False
                self.error = str(e)
                safe_log(None, f"Serial thread encountered error: {e}", tag = "error", do_print = True)
                logging.debug(traceback.format_exc())

    def stop(self):
        self.running = False

#------------------------------------------------------------------------------
class SerialPort:
    def __init__(self, baudrate = 115200, timeout = 2):
        self.baudrate = baudrate
        self.timeout  = timeout
        
        self.serial_port = None
        self.serial_port_name = None
        
        self.last_error = None   # add in __init__ too, default None
        
        self.init_serial_port()

#------------------------------------------------------------------------------
    def init_serial_port(self):
        self.get_serial_port_name()
        if self.serial_port_name:
            if self.open_serial_port():
                set_session_flag('connection', 'serial_port')
            else:
                set_session_flag('connection', None)
            
#------------------------------------------------------------------------------
    def open_serial_port(self):
        self.last_error = None
        try:
            self.serial_port = serial.Serial(
                port = self.serial_port_name, baudrate = self.baudrate,
                bytesize = 8, parity = 'N', stopbits = 1, 
                xonxoff  = 0, rtscts = 0,                
                timeout  = self.timeout,
                write_timeout = self.timeout,
            )

            if self.serial_port.isOpen():
                self.serial_port.set_buffer_size(rx_size = 131072, tx_size = 2048)
                self.serial_port.flushInput()
                self.serial_port.flushOutput()
                safe_log(None, f"Serial Port {self.serial_port_name} opened @{self.baudrate}")
                return True

            else:
                safe_log(None, "Serial port failed to open.", tag = "error", do_print = True)
                self.last_error = "Serial port failed to open."
                return False
            
        except Exception as e:
            safe_log(None, f"[SerialPort] Failed to open {self.serial_port_name}: {e}", tag = "error", do_print = True)
            self.last_error  = str(e)
            self.serial_port = None
            self.serial_port_name = None
            return False

#------------------------------------------------------------------------------
    def is_serial_port_open(self):
        return self.serial_port and self.serial_port.is_open

#------------------------------------------------------------------------------
    def send_data(self, data_bytes):
        """
        Sends a command via serial port.
        Parameters:
            data_bytes         : bytes or bytearray
        Returns:
            Length if successful, None if failure occurs.
        """        
        if not self.is_serial_port_open():
            safe_log(None, f"[ERROR] Serial port not open.", tag = "error", do_print = True)
            return None
        try:
            sent_size = self.serial_port.write(data_bytes)
            if sent_size != len(data_bytes):
                safe_log(None, f"[ERROR] Failed to send! sent {sent_size}, against {len(data_bytes)} bytes.", tag = "error", do_print = True)                
                return None
            return sent_size

        except Exception as e:
            safe_log(None, f"Serial communication failed: {e}", tag = "error", do_print = True)             
            logging.debug(traceback.format_exc())
            return None

#------------------------------------------------------------------------------
    def receive_data(self, size, timeout = None):
        """
        Reads expected-size reply from serial port.
        Parameters:
            size    : Expected reply size in bytes
            timeout : Optional override (seconds) for this read only; restored afterward.
        Returns:
            rply (bytes) if successful, or None
        """
        if not self.is_serial_port_open():
            safe_log(None, f"[ERROR] Serial port not open.", tag = "warning", do_print = True)
            return None

        original_timeout = self.serial_port.timeout
        try:
            if timeout is not None:
                self.serial_port.timeout = timeout

            rply = self.serial_port.read(size)
            if len(rply) != size:
                safe_log(None, f"Incomplete received! Expected {size}, got {len(rply)} bytes.", tag = "warning", do_print = True)
            return rply

        except Exception as e:
            safe_log(None, f"[SerialPort] Receive error: {e}", tag = "error", do_print = True)
            logging.debug(traceback.format_exc())
            return None

        finally:
            self.serial_port.timeout = original_timeout
        
#------------------------------------------------------------------------------
    def close_serial_port(self):
        if self.serial_port.is_open:
            self.serial_port.close()
        safe_log(None, f"SerialPort {self.serial_port} Closed.")        
        self.serial_port = None

#-------------------------------------------------------------------------------
    def get_serial_port_name(self):
        """
        Finds and returns the serial port matching to VID_STM.
        If multiple ports match, logs them but only returns the first.
        """
        import serial.tools.list_ports

        VID_STM: int = 1155  # STM USB Vendor ID code

        ports = list(serial.tools.list_ports.comports())
        matching_ports = [port.device for port in ports if port.vid == VID_STM]

        if not matching_ports:
            safe_log(None, "No valid serial device found.", tag = "error", do_print = True)
            return None

        # Print all matching ports for debugging
        if len(matching_ports) > 1:
            safe_log(None, f"Multiple matching serial ports found: {matching_ports}. Using {matching_ports[0]}.", tag = "warning", do_print = True)

        self.serial_port_name = matching_ports[0]
        return True

#------------------------------------------------------------------------------
# these two classes are for testing in stand alone mode only
class DummyQueueHandler:
    def handle_serial_data(self, data):
        print(f"[DummyQueue] Received {len(data)} bytes.")

class DummySignalHandler:
    def insert_new_data(self, data):
        print(f"[DummySignal] Data: {len(data)} bytes")

#------------------------------------------------------------------------------
if __name__ == '__main__':
    import time

    sp = SerialPort()
    available_port = sp.serial_port_name
    print("Available Serial Port:", available_port)

    if sp.is_serial_port_open():
        # Run SerialReader briefly
        qh = DummyQueueHandler()
        sh = DummySignalHandler()
        reader = SerialReader(qh, sh, sp.serial_port)
        reader.start()

        print("[TEST] SerialReader started. Waiting 2s...")
        time.sleep(2)
        reader.stop()
        reader.join()

        sp.close_serial_port()
        print("[TEST] Complete.")

    else:
        print("No valid serial port for thread test.")

