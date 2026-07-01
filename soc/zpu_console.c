#include "zpu_console.h"

#define UART0_BASE 0x10000000u
#define UART_DATA 0x00
#define UART_STATUS 0x04
#define UART_STATUS_RX_READY 1u
#define UART_STATUS_TX_READY 2u

#define reg(offset) (*(volatile unsigned int *)(UART0_BASE + (offset)))

void zpu_console_init(void) {
}

void zpu_console_putc(char c) {
    while (!(reg(UART_STATUS) & UART_STATUS_TX_READY))
        ;
    reg(UART_DATA) = (unsigned char)c;
}

void zpu_console_write(const char *data, int len) {
    for (int i = 0; i < len; i++)
        zpu_console_putc(data[i]);
}

void zpu_console_puts(const char *s) {
    while (*s)
        zpu_console_putc(*s++);
}

int zpu_console_getc(void) {
    while (!(reg(UART_STATUS) & UART_STATUS_RX_READY))
        ;
    return (int)(reg(UART_DATA) & 0xff);
}
