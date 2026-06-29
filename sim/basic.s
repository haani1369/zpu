; Core ISA test bench. Each comment shows the stack, top first, after the
; line runs. Final stack, top first: 0xBEEF 200 100 295.
; Memory word at 0x200 holds 0x55.

; immediates and signed addition
    im 5            ; 5
    im 3            ; 3 5
    add             ; 8
    im -3           ; FFFFFFFD 8
    add             ; 5

; bitwise or, and, not
    im 0xF0         ; F0 5
    or              ; F5
    im 0x0F         ; 0F F5
    and             ; 05
    not             ; FFFFFFFA
    not             ; 05

; bit reversal round trip
    flip            ; A0000000
    flip            ; 05

; duplicate and add
    loadsp 0        ; 5 5
    add             ; 10

; store then load through memory
    im 0x55         ; 55 10
    im 0x200        ; 200 55 10
    store           ; 10              (mem[0x200] = 0x55)
    im 0x200        ; 200 10
    load            ; 55 10
    add             ; 95

; SP-relative offsets
    im 100          ; 100 95
    im 200          ; 200 100 95
    loadsp 8        ; 95 200 100 95
    addsp 4         ; 295 200 100 95
    storesp 12      ; 200 100 295

; push and restore SP
    pushsp          ; SP 200 100 295
    popsp           ; 200 100 295

; computed jump over a trap
    nop
    im done
    poppc
    im 0xDEAD       ; skipped
    breakpoint      ; skipped
done:
    im 0xBEEF       ; BEEF 200 100 295
    breakpoint
