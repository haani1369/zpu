import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))

from zpu import ZPUError


class Bus:
    def __init__(self, ram_size):
        self.ram = bytearray(ram_size)
        self.ram_size = ram_size
        self._regions = []

    def attach(self, device, size):
        base = len(self)
        self._regions.append((base, size, device))
        return base

    def __len__(self):
        return self.ram_size + sum(size for _, size, _ in self._regions)

    def _device_at(self, addr):
        for base, size, device in self._regions:
            if base <= addr < base + size:
                return base, device
        return None, None

    def __getitem__(self, key):
        if isinstance(key, slice):
            start, stop = key.start, key.stop
            assert stop - start == 4 and start % 4 == 0
            if start < self.ram_size:
                return bytes(self.ram[start:stop])
            base, device = self._device_at(start)
            if device is None:
                raise ZPUError("read out of bounds at %d" % start)
            return device.read32(start - base).to_bytes(4, "big")
        if key < self.ram_size:
            return self.ram[key]
        raise ZPUError("byte access to mmio is not supported at %d" % key)

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            start, stop = key.start, key.stop
            assert stop - start == 4 and start % 4 == 0
            if start < self.ram_size:
                self.ram[start:stop] = value
                return
            base, device = self._device_at(start)
            if device is None:
                raise ZPUError("write out of bounds at %d" % start)
            device.write32(start - base, int.from_bytes(value, "big"))
            return
        if key < self.ram_size:
            self.ram[key] = value
            return
        raise ZPUError("byte access to mmio is not supported at %d" % key)
