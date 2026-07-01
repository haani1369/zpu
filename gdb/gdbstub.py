import os
import select
import socket
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))

from zpu import ZPU, ZPUError

TARGET_XML = b"""<?xml version="1.0"?>
<!DOCTYPE target SYSTEM "gdb-target.dtd">
<target>
<feature name="org.gnu.gdb.zpu.core">
<reg name="pc" bitsize="32" type="code_ptr"/>
<reg name="sp" bitsize="32" type="data_ptr"/>
</feature>
</target>
"""


def target_xml():
    return TARGET_XML


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
            return b"%08x%08x" % (pc, sp)
        if packet.startswith(b"G"):
            hexdata = packet[1:]
            self.target.write_registers(int(hexdata[0:8], 16),
                                        int(hexdata[8:16], 16))
            return b"OK"
        if packet.startswith(b"p"):
            n = int(packet[1:], 16)
            pc, sp = self.target.read_registers()
            if n == 0:
                return b"%08x" % pc
            if n == 1:
                return b"%08x" % sp
            return b"E01"
        if packet.startswith(b"P"):
            n_hex, val_hex = packet[1:].split(b"=")
            n, val = int(n_hex, 16), int(val_hex, 16)
            pc, sp = self.target.read_registers()
            if n == 0:
                self.target.write_registers(val, sp)
            elif n == 1:
                self.target.write_registers(pc, val)
            else:
                return b"E01"
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
            return b"qXfer:features:read+;PacketSize=4000"
        if packet.startswith(b"qXfer:features:read:target.xml:"):
            off_hex, len_hex = packet.rsplit(b":", 1)[-1].split(b",")
            off, length = int(off_hex, 16), int(len_hex, 16)
            xml = target_xml()
            chunk = xml[off:off + length]
            marker = b"l" if off + length >= len(xml) else b"m"
            return marker + chunk
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
