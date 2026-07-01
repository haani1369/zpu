import os
import select
import socket
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))

from zpu import ZPU, ZPUError

# gdb has no built-in notion of a zpu architecture, and every architecture it
# does know rejects a target-description register set that doesn't match its
# own hardcoded expectations, even when told there is no os. rather than
# fight that, the stub speaks the i386 register wire format instead: no
# target description is needed at all for an architecture gdb already knows
# natively, and gdb's own $pc/$sp convenience registers already resolve to
# eip/esp for i386, so nothing user-visible actually says "i386" except the
# `set architecture i386` and `set endian big` lines the user runs once.
# `set endian big` is what makes gdb display memory (the stack, e.g. `x/xw
# $sp`) in zpu's real big-endian byte order instead of i386's native little-
# endian; it makes gdb expect registers in big-endian order too, which is why
# registers are encoded that way here rather than in i386's own native order.
# the register ordering and regnums below are i386's fixed protocol register
# list, not anything specific to this stub: eax, ecx, edx, ebx, esp, ebp,
# esi, edi, eip, eflags, cs, ss, ds, es, fs, gs. only esp (regnum 4) and eip
# (regnum 8) mean anything here.
I386_REGNUM_SP = 4
I386_REGNUM_PC = 8
I386_NUM_REGS = 16


def _encode_reg(value):
    return value.to_bytes(4, "big").hex().encode()


def _decode_reg(hexdata):
    return int.from_bytes(bytes.fromhex(hexdata.decode()), "big")


def checksum(data):
    return sum(data) & 0xff


def frame(data):
    return b"$" + data + b"#" + b"%02x" % checksum(data)


class PacketStream:
    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        self.buf += data

    def next_event(self):
        if not self.buf:
            return None
        first = self.buf[0]
        if first == ord("+"):
            del self.buf[0]
            return ("ack",)
        if first == ord("-"):
            del self.buf[0]
            return ("nak",)
        if first == 0x03:
            del self.buf[0]
            return ("interrupt",)
        if first == ord("$"):
            end = self.buf.find(b"#")
            if end < 0 or len(self.buf) < end + 3:
                return None
            data = bytes(self.buf[1:end])
            their_checksum = int(bytes(self.buf[end + 1:end + 3]), 16)
            del self.buf[:end + 3]
            if their_checksum != checksum(data):
                return ("badpacket",)
            return ("packet", data)
        del self.buf[0]
        return self.next_event()


class Target:
    def __init__(self, cpu):
        self.cpu = cpu
        self.breakpoints = set()
        self.interrupt_check_interval = 4096

    def read_registers(self):
        return self.cpu.pc, self.cpu.sp

    def write_registers(self, pc, sp):
        self.cpu.pc = pc
        self.cpu.sp = sp

    def read_memory(self, addr, length):
        if addr < 0 or addr + length > len(self.cpu.mem):
            raise ZPUError("read out of bounds at %d" % addr)
        return bytes(self.cpu.mem[addr:addr + length])

    def write_memory(self, addr, data):
        if addr < 0 or addr + len(data) > len(self.cpu.mem):
            raise ZPUError("write out of bounds at %d" % addr)
        self.cpu.mem[addr:addr + len(data)] = data

    def step(self):
        self.cpu.step()
        return self.cpu.halted

    def continue_(self, should_stop=lambda: False):
        if self.cpu.pc in self.breakpoints and self.step():
            return "halt"
        since_check = 0
        while True:
            if self.cpu.pc in self.breakpoints:
                return "break"
            since_check += 1
            if since_check >= self.interrupt_check_interval:
                since_check = 0
                if should_stop():
                    return "interrupt"
            if self.step():
                return "halt"


class GDBServer:
    def __init__(self, sock, target):
        self.sock = sock
        self.target = target
        self.stream = PacketStream()
        self.should_close = False

    def run(self):
        while not self.should_close:
            data = self.sock.recv(4096)
            if not data:
                return
            self._process(data)

    def serve_one(self):
        data = self.sock.recv(4096)
        if data:
            self._process(data)

    def _process(self, data):
        self.stream.feed(data)
        while True:
            event = self.stream.next_event()
            if event is None:
                return
            self._handle_event(event)

    def _handle_event(self, event):
        kind = event[0]
        if kind == "packet":
            self.sock.sendall(b"+")
            packet = event[1]
            self.sock.sendall(frame(self.handle_command(packet)))
            if packet in (b"D", b"k"):
                self.should_close = True
        elif kind == "badpacket":
            self.sock.sendall(b"-")

    def _check_interrupt(self):
        readable, _, _ = select.select([self.sock], [], [], 0)
        if not readable:
            return False
        data = self.sock.recv(4096)
        if data:
            self.stream.feed(data)
        if self.stream.buf and self.stream.buf[0] == 0x03:
            del self.stream.buf[0]
            return True
        return False

    def _continue_reply(self):
        result = self.target.continue_(should_stop=self._check_interrupt)
        return {"break": b"S05", "halt": b"W00", "interrupt": b"S02"}[result]

    def _step_reply(self):
        return b"W00" if self.target.step() else b"S05"

    def handle_command(self, packet):
        try:
            return self._dispatch(packet)
        except Exception:
            return b"E01"

    def _dispatch(self, packet):
        if packet == b"?":
            return b"S05"
        if packet == b"g":
            pc, sp = self.target.read_registers()
            regs = [0] * I386_NUM_REGS
            regs[I386_REGNUM_SP] = sp
            regs[I386_REGNUM_PC] = pc
            return b"".join(_encode_reg(r) for r in regs)
        if packet.startswith(b"G"):
            hexdata = packet[1:]
            fields = [hexdata[i:i + 8] for i in range(0, len(hexdata), 8)]
            pc, sp = self.target.read_registers()
            if len(fields) > I386_REGNUM_SP:
                sp = _decode_reg(fields[I386_REGNUM_SP])
            if len(fields) > I386_REGNUM_PC:
                pc = _decode_reg(fields[I386_REGNUM_PC])
            self.target.write_registers(pc, sp)
            return b"OK"
        if packet.startswith(b"p"):
            n = int(packet[1:], 16)
            if n >= I386_NUM_REGS:
                return b"E01"
            pc, sp = self.target.read_registers()
            if n == I386_REGNUM_PC:
                return _encode_reg(pc)
            if n == I386_REGNUM_SP:
                return _encode_reg(sp)
            return _encode_reg(0)
        if packet.startswith(b"P"):
            n_hex, val_hex = packet[1:].split(b"=")
            n, val = int(n_hex, 16), _decode_reg(val_hex)
            if n >= I386_NUM_REGS:
                return b"E01"
            pc, sp = self.target.read_registers()
            if n == I386_REGNUM_PC:
                self.target.write_registers(val, sp)
            elif n == I386_REGNUM_SP:
                self.target.write_registers(pc, val)
            return b"OK"
        if packet.startswith(b"m"):
            addr_hex, len_hex = packet[1:].split(b",")
            data = self.target.read_memory(int(addr_hex, 16), int(len_hex, 16))
            return data.hex().encode()
        if packet.startswith(b"M"):
            header, hexdata = packet[1:].split(b":")
            addr_hex, len_hex = header.split(b",")
            self.target.write_memory(int(addr_hex, 16),
                                     bytes.fromhex(hexdata.decode()))
            return b"OK"
        if packet.startswith(b"Z0,"):
            _, addr_hex, _ = packet.split(b",")
            self.target.breakpoints.add(int(addr_hex, 16))
            return b"OK"
        if packet.startswith(b"z0,"):
            _, addr_hex, _ = packet.split(b",")
            self.target.breakpoints.discard(int(addr_hex, 16))
            return b"OK"
        if packet == b"c" or packet.startswith(b"c"):
            if len(packet) > 1:
                self.target.cpu.pc = int(packet[1:], 16)
            return self._continue_reply()
        if packet == b"s" or packet.startswith(b"s"):
            if len(packet) > 1:
                self.target.cpu.pc = int(packet[1:], 16)
            return self._step_reply()
        if packet.startswith(b"qSupported"):
            return b"PacketSize=4000"
        if packet in (b"D", b"k"):
            return b"OK"
        return b""


def main():
    import argparse

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))
    from assembler import assemble

    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--port", type=int, default=1234)
    parser.add_argument("--memory", type=int, default=1 << 16)
    args = parser.parse_args()

    with open(args.file, "rb" if not args.file.endswith(".s") else "r") as f:
        content = f.read()
    program = assemble(content) if args.file.endswith(".s") else content

    cpu = ZPU(program, memory_size=args.memory)
    target = Target(cpu)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("localhost", args.port))
    listener.listen(1)
    print("listening on port %d" % args.port)
    conn, _ = listener.accept()
    try:
        GDBServer(conn, target).run()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
