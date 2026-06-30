import sys

from virtio import VirtioMMIODevice


class VirtioConsole(VirtioMMIODevice):
    DEVICE_ID = 3
    RECEIVEQ = 0
    TRANSMITQ = 1
    CONFIG_SIZE = 16

    def __init__(self, queue_size=8, on_output=None):
        super().__init__(self.DEVICE_ID, [queue_size, queue_size],
                         config_size=self.CONFIG_SIZE)
        self.on_output = on_output or self._write_stdout
        self._input = bytearray()

    @staticmethod
    def _write_stdout(data):
        sys.stdout.write(data.decode("latin-1"))
        sys.stdout.flush()

    def feed(self, data):
        self._input += data
        self._drain_receiveq()

    def on_notify(self, queue_idx):
        if queue_idx == self.TRANSMITQ:
            self._drain_transmitq()
        elif queue_idx == self.RECEIVEQ:
            self._drain_receiveq()

    def _drain_transmitq(self):
        q = self.queues[self.TRANSMITQ]
        if q.vq is None:
            return
        while q.vq.has_pending():
            head = q.vq.next_pending()
            data = q.vq.read_chain(head)
            self.on_output(data)
            q.vq.complete(head, len(data))
            q.vq.advance()
            self.interrupt_status |= 1

    def _drain_receiveq(self):
        q = self.queues[self.RECEIVEQ]
        if q.vq is None:
            return
        while self._input and q.vq.has_pending():
            head = q.vq.next_pending()
            written = q.vq.write_chain(head, bytes(self._input))
            del self._input[:written]
            q.vq.complete(head, written)
            q.vq.advance()
            self.interrupt_status |= 1

    def config_read32(self, offset):
        if offset == 8:
            return 1  # max_nr_ports
        return 0

    def config_write32(self, offset, value):
        if offset == 12:  # emerg_wr
            self.on_output(bytes([value & 0xff]))
