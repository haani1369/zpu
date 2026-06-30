zpu example programs

small c programs compiled with the zpu llvm backend and run on the python
simulator in ../sim. each program's main returns an int that run.py prints.

build the compiler and the simulator first (see the top-level project), then:

    python3 run.py fib.c
    python3 run.py *.c

for each file, run.py compiles it with clang --target=zpu, appends the software
runtime in ../runtime (the 64-bit integer and floating-point helpers the
backend calls), assembles the result with the simulator's assembler, then runs
main on the simulated zpu and prints its return value.

expected output:

    fib.c          75025     fib(25)
    gcd.c          21        gcd(1071, 462)
    sieve.c        25        primes below 100
    sort.c         109       bubble sort, a[0] * 100 + a[7]
    collatz.c      111       collatz steps starting from 27
    ackermann.c    61        ackermann(3, 3)
    factorial.c    640000    low six digits of 20! (64-bit)
    sqrt.c         141421    sqrt(2) * 100000, newton's method (float)
    euler.c        271828    e * 100000, taylor series (float)

these run through the reference flow: clang and llc emit text assembly which
the python assembler in ../sim turns into a program image. the separate object
and linker path (llc -filetype=obj with ../linker) is for multi-file programs.
