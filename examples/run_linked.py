import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))

from zpu import ZPU, MASK

CLANG = os.path.join(ROOT, "llvm-project/build/bin/clang")

SINGLE_FILE = {
    "fib.c": 75025, "gcd.c": 21, "sieve.c": 25, "sort.c": 109,
    "collatz.c": 111, "ackermann.c": 61, "factorial.c": 640000,
    "sqrt.c": 141421, "euler.c": 271828,
}
MULTI_FILE = (("multi_helper.c", "multi_main.c"), 21)


def run_image(path, limit=80000000):
    cpu = ZPU(open(path, "rb").read(), memory_size=400000)
    cpu.run(limit=limit)
    return cpu.stack()[0] & MASK


def run_single(name, workdir):
    out = os.path.join(workdir, name + ".bin")
    subprocess.run([CLANG, "--target=zpu", "-O2", os.path.join(HERE, name),
                    "-o", out], check=True)
    return run_image(out)


def run_multi(names, workdir):
    objs = []
    for name in names:
        obj = os.path.join(workdir, name + ".o")
        subprocess.run([CLANG, "--target=zpu", "-O2", "-c",
                        os.path.join(HERE, name), "-o", obj], check=True)
        objs.append(obj)
    out = os.path.join(workdir, "multi.bin")
    subprocess.run([CLANG, "--target=zpu", *objs, "-o", out], check=True)
    return run_image(out)


def main():
    failures = 0
    with tempfile.TemporaryDirectory() as workdir:
        for name, expected in SINGLE_FILE.items():
            got = run_single(name, workdir)
            ok = got == expected
            failures += not ok
            print("%-14s -> %-10d %s" % (name, got, "ok" if ok else
                                         "expected %d" % expected))

        names, expected = MULTI_FILE
        got = run_multi(names, workdir)
        ok = got == expected
        failures += not ok
        print("%-14s -> %-10d %s" % ("+".join(names), got, "ok" if ok else
                                     "expected %d" % expected))

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
