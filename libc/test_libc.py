import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "soc"))

import run_c

CLANG_MISSING = not os.path.exists(run_c.CLANG)


@unittest.skipIf(CLANG_MISSING, "zpu clang is not built")
class LibcTests(unittest.TestCase):
    def _run(self, name, feed=None):
        path = os.path.join(HERE, name)
        soc = run_c.build(path, ram_size=1 << 18)
        output = bytearray()
        soc.uart.on_output = output.extend
        if feed is not None:
            soc.uart.feed(feed.encode())
        try:
            soc.run(limit=20000000)
        except Exception:
            pass
        return soc, bytes(output).decode(errors="replace")

    def test_string(self):
        soc, output = self._run("test_string.c")
        self.assertIn("ALL PASS", output, output)

    def test_ctype(self):
        soc, output = self._run("test_ctype.c")
        self.assertIn("ALL PASS", output, output)

    def test_stdlib(self):
        soc, output = self._run("test_stdlib.c")
        self.assertIn("ALL PASS", output, output)

    def test_stdio(self):
        soc, output = self._run("test_stdio.c", feed="Q")
        self.assertIn("PUTS-LINE", output, output)
        self.assertIn("PRINTF 99 abc z", output, output)
        self.assertIn("ALL PASS", output, output)


if __name__ == "__main__":
    unittest.main()
