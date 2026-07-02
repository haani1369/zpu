#ifndef ZPU_STDLIB_H
#define ZPU_STDLIB_H

void *malloc(unsigned int size);
void free(void *ptr);
void *calloc(unsigned int nmemb, unsigned int size);
void *realloc(void *ptr, unsigned int size);

int abs(int n);
long labs(long n);

int atoi(const char *s);
long atol(const char *s);

void srand(unsigned int seed);
int rand(void);

void qsort(void *base, unsigned int nmemb, unsigned int size,
          int (*cmp)(const void *, const void *));

void abort(void);
void exit(int status);

#endif
