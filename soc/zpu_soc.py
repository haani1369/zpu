import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))
sys.path.insert(0, os.path.dirname(__file__))

from zpu import ZPU
from assembler import assemble
from mmio import Bus
from virtio_console import VirtioConsole

CONSOLE_MMIO_SIZE = 0x200


class SoC:
    def __init__(self, ram_size=1 << 16, console_queue_size=8, on_output=None):
        self.bus = Bus(ram_size)
        self.console = VirtioConsole(queue_size=console_queue_size,
                                     on_output=on_output)
        self.console_base = self.bus.attach(self.console, CONSOLE_MMIO_SIZE)
        self.console.attach_ram(self.bus.ram)
        self.cpu = None

    def load(self, program):
        self.cpu = ZPU(program, memory_size=self.bus.ram_size)
        self.bus.ram[:] = self.cpu.mem
        self.cpu.mem = self.bus
        return self.cpu

    def run(self, limit=1000000):
        return self.cpu.run(limit=limit)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--ram", type=int, default=1 << 16)
    parser.add_argument("--limit", type=int, default=5000000)
    parser.add_argument("--feed", default=None)
    args = parser.parse_args()

    if args.file.endswith(".s"):
        with open(args.file) as f:
            program = assemble(f.read())
    else:
        with open(args.file, "rb") as f:
            program = f.read()

    soc = SoC(ram_size=args.ram)
    soc.load(program)
    if args.feed is not None:
        soc.console.feed(args.feed.encode())
    soc.run(limit=args.limit)


if __name__ == "__main__":
    main()
