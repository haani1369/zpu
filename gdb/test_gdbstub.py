import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))
sys.path.insert(0, os.path.dirname(__file__))

from zpu import ZPU
from gdbstub import PacketStream, Target, GDBServer, checksum, frame, target_xml


class FramingTests(unittest.TestCase):
    def test_checksum_matches_spec_example(self):
        self.assertEqual(checksum(b"qSupported"), sum(b"qSupported") & 0xff)

    def test_frame_round_trips_through_packet_stream(self):
        stream = PacketStream()
        stream.feed(frame(b"g"))
        self.assertEqual(stream.next_event(), ("packet", b"g"))

    def test_ack_nak_interrupt_bytes(self):
        stream = PacketStream()
        stream.feed(b"+-\x03")
        self.assertEqual(stream.next_event(), ("ack",))
        self.assertEqual(stream.next_event(), ("nak",))
        self.assertEqual(stream.next_event(), ("interrupt",))
        self.assertIsNone(stream.next_event())

    def test_packet_split_across_feeds(self):
        stream = PacketStream()
        data = frame(b"qSupported")
        stream.feed(data[:3])
        self.assertIsNone(stream.next_event())
        stream.feed(data[3:])
        self.assertEqual(stream.next_event(), ("packet", b"qSupported"))

    def test_bad_checksum_reported(self):
        stream = PacketStream()
        stream.feed(b"$g#00")
        self.assertEqual(stream.next_event(), ("badpacket",))

    def test_two_packets_in_one_feed(self):
        stream = PacketStream()
        stream.feed(frame(b"g") + frame(b"?"))
        self.assertEqual(stream.next_event(), ("packet", b"g"))
        self.assertEqual(stream.next_event(), ("packet", b"?"))
        self.assertIsNone(stream.next_event())


class TargetTests(unittest.TestCase):
    def make(self, asm=None, program=None):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))
        from assembler import assemble
        if program is None:
            program = assemble(asm)
        cpu = ZPU(program, memory_size=4096)
        return Target(cpu)

    def test_step_executes_one_instruction(self):
        t = self.make("    im 5\n    im 3\n    add\n    breakpoint\n")
        self.assertFalse(t.step())
        self.assertEqual(t.cpu.pc, 1)

    def test_step_reports_halt(self):
        t = self.make("    breakpoint\n")
        self.assertTrue(t.step())

    def test_continue_runs_to_halt_with_no_breakpoints(self):
        t = self.make("    im 5\n    im 3\n    add\n    breakpoint\n")
        self.assertEqual(t.continue_(), "halt")
        self.assertTrue(t.cpu.halted)

    def test_continue_stops_at_breakpoint(self):
        t = self.make("    im 5\n    im 3\n    add\n    breakpoint\n")
        t.breakpoints.add(2)
        self.assertEqual(t.continue_(), "break")
        self.assertEqual(t.cpu.pc, 2)

    def test_continue_past_current_breakpoint_does_not_refire(self):
        t = self.make("    im 5\n    im 3\n    add\n    breakpoint\n")
        t.breakpoints.add(0)
        self.assertEqual(t.continue_(), "halt")

    def test_continue_honors_interrupt_check(self):
        t = self.make("    im 5\n    im 3\n    add\n    breakpoint\n")
        t.interrupt_check_interval = 1
        calls = []

        def should_stop():
            calls.append(1)
            return len(calls) >= 2

        self.assertEqual(t.continue_(should_stop=should_stop), "interrupt")

    def test_read_write_memory(self):
        t = self.make("    breakpoint\n")
        t.write_memory(0x100, b"\x01\x02\x03")
        self.assertEqual(t.read_memory(0x100, 3), b"\x01\x02\x03")

    def test_read_write_registers(self):
        t = self.make("    breakpoint\n")
        t.write_registers(pc=4, sp=8)
        self.assertEqual(t.read_registers(), (4, 8))


class GDBServerTests(unittest.TestCase):
    def make(self, asm):
        from assembler import assemble
        program = assemble(asm)
        cpu = ZPU(program, memory_size=4096)
        return GDBServer(sock=None, target=Target(cpu))

    def test_initial_stop_query(self):
        s = self.make("    breakpoint\n")
        self.assertEqual(s.handle_command(b"?"), b"S05")

    def test_read_all_registers(self):
        s = self.make("    breakpoint\n")
        s.target.cpu.pc = 0x10
        s.target.cpu.sp = 0x2000
        self.assertEqual(s.handle_command(b"g"), b"00000010" + b"00002000")

    def test_write_all_registers(self):
        s = self.make("    breakpoint\n")
        reply = s.handle_command(b"G0000001000002000")
        self.assertEqual(reply, b"OK")
        self.assertEqual(s.target.read_registers(), (0x10, 0x2000))

    def test_read_single_register(self):
        s = self.make("    breakpoint\n")
        s.target.cpu.sp = 0x4000
        self.assertEqual(s.handle_command(b"p1"), b"00004000")

    def test_read_unknown_register_is_an_error(self):
        s = self.make("    breakpoint\n")
        self.assertEqual(s.handle_command(b"p9"), b"E01")

    def test_write_single_register(self):
        s = self.make("    breakpoint\n")
        reply = s.handle_command(b"P0=0000abcd")
        self.assertEqual(reply, b"OK")
        self.assertEqual(s.target.read_registers()[0], 0xabcd)

    def test_read_memory(self):
        s = self.make("    breakpoint\n")
        s.target.write_memory(0x20, b"\xde\xad\xbe\xef")
        self.assertEqual(s.handle_command(b"m20,4"), b"deadbeef")

    def test_write_memory(self):
        s = self.make("    breakpoint\n")
        reply = s.handle_command(b"M20,4:deadbeef")
        self.assertEqual(reply, b"OK")
        self.assertEqual(s.target.read_memory(0x20, 4), b"\xde\xad\xbe\xef")

    def test_memory_out_of_bounds_is_an_error(self):
        s = self.make("    breakpoint\n")
        self.assertEqual(s.handle_command(b"m100000,4"), b"E01")

    def test_insert_and_remove_breakpoint(self):
        s = self.make("    breakpoint\n")
        self.assertEqual(s.handle_command(b"Z0,10,1"), b"OK")
        self.assertIn(0x10, s.target.breakpoints)
        self.assertEqual(s.handle_command(b"z0,10,1"), b"OK")
        self.assertNotIn(0x10, s.target.breakpoints)

    def test_continue_to_halt(self):
        s = self.make("    im 5\n    im 3\n    add\n    breakpoint\n")
        self.assertEqual(s.handle_command(b"c"), b"W00")

    def test_continue_to_breakpoint(self):
        s = self.make("    im 5\n    im 3\n    add\n    breakpoint\n")
        s.target.breakpoints.add(2)
        self.assertEqual(s.handle_command(b"c"), b"S05")

    def test_continue_at_new_address(self):
        s = self.make("    breakpoint\n    im 1\n    breakpoint\n")
        self.assertEqual(s.handle_command(b"c1"), b"W00")

    def test_step_reply(self):
        s = self.make("    im 5\n    breakpoint\n")
        self.assertEqual(s.handle_command(b"s"), b"S05")
        self.assertEqual(s.target.cpu.pc, 2)

    def test_step_to_halt_reply(self):
        s = self.make("    breakpoint\n")
        self.assertEqual(s.handle_command(b"s"), b"W00")

    def test_qsupported_advertises_target_description(self):
        s = self.make("    breakpoint\n")
        reply = s.handle_command(b"qSupported:multiprocess+")
        self.assertIn(b"qXfer:features:read+", reply)

    def test_target_xml_transfer(self):
        s = self.make("    breakpoint\n")
        xml = target_xml()
        reply = s.handle_command(
            b"qXfer:features:read:target.xml:0,%x" % len(xml))
        self.assertEqual(reply, b"l" + xml)

    def test_target_xml_transfer_is_chunked(self):
        s = self.make("    breakpoint\n")
        xml = target_xml()
        reply = s.handle_command(
            b"qXfer:features:read:target.xml:0,4")
        self.assertEqual(reply, b"m" + xml[:4])

    def test_unknown_packet_is_unsupported(self):
        s = self.make("    breakpoint\n")
        self.assertEqual(s.handle_command(b"vMustReplyEmpty"), b"")

    def test_malformed_packet_does_not_raise(self):
        s = self.make("    breakpoint\n")
        self.assertEqual(s.handle_command(b"m"), b"E01")
        self.assertEqual(s.handle_command(b"P"), b"E01")


class GDBServerSocketTests(unittest.TestCase):
    def test_full_session_over_a_real_socket_pair(self):
        import socket
        from assembler import assemble

        client, server_sock = socket.socketpair()
        program = assemble("    im 5\n    im 3\n    add\n    breakpoint\n")
        cpu = ZPU(program, memory_size=4096)
        server = GDBServer(server_sock, Target(cpu))

        client.sendall(frame(b"g"))
        server.serve_one()
        self.assertEqual(client.recv(1), b"+")
        reply = client.recv(4096)
        self.assertTrue(reply.startswith(b"$"))

        client.close()
        server_sock.close()


if __name__ == "__main__":
    unittest.main()
