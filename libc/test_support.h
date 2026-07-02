#ifndef ZPU_TEST_SUPPORT_H
#define ZPU_TEST_SUPPORT_H

#include "../soc/zpu_console.h"

static int test_failures = 0;

#define CHECK(cond, msg) do { \
    if (!(cond)) { \
        zpu_console_puts("FAIL: " msg "\n"); \
        test_failures++; \
    } \
} while (0)

#define TEST_REPORT() do { \
    if (test_failures == 0) \
        zpu_console_puts("ALL PASS\n"); \
    else \
        zpu_console_puts("SOME FAILED\n"); \
    return test_failures; \
} while (0)

#endif
