#include "zpu_console.h"

int main(void) {
    zpu_console_init();
    zpu_console_puts("hello from zpu (c)!\n");
    for (int i = 0; i < 5; i++)
        zpu_console_putc(zpu_console_getc());
    zpu_console_putc('\n');
    return 0;
}
