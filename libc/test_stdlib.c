#include "stdlib.h"
#include "test_support.h"

static int cmp_int(const void *a, const void *b) {
    int x = *(const int *)a;
    int y = *(const int *)b;
    return x - y;
}

int main(void) {
    CHECK(abs(-5) == 5 && abs(5) == 5 && abs(0) == 0, "abs");
    CHECK(labs(-5) == 5, "labs");

    CHECK(atoi("42") == 42, "atoi positive");
    CHECK(atoi("-42") == -42, "atoi negative");
    CHECK(atoi("  7") == 7, "atoi leading space");
    CHECK(atoi("0") == 0, "atoi zero");
    CHECK(atol("123456") == 123456, "atol");

    srand(1);
    {
        int a = rand();
        srand(1);
        int b = rand();
        CHECK(a == b, "srand makes rand repeatable");
        CHECK(a >= 0, "rand is non-negative");
    }

    {
        int arr[6] = {5, 3, 1, 4, 1, 2};
        qsort(arr, 6, sizeof(int), cmp_int);
        CHECK(arr[0] == 1 && arr[1] == 1 && arr[2] == 2 &&
             arr[3] == 3 && arr[4] == 4 && arr[5] == 5, "qsort sorts");
    }

    {
        void *p1 = malloc(16);
        void *p2 = malloc(32);
        CHECK(p1 != 0 && p2 != 0, "malloc succeeds");
        CHECK(p1 != p2, "distinct allocations");
        *(int *)p1 = 0x11111111;
        *(int *)p2 = 0x22222222;
        CHECK(*(int *)p1 == 0x11111111 && *(int *)p2 == 0x22222222,
             "allocations don't alias");
        free(p1);
        free(p2);
    }

    {
        int *arr = calloc(8, sizeof(int));
        CHECK(arr != 0, "calloc succeeds");
        int allzero = 1;
        for (int i = 0; i < 8; i++)
            if (arr[i] != 0)
                allzero = 0;
        CHECK(allzero, "calloc zeroes");
        free(arr);
    }

    {
        char *p = malloc(4);
        p[0] = 'a'; p[1] = 'b'; p[2] = 'c'; p[3] = 0;
        char *q = realloc(p, 8);
        CHECK(q != 0, "realloc succeeds");
        CHECK(q[0] == 'a' && q[1] == 'b' && q[2] == 'c' && q[3] == 0,
             "realloc preserves contents");
        free(q);
    }

    {
        // free/coalesce stress: many small allocations, free them all in a
        // different order, then confirm a big allocation still fits.
        void *p[20];
        for (int i = 0; i < 20; i++) {
            p[i] = malloc(8);
            CHECK(p[i] != 0, "stress allocation succeeds");
        }
        for (int i = 19; i >= 0; i--)
            free(p[i]);
        void *big = malloc(400);
        CHECK(big != 0, "large allocation after freeing/coalescing");
        free(big);
    }

    TEST_REPORT();
}
