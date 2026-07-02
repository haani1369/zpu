#include "stdio.h"
#include "../soc/zpu_console.h"
#include <stdarg.h>

int putchar(int c) {
    zpu_console_putc((char)c);
    return c;
}

int getchar(void) {
    return zpu_console_getc();
}

int puts(const char *s) {
    zpu_console_puts(s);
    zpu_console_putc('\n');
    return 0;
}

/* forms the digits of v in the given base into out (no sign, no padding),
   most significant digit first, and returns how many digits were written */
static int format_digits(char *out, unsigned int v, int base) {
    char tmp[12];
    int n = 0;
    if (v == 0) {
        tmp[n++] = '0';
    } else {
        while (v) {
            int d = (int)(v % (unsigned int)base);
            tmp[n++] = (char)(d < 10 ? '0' + d : 'a' + d - 10);
            v /= (unsigned int)base;
        }
    }
    for (int i = 0; i < n; i++)
        out[i] = tmp[n - 1 - i];
    return n;
}

/* The printf/sprintf/snprintf family shares this parsing loop via a macro
   rather than a shared function taking a va_list and a callback: this
   backend is new enough that passing a va_list to a helper function, and
   dispatching output through a stored function pointer, both interact
   badly with it once combined in the same call chain. Duplicating the loop
   through EMIT sidesteps that entirely, at the cost of one copy of the
   format grammar per entry point instead of one shared implementation.
   Leaves `count` set in the caller's scope; does not return on its own, so
   each caller can finish up (null-terminate a buffer) before returning. */
#define VFORMAT_BODY(EMIT)                                                  \
    while (*fmt) {                                                          \
        if (*fmt != '%') {                                                  \
            EMIT(*fmt++);                                                   \
            count++;                                                        \
            continue;                                                       \
        }                                                                    \
        fmt++;                                                              \
        if (!*fmt)                                                          \
            break;                                                          \
        int left_align = 0;                                                 \
        int zero_pad = 0;                                                   \
        for (;;) {                                                          \
            if (*fmt == '-') {                                              \
                left_align = 1;                                             \
                fmt++;                                                      \
            } else if (*fmt == '0') {                                       \
                zero_pad = 1;                                               \
                fmt++;                                                      \
            } else {                                                        \
                break;                                                      \
            }                                                               \
        }                                                                    \
        int width = 0;                                                      \
        while (*fmt >= '0' && *fmt <= '9')                                  \
            width = width * 10 + (*fmt++ - '0');                            \
        char digits[12];                                                    \
        const char *sign = "";                                             \
        int signlen = 0;                                                    \
        const char *digitsrc = digits;                                      \
        int digitlen = 0;                                                   \
        char conv = *fmt;                                                   \
        if (conv == 'd' || conv == 'i') {                                   \
            int v = va_arg(ap, int);                                        \
            if (v < 0) {                                                    \
                sign = "-";                                                 \
                signlen = 1;                                                \
                digitlen = format_digits(digits, (unsigned int)(-v), 10);   \
            } else {                                                        \
                digitlen = format_digits(digits, (unsigned int)v, 10);      \
            }                                                                \
        } else if (conv == 'u') {                                           \
            digitlen = format_digits(digits, va_arg(ap, unsigned int), 10); \
        } else if (conv == 'x') {                                           \
            digitlen = format_digits(digits, va_arg(ap, unsigned int), 16); \
        } else if (conv == 'c') {                                           \
            digits[0] = (char)va_arg(ap, int);                              \
            digitlen = 1;                                                   \
        } else if (conv == 's') {                                           \
            digitsrc = va_arg(ap, const char *);                            \
            while (digitsrc[digitlen])                                     \
                digitlen++;                                                 \
        } else if (conv == '%') {                                          \
            digits[0] = '%';                                                \
            digitlen = 1;                                                   \
        } else {                                                            \
            EMIT('%');                                                      \
            EMIT(conv);                                                     \
            count += 2;                                                    \
            fmt++;                                                          \
            continue;                                                      \
        }                                                                    \
        int pad = width - (signlen + digitlen);                            \
        if (pad < 0)                                                        \
            pad = 0;                                                        \
        if (left_align) {                                                   \
            for (int k = 0; k < signlen; k++) EMIT(sign[k]);                \
            for (int k = 0; k < digitlen; k++) EMIT(digitsrc[k]);           \
            for (int k = 0; k < pad; k++) EMIT(' ');                        \
        } else if (zero_pad) {                                              \
            for (int k = 0; k < signlen; k++) EMIT(sign[k]);                \
            for (int k = 0; k < pad; k++) EMIT('0');                        \
            for (int k = 0; k < digitlen; k++) EMIT(digitsrc[k]);           \
        } else {                                                            \
            for (int k = 0; k < pad; k++) EMIT(' ');                        \
            for (int k = 0; k < signlen; k++) EMIT(sign[k]);                \
            for (int k = 0; k < digitlen; k++) EMIT(digitsrc[k]);           \
        }                                                                    \
        count += signlen + digitlen + pad;                                 \
        fmt++;                                                              \
    }

int printf(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    int count = 0;
#define EMIT_CONSOLE(c) zpu_console_putc(c)
    VFORMAT_BODY(EMIT_CONSOLE)
#undef EMIT_CONSOLE
    va_end(ap);
    return count;
}

int sprintf(char *buf, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    int count = 0;
    unsigned int pos = 0;
#define EMIT_UNBOUNDED(c) (buf[pos++] = (c))
    VFORMAT_BODY(EMIT_UNBOUNDED)
#undef EMIT_UNBOUNDED
    va_end(ap);
    buf[pos] = 0;
    return count;
}

int snprintf(char *buf, unsigned int size, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    int count = 0;
    unsigned int pos = 0;
    unsigned int limit = size > 0 ? size - 1 : 0;
#define EMIT_BOUNDED(c) do { if (pos < limit) buf[pos] = (c); pos++; } while (0)
    VFORMAT_BODY(EMIT_BOUNDED)
#undef EMIT_BOUNDED
    va_end(ap);
    if (size > 0)
        buf[pos < limit ? pos : limit] = 0;
    return count;
}
