import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from uart import UartDevice
from memmap import UART_DATA, UART_STATUS, UART_STATUS_RX_READY, \
    UART_STATUS_TX_READY, UART_RX_FIFO_DEPTH


class UartDeviceTests(unittest.TestCase):
    def make(self):
        output = bytearray()
        return UartDevice(on_output=output.extend), output

    def test_status_with_empty_rx_fifo(self):
        uart, _ = self.make()
        self.assertEqual(uart.read32(UART_STATUS), UART_STATUS_TX_READY)

    def test_write_data_calls_output(self):
        uart, output = self.make()
        uart.write32(UART_DATA, ord("a"))
        self.assertEqual(bytes(output), b"a")

    def test_write_data_only_uses_low_byte(self):
        uart, output = self.make()
        uart.write32(UART_DATA, 0x1234ff41)
        self.assertEqual(bytes(output), b"A")

    def test_feed_sets_rx_ready(self):
        uart, _ = self.make()
        uart.feed(b"hi")
        status = uart.read32(UART_STATUS)
        self.assertTrue(status & UART_STATUS_RX_READY)
        self.assertTrue(status & UART_STATUS_TX_READY)

    def test_read_data_pops_in_order(self):
        uart, _ = self.make()
        uart.feed(b"hi")
        self.assertEqual(uart.read32(UART_DATA), ord("h"))
        self.assertEqual(uart.read32(UART_DATA), ord("i"))

    def test_read_data_with_empty_fifo_is_zero(self):
        uart, _ = self.make()
        self.assertEqual(uart.read32(UART_DATA), 0)

    def test_rx_ready_clears_once_drained(self):
        uart, _ = self.make()
        uart.feed(b"x")
        uart.read32(UART_DATA)
        self.assertFalse(uart.read32(UART_STATUS) & UART_STATUS_RX_READY)

    def test_overrun_drops_newest_byte_keeps_queued_data(self):
        uart, _ = self.make()
        uart.feed(bytes(range(UART_RX_FIFO_DEPTH)))
        uart.feed(bytes([0xff]))
        received = [uart.read32(UART_DATA) for _ in range(UART_RX_FIFO_DEPTH)]
        self.assertEqual(received, list(range(UART_RX_FIFO_DEPTH)))
        self.assertEqual(uart.read32(UART_DATA), 0)

    def test_default_output_goes_to_stdout(self):
        uart = UartDevice()
        self.assertIsNotNone(uart.on_output)


if __name__ == "__main__":
    unittest.main()
