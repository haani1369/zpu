#ifndef ZPU_STDIO_H
#define ZPU_STDIO_H

int putchar(int c);
int getchar(void);
int puts(const char *s);

int printf(const char *fmt, ...);
int sprintf(char *buf, const char *fmt, ...);
int snprintf(char *buf, unsigned int size, const char *fmt, ...);

#endif
