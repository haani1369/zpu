import os
import sys
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))

from assembler import assemble
from zpu import ZPU, MASK

CLANG = os.path.join(ROOT, "llvm-project/build/bin/clang")
LLC = os.path.join(ROOT, "llvm-project/build/bin/llc")
RUNTIME = (open(os.path.join(ROOT, "runtime/builtins.c")).read() + "\n" +
           open(os.path.join(ROOT, "runtime/softfloat.c")).read())


def code_lines(asm):
    lines = []
    for raw in asm.splitlines():
        text = raw.split(";", 1)[0].rstrip()
        stripped = text.strip()
        if not stripped or stripped == "__zpu_fp:":
            continue
        if stripped.startswith("."):
            if stripped.endswith(":"):
                lines.append(stripped)
            continue
        lines.append(text if stripped.endswith(":") else "    " + stripped)
    return "\n".join(lines)


def run(path):
    work = tempfile.mkdtemp()
    csrc = os.path.join(work, "prog.c")
    ir = os.path.join(work, "prog.ll")
    open(csrc, "w").write(open(path).read() + "\n" + RUNTIME)
    subprocess.run([CLANG, "--target=zpu", "-O2", "-fno-builtin",
                    "-emit-llvm", "-S", csrc, "-o", ir], check=True)
    asm = subprocess.run([LLC, "-mtriple=zpu", ir, "-o", "-"],
                         check=True, capture_output=True, text=True).stdout
    program = ("    im 0\n    im done\n    im main\n    poppc\n" +
               code_lines(asm) +
               "\ndone:\n    breakpoint\n__zpu_fp:\n    nop\n")
    cpu = ZPU(assemble(program), memory_size=400000)
    cpu.run(limit=80000000)
    return cpu.stack()[0] & MASK


if __name__ == "__main__":
    for path in sys.argv[1:]:
        print("%-14s -> %d" % (os.path.basename(path), run(path)))
