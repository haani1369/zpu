import os
import pty
import subprocess
import sys
import termios
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from zpu_soc import _pump_input
from uart import UartDevice
from memmap import UART_DATA, UART_STATUS, UART_STATUS_RX_READY

HERE = os.path.dirname(os.path.abspath(__file__))


def _wait_for_raw_mode(fd, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not (termios.tcgetattr(fd)[3] & termios.ICANON):
            return True
        time.sleep(0.05)
    return False


class PumpInputTests(unittest.TestCase):
    def setUp(self):
        self.read_fd, self.write_fd = os.pipe()
        self.uart = UartDevice(on_output=lambda data: None)

    def tearDown(self):
        os.close(self.read_fd)
        os.close(self.write_fd)

    def test_does_nothing_before_the_check_interval(self):
        os.write(self.write_fd, b"x")
        stop, since_check = _pump_input(self.uart, self.read_fd, 0, 10)
        self.assertFalse(stop)
        self.assertEqual(since_check, 1)
        self.assertEqual(self.uart.read32(UART_STATUS) & UART_STATUS_RX_READY, 0)

    def test_feeds_available_bytes_once_interval_is_reached(self):
        os.write(self.write_fd, b"hi")
        stop, since_check = _pump_input(self.uart, self.read_fd, 9, 10)
        self.assertFalse(stop)
        self.assertEqual(since_check, 0)
        self.assertEqual(self.uart.read32(UART_DATA), ord("h"))
        self.assertEqual(self.uart.read32(UART_DATA), ord("i"))

    def test_no_data_available_is_not_an_error(self):
        stop, since_check = _pump_input(self.uart, self.read_fd, 9, 10)
        self.assertFalse(stop)
        self.assertEqual(since_check, 0)

    def test_ctrl_c_byte_requests_stop_without_feeding_it(self):
        os.write(self.write_fd, b"\x03")
        stop, _ = _pump_input(self.uart, self.read_fd, 9, 10)
        self.assertTrue(stop)
        self.assertEqual(self.uart.read32(UART_STATUS) & UART_STATUS_RX_READY, 0)


@unittest.skipUnless(sys.platform.startswith("linux") or
                     sys.platform == "darwin", "needs a pty")
class InteractiveSessionTests(unittest.TestCase):
    def test_typed_input_is_echoed_back_live(self):
        master_fd, slave_fd = pty.openpty()
        proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "run_c.py"),
             os.path.join(HERE, "echo.c"), "--interactive"],
            stdin=slave_fd, stdout=slave_fd, stderr=subprocess.PIPE,
            close_fds=True)
        os.close(slave_fd)
        try:
            self.assertTrue(_wait_for_raw_mode(master_fd),
                            "child never entered raw mode")
            deadline = time.time() + 10
            output = b""
            os.write(master_fd, b"hi")
            while b"hi" not in output and time.time() < deadline:
                try:
                    output += os.read(master_fd, 1024)
                except OSError:
                    break
            self.assertIn(b"hi", output)

            os.write(master_fd, b"\x04")
            proc.wait(timeout=5)
            self.assertEqual(proc.returncode, 0)
        finally:
            os.close(master_fd)
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
