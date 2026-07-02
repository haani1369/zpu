zpu: a stack machine, built from the isa up

zpu is a small, from-scratch 32-bit stack-based instruction set, with a
full software stack built for it: a python reference simulator and
assembler, a real llvm backend (clang and llc both work), a linker, a
gdb remote-serial stub, a small system-on-chip emulator (uart, a video
framebuffer, virtio), and a small freestanding c library.


why

mostly to actually understand, rather than just use, everything between
"c source" and "bytes executing on a cpu": how an instruction set gets
chosen, how a compiler backend lowers real code to it, how a linker
resolves symbols across object files, how a libc's malloc and printf
work with no os underneath. every layer here is small enough to read
end to end, which most real toolchains aren't.

nothing here is meant to be fast, production-grade, or novel as an
architecture -- it's a hobby project. if anything about it is worth
noting, it's that it's a genuinely complete, working stack rather than
one clever piece of one layer.


layout

    sim/            the reference vm and assembler
    llvm-project/   llvm/clang, with a zpu backend added (branch zpu)
    linker/         zpld.py, the elf-ish object linker
    runtime/        compiler-emitted support calls (64-bit ops, soft float)
    libc/           string.h, ctype.h, a small stdlib.h and stdio.h
    soc/            a uart + video + virtio system-on-chip, in python
    gdb/            a gdb remote serial protocol stub for the simulator
    examples/       small c programs, and two ways to compile and run them
    docs/           a design doc for each piece above


usage

build the compiler once:

    cmake -G Ninja -S llvm-project/llvm -B llvm-project/build \
      -DLLVM_TARGETS_TO_BUILD="" -DLLVM_EXPERIMENTAL_TARGETS_TO_BUILD="ZPU" \
      -DLLVM_ENABLE_PROJECTS="clang" -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++
    ninja -C llvm-project/build -j4 clang llc

then compile and run a c program on the simulated soc:

    python3 soc/run_c.py soc/bounce.c --interactive

one frame of that demo -- an ascii ball bouncing over the uart, no
floating point, so it runs in seconds:

    --------------------------
    |                        |
    |               O        |
    |                        |
    |                        |
    |                        |
    |                        |
    |                        |
    |                        |
    --------------------------
    frame 15/40

see docs/zpu_soc.txt and docs/zpu_libc.txt for the rest: soc/hello.c
and soc/echo.c exercise the terminal driver, soc/mandelbrot.c renders
to the video framebuffer using the libc's malloc/printf and
double-precision software float.


what's next

  - root-cause the single-precision soft-float bug noted in
    docs/zpu_soc.txt (double works; float hangs)
  - a qemu machine and an fpga build targeting the same fixed physical
    memory map the python soc already implements (docs/zpu_memmap.txt),
    so the same compiled binaries run unchanged on all three
  - archive support in the linker, so a program only pulls in the
    runtime/libc functions it actually calls instead of all of them
