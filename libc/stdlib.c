#include "stdlib.h"
#include "ctype.h"
#include "string.h"

#define ZPU_HEAP_WORDS (4096)

static unsigned int heap_storage[ZPU_HEAP_WORDS];

typedef struct block {
    unsigned int size; /* payload size in bytes, a multiple of 4 */
    int free;
} block_t;

static char *heap_start;
static char *heap_end;

static void heap_init(void) {
    heap_start = (char *)heap_storage;
    heap_end = heap_start + sizeof(heap_storage);
    block_t *first = (block_t *)heap_start;
    first->size = (unsigned int)(heap_end - heap_start) - sizeof(block_t);
    first->free = 1;
}

void *malloc(unsigned int n) {
    if (!heap_start)
        heap_init();
    if (n == 0)
        return 0;
    n = (n + 3u) & ~3u;

    block_t *b = (block_t *)heap_start;
    while ((char *)b < heap_end) {
        if (b->free && b->size >= n) {
            unsigned int remaining = b->size - n;
            if (remaining >= sizeof(block_t) + 4) {
                block_t *rest = (block_t *)((char *)b + sizeof(block_t) + n);
                rest->size = remaining - sizeof(block_t);
                rest->free = 1;
                b->size = n;
            }
            b->free = 0;
            return (char *)b + sizeof(block_t);
        }
        b = (block_t *)((char *)b + sizeof(block_t) + b->size);
    }
    return 0;
}

static void heap_coalesce(void) {
    block_t *b = (block_t *)heap_start;
    while ((char *)b < heap_end) {
        block_t *next = (block_t *)((char *)b + sizeof(block_t) + b->size);
        if (b->free && (char *)next < heap_end && next->free) {
            b->size += sizeof(block_t) + next->size;
            continue;
        }
        b = next;
    }
}

void free(void *ptr) {
    if (!ptr)
        return;
    block_t *b = (block_t *)((char *)ptr - sizeof(block_t));
    b->free = 1;
    heap_coalesce();
}

void *calloc(unsigned int nmemb, unsigned int size) {
    unsigned int total = nmemb * size;
    void *p = malloc(total);
    if (p)
        memset(p, 0, total);
    return p;
}

void *realloc(void *ptr, unsigned int n) {
    if (!ptr)
        return malloc(n);
    if (n == 0) {
        free(ptr);
        return 0;
    }
    block_t *b = (block_t *)((char *)ptr - sizeof(block_t));
    if (b->size >= n)
        return ptr;
    void *fresh = malloc(n);
    if (fresh) {
        memcpy(fresh, ptr, b->size);
        free(ptr);
    }
    return fresh;
}

int abs(int n) {
    return n < 0 ? -n : n;
}

long labs(long n) {
    return n < 0 ? -n : n;
}

int atoi(const char *s) {
    while (isspace((unsigned char)*s))
        s++;
    int sign = 1;
    if (*s == '-') {
        sign = -1;
        s++;
    } else if (*s == '+') {
        s++;
    }
    int n = 0;
    while (isdigit((unsigned char)*s))
        n = n * 10 + (*s++ - '0');
    return sign * n;
}

long atol(const char *s) {
    return (long)atoi(s);
}

static unsigned int rand_state = 1;

void srand(unsigned int seed) {
    rand_state = seed;
}

int rand(void) {
    rand_state = rand_state * 1103515245u + 12345u;
    return (int)((rand_state >> 1) & 0x7fffffffu);
}

void qsort(void *base, unsigned int nmemb, unsigned int size,
          int (*cmp)(const void *, const void *)) {
    char *p = base;
    /* insertion sort: simple, correct, and fine at demo scale -- swapping
       through a scratch buffer of size bytes since elements are of
       unknown, caller-supplied width. */
    for (unsigned int i = 1; i < nmemb; i++) {
        unsigned int j = i;
        while (j > 0 && cmp(p + (j - 1) * size, p + j * size) > 0) {
            char *a = p + (j - 1) * size;
            char *b = p + j * size;
            for (unsigned int k = 0; k < size; k++) {
                char t = a[k];
                a[k] = b[k];
                b[k] = t;
            }
            j--;
        }
    }
}

void abort(void) {
    for (;;)
        ;
}

void exit(int status) {
    (void)status;
    for (;;)
        ;
}
