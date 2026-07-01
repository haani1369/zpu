#include "zpu_console.h"

int main(void) {
    zpu_console_init();
    for (;;) {
        int c = zpu_console_getc();
        if (c == 0x04)
            break;
        zpu_console_putc((char)c);
    }
    return 0;
}
