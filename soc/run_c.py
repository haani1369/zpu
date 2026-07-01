import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "linker"))
sys.path.insert(0, HERE)

from zpu import ZPU
import zpld
from zpu_soc import SoC

CLANG = os.path.join(ROOT, "llvm-project/build/bin/clang")
LLC = os.path.join(ROOT, "llvm-project/build/bin/llc")

ENTRY_SP = 0x8000


def _compile(path, workdir):
    name = os.path.splitext(os.path.basename(path))[0]
    ir = os.path.join(workdir, name + ".ll")
    obj = os.path.join(workdir, name + ".o")
    subprocess.run([CLANG, "--target=zpu", "-O2", "-I", HERE,
                    "-emit-llvm", "-S", path, "-o", ir], check=True)
    subprocess.run([LLC, "-mtriple=zpu", "-filetype=obj", ir, "-o", obj],
                   check=True)
    with open(obj, "rb") as f:
        return f.read()


def build(path, ram_size=1 << 16):
    workdir = tempfile.mkdtemp()
    objs = [_compile(os.path.join(HERE, "zpu_console.c"), workdir),
            _compile(path, workdir),
            _compile(os.path.join(ROOT, "runtime", "builtins.c"), workdir),
            _compile(os.path.join(ROOT, "runtime", "softfloat.c"), workdir)]
    image, syms = zpld.link(objs)

    soc = SoC(ram_size=ram_size)
    soc.load(image)
    soc.cpu.sp = ENTRY_SP
    soc.cpu.pc = syms["main"]
    soc.cpu.write_word(ENTRY_SP, len(image))
    return soc


def run(path, feed=None, ram_size=1 << 16, limit=20000000):
    soc = build(path, ram_size=ram_size)
    if feed is not None:
        soc.uart.feed(feed.encode())
    soc.run(limit=limit)
    return soc


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--feed", default=None)
    parser.add_argument("--ram", type=int, default=1 << 16)
    parser.add_argument("--limit", type=int, default=20000000)
    args = parser.parse_args()
    run(args.file, feed=args.feed, ram_size=args.ram, limit=args.limit)
