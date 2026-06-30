import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))
sys.path.insert(0, os.path.dirname(__file__))

from zpu import ZPU, ZPUError
from assembler import assemble
from mmio import Bus
from virtio import (
    VirtioMMIODevice,
    Virtqueue,
    MAGICVALUE,
    VERSION,
    DEVICEID,
    VENDORID,
    QUEUESEL,
    QUEUENUMMAX,
    QUEUENUM,
    QUEUEREADY,
    QUEUENOTIFY,
    QUEUEDESCLOW,
    QUEUEAVAILLOW,
    QUEUEUSEDLOW,
    STATUS,
    INTERRUPTSTATUS,
    INTERRUPTACK,
    CONFIG,
)
from virtio_console import VirtioConsole


class FakeDevice:
    def __init__(self):
        self.writes = []

    def read32(self, offset):
        return 0xabcd0000 | offset

    def write32(self, offset, value):
        self.writes.append((offset, value))


class BusTests(unittest.TestCase):
    def test_ram_word_access(self):
        bus = Bus(64)
        bus[0:4] = (0x11223344).to_bytes(4, "big")
        self.assertEqual(int.from_bytes(bus[0:4], "big"), 0x11223344)

    def test_ram_byte_access(self):
        bus = Bus(64)
        bus[5] = 0x42
        self.assertEqual(bus[5], 0x42)

    def test_device_dispatch(self):
        bus = Bus(64)
        dev = FakeDevice()
        base = bus.attach(dev, 0x100)
        self.assertEqual(base, 64)
        bus[base + 8:base + 12] = (99).to_bytes(4, "big")
        self.assertEqual(dev.writes, [(8, 99)])
        self.assertEqual(int.from_bytes(bus[base + 4:base + 8], "big"),
                         0xabcd0000 | 4)

    def test_byte_access_to_device_rejected(self):
        bus = Bus(64)
        base = bus.attach(FakeDevice(), 0x100)
        with self.assertRaises(ZPUError):
            bus[base]

    def test_len_covers_ram_and_devices(self):
        bus = Bus(64)
        bus.attach(FakeDevice(), 0x100)
        self.assertEqual(len(bus), 64 + 0x100)

    def test_out_of_bounds_via_zpu_read_word(self):
        bus = Bus(64)
        bus.attach(FakeDevice(), 0x100)
        cpu = ZPU(bytes(4), memory_size=64)
        cpu.mem = bus
        with self.assertRaises(ZPUError):
            cpu.read_word(64 + 0x100)


class VirtioRegisterTests(unittest.TestCase):
    def make(self):
        dev = VirtioMMIODevice(device_id=42, queue_num_max=[4, 8])
        dev.attach_ram(bytearray(4096))
        return dev

    def test_identity_registers(self):
        dev = self.make()
        self.assertEqual(dev.read32(MAGICVALUE), 0x74726976)
        self.assertEqual(dev.read32(VERSION), 2)
        self.assertEqual(dev.read32(DEVICEID), 42)
        self.assertEqual(dev.read32(VENDORID), VirtioMMIODevice.VENDOR_ID)

    def test_queue_num_max_is_per_selected_queue(self):
        dev = self.make()
        dev.write32(QUEUESEL, 0)
        self.assertEqual(dev.read32(QUEUENUMMAX), 4)
        dev.write32(QUEUESEL, 1)
        self.assertEqual(dev.read32(QUEUENUMMAX), 8)

    def test_status_roundtrip_and_reset(self):
        dev = self.make()
        dev.write32(STATUS, VirtioMMIODevice.ACKNOWLEDGE | VirtioMMIODevice.DRIVER)
        self.assertEqual(dev.read32(STATUS),
                         VirtioMMIODevice.ACKNOWLEDGE | VirtioMMIODevice.DRIVER)
        dev.write32(STATUS, 0)
        self.assertEqual(dev.read32(STATUS), 0)

    def test_configuring_queue_creates_virtqueue(self):
        dev = self.make()
        dev.write32(QUEUESEL, 0)
        dev.write32(QUEUENUM, 4)
        dev.write32(QUEUEDESCLOW, 0x100)
        dev.write32(QUEUEAVAILLOW, 0x200)
        dev.write32(QUEUEUSEDLOW, 0x300)
        dev.write32(QUEUEREADY, 1)
        vq = dev.queues[0].vq
        self.assertIsNotNone(vq)
        self.assertEqual((vq.desc_addr, vq.avail_addr, vq.used_addr, vq.num),
                         (0x100, 0x200, 0x300, 4))
        self.assertEqual(dev.read32(QUEUEREADY), 1)

    def test_notify_ignored_before_driver_ok(self):
        calls = []

        class D(VirtioMMIODevice):
            def on_notify(self, idx):
                calls.append(idx)

        dev = D(device_id=1, queue_num_max=[4])
        dev.attach_ram(bytearray(64))
        dev.write32(QUEUENOTIFY, 0)
        self.assertEqual(calls, [])
        dev.write32(STATUS, VirtioMMIODevice.DRIVER_OK)
        dev.write32(QUEUENOTIFY, 0)
        self.assertEqual(calls, [0])

    def test_interrupt_ack_clears_status(self):
        dev = self.make()
        dev.interrupt_status = 1
        dev.write32(INTERRUPTACK, 1)
        self.assertEqual(dev.read32(INTERRUPTSTATUS), 0)

    def test_config_space_dispatch(self):
        class D(VirtioMMIODevice):
            def config_read32(self, offset):
                return 0x55 if offset == 4 else 0

            def config_write32(self, offset, value):
                self.last = (offset, value)

        dev = D(device_id=1, queue_num_max=[], config_size=8)
        dev.attach_ram(bytearray(64))
        self.assertEqual(dev.read32(CONFIG + 4), 0x55)
        dev.write32(CONFIG, 7)
        self.assertEqual(dev.last, (0, 7))


def poke_descriptor(ram, table, index, addr, length, flags, nxt):
    base = table + index * 20
    for offset, value in ((0, addr), (4, 0), (8, length), (12, flags), (16, nxt)):
        ram[base + offset:base + offset + 4] = (value & 0xffffffff).to_bytes(4, "big")


def publish(ram, avail, num, slot, head):
    ram[avail + 8 + (slot % num) * 4:avail + 12 + (slot % num) * 4] = \
        (head & 0xffffffff).to_bytes(4, "big")
    idx = int.from_bytes(ram[avail + 4:avail + 8], "big")
    ram[avail + 4:avail + 8] = ((idx + 1) & 0xffffffff).to_bytes(4, "big")


def used_entry(ram, used, num, slot):
    base = used + 8 + (slot % num) * 8
    return (int.from_bytes(ram[base:base + 4], "big"),
            int.from_bytes(ram[base + 4:base + 8], "big"))


class VirtqueueTests(unittest.TestCase):
    def setUp(self):
        self.ram = bytearray(4096)
        self.vq = Virtqueue(self.ram, num=4)
        self.vq.desc_addr = 0x000
        self.vq.avail_addr = 0x100
        self.vq.used_addr = 0x200

    def test_no_pending_initially(self):
        self.assertFalse(self.vq.has_pending())

    def test_single_descriptor_chain_read(self):
        self.ram[0x300:0x305] = b"hello"
        poke_descriptor(self.ram, 0x000, 0, 0x300, 5, 0, 0)
        publish(self.ram, 0x100, 4, 0, 0)
        self.assertTrue(self.vq.has_pending())
        head = self.vq.next_pending()
        self.assertEqual(head, 0)
        self.assertEqual(self.vq.read_chain(head), b"hello")

    def test_multi_descriptor_chain_read(self):
        self.ram[0x300:0x303] = b"abc"
        self.ram[0x310:0x313] = b"def"
        poke_descriptor(self.ram, 0x000, 0, 0x300, 3, 1, 1)
        poke_descriptor(self.ram, 0x000, 1, 0x310, 3, 0, 0)
        publish(self.ram, 0x100, 4, 0, 0)
        head = self.vq.next_pending()
        self.assertEqual(self.vq.read_chain(head), b"abcdef")

    def test_write_chain_truncates_to_buffer_size(self):
        poke_descriptor(self.ram, 0x000, 0, 0x300, 3, 0, 0)
        written = self.vq.write_chain(0, b"abcdef")
        self.assertEqual(written, 3)
        self.assertEqual(bytes(self.ram[0x300:0x303]), b"abc")

    def test_complete_writes_used_ring_and_advances_idx(self):
        self.vq.complete(head=2, length=7)
        self.assertEqual(used_entry(self.ram, 0x200, 4, 0), (2, 7))
        self.assertEqual(int.from_bytes(self.ram[0x204:0x208], "big"), 1)

    def test_advance_moves_past_consumed_entry(self):
        poke_descriptor(self.ram, 0x000, 0, 0x300, 0, 0, 0)
        publish(self.ram, 0x100, 4, 0, 0)
        publish(self.ram, 0x100, 4, 1, 1)
        self.assertTrue(self.vq.has_pending())
        self.assertEqual(self.vq.next_pending(), 0)
        self.vq.advance()
        self.assertTrue(self.vq.has_pending())
        self.assertEqual(self.vq.next_pending(), 1)
        self.vq.advance()
        self.assertFalse(self.vq.has_pending())


def bring_up(dev, queue, num, desc, avail, used):
    dev.write32(QUEUESEL, queue)
    dev.write32(QUEUENUM, num)
    dev.write32(QUEUEDESCLOW, desc)
    dev.write32(QUEUEAVAILLOW, avail)
    dev.write32(QUEUEUSEDLOW, used)
    dev.write32(QUEUEREADY, 1)


class VirtioConsoleTests(unittest.TestCase):
    def setUp(self):
        self.output = bytearray()
        self.console = VirtioConsole(queue_size=4, on_output=self.output.extend)
        self.ram = bytearray(4096)
        self.console.attach_ram(self.ram)
        self.console.write32(STATUS, VirtioMMIODevice.ACKNOWLEDGE
                             | VirtioMMIODevice.DRIVER
                             | VirtioMMIODevice.DRIVER_OK)

    def test_device_id_is_console(self):
        self.assertEqual(self.console.read32(DEVICEID), VirtioConsole.DEVICE_ID)

    def test_transmit_one_chain(self):
        bring_up(self.console, VirtioConsole.TRANSMITQ, 4, 0x000, 0x100, 0x200)
        self.ram[0x300:0x305] = b"hello"
        poke_descriptor(self.ram, 0x000, 0, 0x300, 5, 0, 0)
        publish(self.ram, 0x100, 4, 0, 0)
        self.console.write32(QUEUENOTIFY, VirtioConsole.TRANSMITQ)
        self.assertEqual(bytes(self.output), b"hello")
        self.assertEqual(used_entry(self.ram, 0x200, 4, 0), (0, 5))
        self.assertTrue(self.console.read32(INTERRUPTSTATUS) & 1)

    def test_receive_fills_posted_buffer(self):
        bring_up(self.console, VirtioConsole.RECEIVEQ, 4, 0x000, 0x100, 0x200)
        poke_descriptor(self.ram, 0x000, 0, 0x400, 8, 2, 0)
        publish(self.ram, 0x100, 4, 0, 0)
        self.console.feed(b"hi")
        self.assertEqual(bytes(self.ram[0x400:0x402]), b"hi")
        self.assertEqual(used_entry(self.ram, 0x200, 4, 0), (0, 2))

    def test_emerg_write_reaches_output(self):
        self.console.write32(CONFIG + 12, ord("!"))
        self.assertEqual(bytes(self.output), b"!")


class IntegrationTests(unittest.TestCase):
    def test_zpu_program_drives_console_over_mmio(self):
        bus = Bus(1024)
        output = bytearray()
        console = VirtioConsole(queue_size=4, on_output=output.extend)
        base = bus.attach(console, 0x200)
        console.attach_ram(bus.ram)

        program = assemble(
            "    im %d\n"
            "    im %d\n"
            "    store\n"
            "    breakpoint\n" % (VirtioConsole.TRANSMITQ, base + QUEUENOTIFY))
        cpu = ZPU(program, memory_size=1024)
        bus.ram[:] = cpu.mem
        cpu.mem = bus

        bring_up(console, VirtioConsole.TRANSMITQ, 4, 0x300, 0x340, 0x380)
        bus.ram[0x3c0:0x3c5] = b"hola!"
        poke_descriptor(bus.ram, 0x300, 0, 0x3c0, 5, 0, 0)
        publish(bus.ram, 0x340, 4, 0, 0)
        console.write32(STATUS, VirtioMMIODevice.DRIVER_OK)

        cpu.run(limit=1000)

        self.assertEqual(bytes(output), b"hola!")


if __name__ == "__main__":
    unittest.main()
