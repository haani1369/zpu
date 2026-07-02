#ifndef ZPU_STRING_H
#define ZPU_STRING_H

void *memcpy(void *dst, const void *src, unsigned int n);
void *memmove(void *dst, const void *src, unsigned int n);
void *memset(void *dst, int c, unsigned int n);
int memcmp(const void *a, const void *b, unsigned int n);
void *memchr(const void *s, int c, unsigned int n);

unsigned int strlen(const char *s);
char *strcpy(char *dst, const char *src);
char *strncpy(char *dst, const char *src, unsigned int n);
int strcmp(const char *a, const char *b);
int strncmp(const char *a, const char *b, unsigned int n);
char *strcat(char *dst, const char *src);
char *strncat(char *dst, const char *src, unsigned int n);
char *strchr(const char *s, int c);
char *strrchr(const char *s, int c);
char *strstr(const char *haystack, const char *needle);

#endif
