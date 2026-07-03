zpu: a full software stack for zylin's zpu

zpu is a small 32-bit stack-based instruction set designed by zylin,
originally for jtag debugging hardware. it's had some tooling over the
years, but nothing substantially worked on in the last decade or so.
this project builds a modern, complete software stack for it instead:
a python reference simulator and assembler, a real llvm backend (clang
and llc both work), a linker, a gdb remote-serial stub, a small
system-on-chip emulator (uart, a video framebuffer, virtio), and a
small freestanding c library.


why

a stack machine with no general registers removes register allocation,
one of the harder parts of a normal compiler backend, while everything
else a real toolchain needs -- calling conventions, relocations,
multi-word arithmetic, software floating point, a linker, a libc --
stays fully real. that keeps each piece small enough to read start to
finish without making any of it a toy.

targeting an isa with no actively maintained toolchain also means
there's nothing to fall back on: every relocation type, every calling
convention detail, every libc primitive has to actually be built
rather than inherited from an existing compiler or runtime.


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

  - a qemu machine and an fpga build targeting the same fixed physical
    memory map the python soc already implements, so the same
    compiled binaries run unchanged across all three
  - a multicore variant of the soc
  - rounding out the linker and c library toward a more complete,
    general-purpose toolchain
