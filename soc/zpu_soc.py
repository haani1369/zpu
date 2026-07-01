import os
import select
import sys
import termios
import tty

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))
sys.path.insert(0, os.path.dirname(__file__))

from zpu import ZPU
from assembler import assemble
from mmio import Bus
from uart import UartDevice
from video import VideoDevice
from virtio_console import VirtioConsole

INTERRUPT_BYTE = b"\x03"
INTERACTIVE_CHECK_INTERVAL = 1000


def _pump_input(uart, fd, since_check, check_interval):
    since_check += 1
    if since_check < check_interval:
        return False, since_check
    readable, _, _ = select.select([fd], [], [], 0)
    if readable:
        data = os.read(fd, 4096)
        if INTERRUPT_BYTE in data:
            return True, 0
        uart.feed(data)
    return False, 0


def run_interactive(soc, limit=None, check_interval=INTERACTIVE_CHECK_INTERVAL):
    stdin_fd = sys.stdin.fileno()
    is_tty = os.isatty(stdin_fd)
    old_settings = termios.tcgetattr(stdin_fd) if is_tty else None
    since_check = 0
    steps = 0
    try:
        if is_tty:
            tty.setraw(stdin_fd)
        while not soc.cpu.halted:
            stop, since_check = _pump_input(soc.uart, stdin_fd, since_check,
                                            check_interval)
            if stop:
                break
            soc.cpu.step()
            steps += 1
            if limit is not None and steps >= limit:
                break
    finally:
        if is_tty:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
            sys.stdout.write("\r\n")
            sys.stdout.flush()


class SoC:
    def __init__(self, ram_size=1 << 16, vram_size=1 << 16,
                on_output=None, attach_virtio_console=False,
                virtio_console_queue_size=8):
        self.bus = Bus(ram_size, vram_size=vram_size)

        self.uart = UartDevice(on_output=on_output)
        self.bus.set_uart(self.uart)

        self.video = VideoDevice()
        self.video.attach_vram(self.bus.vram)
        self.bus.set_video(self.video)

        self.console = None
        if attach_virtio_console:
            self.console = VirtioConsole(queue_size=virtio_console_queue_size)
            self.bus.set_virtio(0, self.console)
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
    parser.add_argument("--vram", type=int, default=1 << 16)
    parser.add_argument("--limit", type=int, default=5000000)
    parser.add_argument("--feed", default=None)
    parser.add_argument("--virtio-console", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()

    if args.file.endswith(".s"):
        with open(args.file) as f:
            program = assemble(f.read())
    else:
        with open(args.file, "rb") as f:
            program = f.read()

    soc = SoC(ram_size=args.ram, vram_size=args.vram,
             attach_virtio_console=args.virtio_console)
    soc.load(program)
    if args.feed is not None:
        soc.uart.feed(args.feed.encode())
    if args.interactive:
        run_interactive(soc)
    else:
        soc.run(limit=args.limit)


if __name__ == "__main__":
    main()
