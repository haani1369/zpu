import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOC = os.path.join(ROOT, "soc")
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "linker"))
sys.path.insert(0, SOC)

import zpld
from zpu_soc import SoC

CLANG = os.path.join(ROOT, "llvm-project/build/bin/clang")
LLC = os.path.join(ROOT, "llvm-project/build/bin/llc")

ENTRY_SP = 0x8000

LIBC_SOURCES = ["string.c", "ctype.c", "stdlib.c", "stdio.c"]


def _compile(path, workdir, include_dirs):
    name = os.path.splitext(os.path.basename(path))[0] + "-" + \
        str(abs(hash(path)) % 100000)
    ir = os.path.join(workdir, name + ".ll")
    obj = os.path.join(workdir, name + ".o")
    include_flags = []
    for d in include_dirs:
        include_flags += ["-I", d]
    subprocess.run([CLANG, "--target=zpu", "-O2", "-fno-jump-tables"] +
                    include_flags +
                    ["-emit-llvm", "-S", path, "-o", ir], check=True)
    subprocess.run([LLC, "-mtriple=zpu", "-filetype=obj", ir, "-o", obj],
                   check=True)
    with open(obj, "rb") as f:
        return f.read()


def build(path, ram_size=1 << 18):
    workdir = tempfile.mkdtemp()
    include_dirs = [HERE, SOC]
    sources = [os.path.join(SOC, "zpu_console.c")]
    sources += [os.path.join(HERE, name) for name in LIBC_SOURCES]
    sources.append(path)
    sources += [os.path.join(ROOT, "runtime", "builtins.c"),
                os.path.join(ROOT, "runtime", "softfloat.c")]
    objs = [_compile(src, workdir, include_dirs) for src in sources]
    image, syms = zpld.link(objs)

    soc = SoC(ram_size=ram_size)
    soc.load(image)
    soc.cpu.sp = ENTRY_SP
    soc.cpu.pc = syms["main"]
    soc.cpu.write_word(ENTRY_SP, len(image))
    return soc


def run(path, feed=None, ram_size=1 << 18, limit=20000000):
    soc = build(path, ram_size=ram_size)
    output = bytearray()
    soc.uart.on_output = output.extend
    if feed is not None:
        soc.uart.feed(feed.encode() if isinstance(feed, str) else feed)
    try:
        soc.run(limit=limit)
    except Exception:
        pass
    return soc, bytes(output)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--feed", default=None)
    parser.add_argument("--ram", type=int, default=1 << 18)
    parser.add_argument("--limit", type=int, default=20000000)
    args = parser.parse_args()
    soc, output = run(args.file, feed=args.feed, ram_size=args.ram,
                      limit=args.limit)
    sys.stdout.write(output.decode(errors="replace"))
    sys.exit(soc.cpu.stack()[0] if soc.cpu.halted else 1)
