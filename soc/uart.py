import collections
import sys

from memmap import UART_DATA, UART_STATUS, UART_STATUS_RX_READY, \
    UART_STATUS_TX_READY, UART_RX_FIFO_DEPTH


class UartDevice:
    def __init__(self, on_output=None):
        self.on_output = on_output or self._write_stdout
        self._rx = collections.deque()

    @staticmethod
    def _write_stdout(data):
        sys.stdout.write(data.decode("latin-1"))
        sys.stdout.flush()

    def feed(self, data):
        for byte in data:
            if len(self._rx) < UART_RX_FIFO_DEPTH:
                self._rx.append(byte)

    def read32(self, offset):
        if offset == UART_DATA:
            return self._rx.popleft() if self._rx else 0
        if offset == UART_STATUS:
            status = UART_STATUS_TX_READY
            if self._rx:
                status |= UART_STATUS_RX_READY
            return status
        return 0

    def write32(self, offset, value):
        if offset == UART_DATA:
            self.on_output(bytes([value & 0xff]))
