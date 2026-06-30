import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import run_c

CLANG_MISSING = not os.path.exists(run_c.CLANG)


@unittest.skipIf(CLANG_MISSING, "zpu clang is not built")
class HelloConsoleTests(unittest.TestCase):
    def test_output_and_echo(self):
        output = bytearray()
        soc = run_c.build(os.path.join(os.path.dirname(__file__), "hello.c"))
        soc.console.on_output = output.extend
        soc.console.feed(b"abcde")
        soc.run(limit=2000000)
        self.assertEqual(bytes(output), b"hello from zpu (c)!\nabcde\n")


if __name__ == "__main__":
    unittest.main()
