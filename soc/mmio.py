import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))
sys.path.insert(0, os.path.dirname(__file__))

from zpu import ZPUError
from memmap import (RAM_BASE, RAM_WINDOW_SIZE, MMIO_BASE, MMIO_WINDOW_SIZE,
                    MMIO_SLOT_SIZE, UART0_BASE, VIDEO0_BASE, VIRTIO_SLOTS,
                    VRAM_BASE, VRAM_WINDOW_SIZE)


class Bus:
    def __init__(self, ram_size, vram_size=1 << 16):
        if ram_size > RAM_WINDOW_SIZE:
            raise ValueError("ram_size exceeds the reserved ram window")
        if vram_size > VRAM_WINDOW_SIZE:
            raise ValueError("vram_size exceeds the reserved vram window")
        self.ram = bytearray(ram_size)
        self.ram_size = ram_size
        self.vram = bytearray(vram_size)
        self.vram_size = vram_size
        self._mmio_slots = {}

    def set_uart(self, device):
        self._mmio_slots[UART0_BASE] = device

    def set_video(self, device):
        self._mmio_slots[VIDEO0_BASE] = device

    def set_virtio(self, slot, device):
        self._mmio_slots[VIRTIO_SLOTS[slot]] = device

    def __len__(self):
        return VRAM_BASE + VRAM_WINDOW_SIZE

    def _mmio_device_at(self, addr):
        slot_base = MMIO_BASE + (addr - MMIO_BASE) // MMIO_SLOT_SIZE * MMIO_SLOT_SIZE
        return self._mmio_slots.get(slot_base), slot_base

    def __getitem__(self, key):
        if isinstance(key, slice):
            start, stop = key.start, key.stop
            assert stop - start == 4 and start % 4 == 0
            if RAM_BASE <= start < RAM_BASE + self.ram_size:
                return bytes(self.ram[start:stop])
            if MMIO_BASE <= start < MMIO_BASE + MMIO_WINDOW_SIZE:
                device, slot_base = self._mmio_device_at(start)
                if device is None:
                    raise ZPUError("read from an unattached mmio slot at %d" % start)
                return device.read32(start - slot_base).to_bytes(4, "big")
            if VRAM_BASE <= start < VRAM_BASE + self.vram_size:
                offset = start - VRAM_BASE
                return bytes(self.vram[offset:offset + 4])
            raise ZPUError("read out of bounds at %d" % start)
        if RAM_BASE <= key < RAM_BASE + self.ram_size:
            return self.ram[key]
        if VRAM_BASE <= key < VRAM_BASE + self.vram_size:
            return self.vram[key - VRAM_BASE]
        raise ZPUError("byte access is not supported at %d" % key)

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            start, stop = key.start, key.stop
            assert stop - start == 4 and start % 4 == 0
            if RAM_BASE <= start < RAM_BASE + self.ram_size:
                self.ram[start:stop] = value
                return
            if MMIO_BASE <= start < MMIO_BASE + MMIO_WINDOW_SIZE:
                device, slot_base = self._mmio_device_at(start)
                if device is None:
                    raise ZPUError("write to an unattached mmio slot at %d" % start)
                device.write32(start - slot_base, int.from_bytes(value, "big"))
                return
            if VRAM_BASE <= start < VRAM_BASE + self.vram_size:
                offset = start - VRAM_BASE
                self.vram[offset:offset + 4] = value
                return
            raise ZPUError("write out of bounds at %d" % start)
        if RAM_BASE <= key < RAM_BASE + self.ram_size:
            self.ram[key] = value
            return
        if VRAM_BASE <= key < VRAM_BASE + self.vram_size:
            self.vram[key - VRAM_BASE] = value
            return
        raise ZPUError("byte access is not supported at %d" % key)
