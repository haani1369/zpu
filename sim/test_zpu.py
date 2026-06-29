import os

from assembler import assemble
from zpu import ZPU


def run(*lines):
    cpu = ZPU(assemble("\n".join(lines)))
    cpu.run()
    return cpu


def test_immediate():
    assert assemble("im 128") == bytes([0x81, 0x80])
    assert run("im 128", "breakpoint").stack() == [128]


def test_negative_immediate():
    assert run("im -3", "breakpoint").stack() == [0xfffffffd]


def test_arithmetic():
    assert run("im 5", "im 3", "add", "breakpoint").stack() == [8]


def test_dup_and_drop():
    assert run("im 7", "loadsp 0", "breakpoint").stack() == [7, 7]
    assert run("im 7", "im 9", "storesp 0", "breakpoint").stack() == [7]


def test_memory():
    cpu = run("im 0x55", "im 0x200", "store", "im 0x200", "load",
              "breakpoint")
    assert cpu.stack() == [0x55]
    assert cpu.read_word(0x200) == 0x55


def test_basic_bench():
    path = os.path.join(os.path.dirname(__file__), "basic.s")
    with open(path) as f:
        cpu = run(f.read())
    assert cpu.stack() == [0xBEEF, 200, 100, 295]
    assert cpu.read_word(0x200) == 0x55


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


if __name__ == "__main__":
    main()
