; brings up the virtio console device (virtio0, a fixed mmio slot at
; 0x10020000 -- see docs/zpu_memmap.txt) and sends one message.
;
; data lives well above this program's code, in ram that nothing else
; uses: the descriptor table at 0x1000, the avail ring at 0x1020, the
; used ring at 0x1040, the message itself at 0x1080.

; bring the device up: acknowledge, driver, features negotiated (this
; device offers none), driver ready.
    im 1            ; acknowledge
    im 0x10020070      ; status
    store
    im 3            ; acknowledge | driver
    im 0x10020070
    store
    im 11           ; acknowledge | driver | features_ok
    im 0x10020070
    store
    im 15           ; acknowledge | driver | features_ok | driver_ok
    im 0x10020070
    store

; configure the transmitq (queue index 1) with a 4-entry virtqueue.
    im 1
    im 0x10020030      ; queuesel
    store
    im 4
    im 0x10020038      ; queuenum
    store
    im 0x1000
    im 0x10020080      ; queuedesclow
    store
    im 0x1020
    im 0x10020090      ; queueavaillow
    store
    im 0x1040
    im 0x100200a0      ; queueusedlow
    store
    im 1
    im 0x10020044      ; queueready
    store

; descriptor 0: points at the message, no next, device-read only.
    im 0x1080
    im 0x1000       ; desc[0].addr
    store
    im 0
    im 0x1004       ; desc[0].addr_hi
    store
    im 16
    im 0x1008       ; desc[0].len
    store
    im 0
    im 0x100c       ; desc[0].flags
    store
    im 0
    im 0x1010       ; desc[0].next
    store

; the message itself, "hello from zpu!\n", four words.
    im 0x68656c6c
    im 0x1080
    store
    im 0x6f206672
    im 0x1084
    store
    im 0x6f6d207a
    im 0x1088
    store
    im 0x7075210a
    im 0x108c
    store

; publish descriptor 0 on the avail ring and notify the device.
    im 0
    im 0x1028       ; avail.ring[0]
    store
    im 1
    im 0x1024       ; avail.idx
    store
    im 1
    im 0x10020050      ; queuenotify
    store

; poll the used ring until the device completes the chain.
poll:
    im 0x1044       ; used.idx
    load
    im 1
    sub
    im poll
    neqbranch

    breakpoint
