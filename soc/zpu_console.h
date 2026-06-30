#ifndef ZPU_CONSOLE_H
#define ZPU_CONSOLE_H

void zpu_console_init(void);
void zpu_console_putc(char c);
void zpu_console_write(const char *data, int len);
void zpu_console_puts(const char *s);
int zpu_console_getc(void);

#endif
