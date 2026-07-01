; brings up the terminal by polling uart0 (a fixed mmio slot at
; 0x10000000 -- see docs/zpu_memmap.txt) and sends one message,
; a byte at a time, the way any uart driver has to. compare with
; hello_virtio_console.s, which sends the same message over the
; secondary channel -- this is the whole point of a plain uart:
; no descriptor table, no rings, just poll and write.

poll0:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll0
    eqbranch
    im 104            ; 'h'
    im 0x10000000       ; data
    store

poll1:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll1
    eqbranch
    im 101            ; 'e'
    im 0x10000000       ; data
    store

poll2:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll2
    eqbranch
    im 108            ; 'l'
    im 0x10000000       ; data
    store

poll3:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll3
    eqbranch
    im 108            ; 'l'
    im 0x10000000       ; data
    store

poll4:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll4
    eqbranch
    im 111            ; 'o'
    im 0x10000000       ; data
    store

poll5:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll5
    eqbranch
    im 32            ; ' '
    im 0x10000000       ; data
    store

poll6:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll6
    eqbranch
    im 102            ; 'f'
    im 0x10000000       ; data
    store

poll7:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll7
    eqbranch
    im 114            ; 'r'
    im 0x10000000       ; data
    store

poll8:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll8
    eqbranch
    im 111            ; 'o'
    im 0x10000000       ; data
    store

poll9:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll9
    eqbranch
    im 109            ; 'm'
    im 0x10000000       ; data
    store

poll10:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll10
    eqbranch
    im 32            ; ' '
    im 0x10000000       ; data
    store

poll11:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll11
    eqbranch
    im 122            ; 'z'
    im 0x10000000       ; data
    store

poll12:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll12
    eqbranch
    im 112            ; 'p'
    im 0x10000000       ; data
    store

poll13:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll13
    eqbranch
    im 117            ; 'u'
    im 0x10000000       ; data
    store

poll14:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll14
    eqbranch
    im 33            ; '!'
    im 0x10000000       ; data
    store

poll15:
    im 0x10000004       ; status
    load
    im 2            ; tx_ready
    and
    im poll15
    eqbranch
    im 10            ; '\n'
    im 0x10000000       ; data
    store

    breakpoint
