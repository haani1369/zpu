#include "string.h"

void *memcpy(void *dst, const void *src, unsigned int n) {
    unsigned char *d = dst;
    const unsigned char *s = src;
    for (unsigned int i = 0; i < n; i++)
        d[i] = s[i];
    return dst;
}

void *memmove(void *dst, const void *src, unsigned int n) {
    unsigned char *d = dst;
    const unsigned char *s = src;
    if (d < s) {
        for (unsigned int i = 0; i < n; i++)
            d[i] = s[i];
    } else {
        for (unsigned int i = n; i > 0; i--)
            d[i - 1] = s[i - 1];
    }
    return dst;
}

void *memset(void *dst, int c, unsigned int n) {
    unsigned char *d = dst;
    for (unsigned int i = 0; i < n; i++)
        d[i] = (unsigned char)c;
    return dst;
}

int memcmp(const void *a, const void *b, unsigned int n) {
    const unsigned char *pa = a;
    const unsigned char *pb = b;
    for (unsigned int i = 0; i < n; i++)
        if (pa[i] != pb[i])
            return (int)pa[i] - (int)pb[i];
    return 0;
}

void *memchr(const void *s, int c, unsigned int n) {
    const unsigned char *p = s;
    for (unsigned int i = 0; i < n; i++)
        if (p[i] == (unsigned char)c)
            return (void *)(p + i);
    return 0;
}

unsigned int strlen(const char *s) {
    unsigned int n = 0;
    while (s[n])
        n++;
    return n;
}

char *strcpy(char *dst, const char *src) {
    char *d = dst;
    while ((*d++ = *src++))
        ;
    return dst;
}

char *strncpy(char *dst, const char *src, unsigned int n) {
    unsigned int i = 0;
    for (; i < n && src[i]; i++)
        dst[i] = src[i];
    for (; i < n; i++)
        dst[i] = 0;
    return dst;
}

int strcmp(const char *a, const char *b) {
    while (*a && *a == *b) {
        a++;
        b++;
    }
    return (int)(unsigned char)*a - (int)(unsigned char)*b;
}

int strncmp(const char *a, const char *b, unsigned int n) {
    for (unsigned int i = 0; i < n; i++) {
        if (a[i] != b[i] || a[i] == 0)
            return (int)(unsigned char)a[i] - (int)(unsigned char)b[i];
    }
    return 0;
}

char *strcat(char *dst, const char *src) {
    strcpy(dst + strlen(dst), src);
    return dst;
}

char *strncat(char *dst, const char *src, unsigned int n) {
    char *end = dst + strlen(dst);
    unsigned int i = 0;
    for (; i < n && src[i]; i++)
        end[i] = src[i];
    end[i] = 0;
    return dst;
}

char *strchr(const char *s, int c) {
    for (; *s; s++)
        if (*s == (char)c)
            return (char *)s;
    return (c == 0) ? (char *)s : 0;
}

char *strrchr(const char *s, int c) {
    const char *found = (c == 0) ? s + strlen(s) : 0;
    for (; *s; s++)
        if (*s == (char)c)
            found = s;
    return (char *)found;
}

char *strstr(const char *haystack, const char *needle) {
    if (!*needle)
        return (char *)haystack;
    for (; *haystack; haystack++) {
        const char *h = haystack;
        const char *n = needle;
        while (*h && *n && *h == *n) {
            h++;
            n++;
        }
        if (!*n)
            return (char *)haystack;
    }
    return 0;
}
