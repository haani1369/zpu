#include "zpu_virtio_console.h"

#define CONSOLE_BASE 0x10000u

#define REG_QUEUESEL 0x030
#define REG_QUEUENUM 0x038
#define REG_QUEUEREADY 0x044
#define REG_QUEUENOTIFY 0x050
#define REG_STATUS 0x070
#define REG_QUEUEDESCLOW 0x080
#define REG_QUEUEAVAILLOW 0x090
#define REG_QUEUEUSEDLOW 0x0a0

#define STATUS_ACKNOWLEDGE 1u
#define STATUS_DRIVER 2u
#define STATUS_DRIVER_OK 4u
#define STATUS_FEATURES_OK 8u

#define RECEIVEQ 0u
#define TRANSMITQ 1u

#define DESC_FLAG_WRITE 2u

#define reg(offset) (*(volatile unsigned int *)(CONSOLE_BASE + (offset)))

typedef struct {
    unsigned int addr;
    unsigned int addr_hi;
    unsigned int len;
    unsigned int flags;
    unsigned int next;
} vq_desc;

typedef struct {
    unsigned int flags;
    unsigned int idx;
    unsigned int ring[1];
} vq_avail;

typedef struct {
    unsigned int id;
    unsigned int len;
} vq_used_elem;

typedef struct {
    unsigned int flags;
    unsigned int idx;
    vq_used_elem ring[1];
} vq_used;

static volatile vq_desc tx_desc;
static volatile vq_avail tx_avail;
static volatile vq_used tx_used;
static unsigned int tx_used_seen;

static volatile vq_desc rx_desc;
static volatile vq_avail rx_avail;
static volatile vq_used rx_used;
static unsigned int rx_used_seen;
static volatile char rx_buf[64];
static int rx_pos;
static int rx_len;

static void configure_queue(unsigned int index, volatile vq_desc *desc,
                            volatile vq_avail *avail, volatile vq_used *used) {
    reg(REG_QUEUESEL) = index;
    reg(REG_QUEUENUM) = 1;
    reg(REG_QUEUEDESCLOW) = (unsigned int)desc;
    reg(REG_QUEUEAVAILLOW) = (unsigned int)avail;
    reg(REG_QUEUEUSEDLOW) = (unsigned int)used;
    reg(REG_QUEUEREADY) = 1;
}

static void post_receive(void) {
    rx_desc.addr = (unsigned int)rx_buf;
    rx_desc.addr_hi = 0;
    rx_desc.len = sizeof(rx_buf);
    rx_desc.flags = DESC_FLAG_WRITE;
    rx_desc.next = 0;
    rx_avail.ring[0] = 0;
    rx_avail.idx = rx_avail.idx + 1;
    reg(REG_QUEUENOTIFY) = RECEIVEQ;
}

void zpu_virtio_console_init(void) {
    reg(REG_STATUS) = STATUS_ACKNOWLEDGE;
    reg(REG_STATUS) = STATUS_ACKNOWLEDGE | STATUS_DRIVER;
    reg(REG_STATUS) = STATUS_ACKNOWLEDGE | STATUS_DRIVER | STATUS_FEATURES_OK;

    configure_queue(TRANSMITQ, &tx_desc, &tx_avail, &tx_used);
    configure_queue(RECEIVEQ, &rx_desc, &rx_avail, &rx_used);

    reg(REG_STATUS) = STATUS_ACKNOWLEDGE | STATUS_DRIVER | STATUS_FEATURES_OK
                      | STATUS_DRIVER_OK;

    tx_used_seen = 0;
    rx_used_seen = 0;
    rx_pos = 0;
    rx_len = 0;
    post_receive();
}

void zpu_virtio_console_write(const char *data, int len) {
    tx_desc.addr = (unsigned int)data;
    tx_desc.addr_hi = 0;
    tx_desc.len = (unsigned int)len;
    tx_desc.flags = 0;
    tx_desc.next = 0;
    tx_avail.ring[0] = 0;
    tx_avail.idx = tx_avail.idx + 1;
    reg(REG_QUEUENOTIFY) = TRANSMITQ;
    while (tx_used.idx == tx_used_seen)
        ;
    tx_used_seen = tx_used.idx;
}

void zpu_virtio_console_putc(char c) {
    volatile char buf;
    buf = c;
    zpu_virtio_console_write((const char *)&buf, 1);
}

void zpu_virtio_console_puts(const char *s) {
    while (*s)
        zpu_virtio_console_putc(*s++);
}

int zpu_virtio_console_getc(void) {
    if (rx_pos == rx_len) {
        while (rx_used.idx == rx_used_seen)
            ;
        rx_used_seen = rx_used.idx;
        rx_len = (int)rx_used.ring[0].len;
        rx_pos = 0;
    }
    char c = rx_buf[rx_pos++];
    if (rx_pos == rx_len)
        post_receive();
    return (int)(unsigned char)c;
}
