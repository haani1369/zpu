#include "string.h"
#include "test_support.h"

int main(void) {
    char buf[16];

    memset(buf, 'x', 5);
    buf[5] = 0;
    CHECK(strcmp(buf, "xxxxx") == 0, "memset");

    memcpy(buf, "hello", 6);
    CHECK(strcmp(buf, "hello") == 0, "memcpy");

    memmove(buf + 1, buf, 5);
    buf[0] = 'H';
    CHECK(memcmp(buf, "Hhello", 6) == 0, "memmove");

    {
        const char *s = "hello";
        CHECK(memchr(s, 'l', 5) == s + 2, "memchr finds");
        CHECK(memchr(s, 'z', 5) == 0, "memchr misses");
    }

    CHECK(strlen("") == 0, "strlen empty");
    CHECK(strlen("hello") == 5, "strlen");

    strcpy(buf, "abc");
    CHECK(strcmp(buf, "abc") == 0, "strcpy");

    strncpy(buf, "xyzw", 2);
    buf[2] = 0;
    CHECK(strcmp(buf, "xy") == 0, "strncpy truncates");

    CHECK(strcmp("abc", "abc") == 0, "strcmp equal");
    CHECK(strcmp("abc", "abd") < 0, "strcmp less");
    CHECK(strcmp("abd", "abc") > 0, "strcmp greater");

    CHECK(strncmp("abcxxx", "abcyyy", 3) == 0, "strncmp equal prefix");
    CHECK(strncmp("abc", "abd", 3) < 0, "strncmp less");

    strcpy(buf, "ab");
    strcat(buf, "cd");
    CHECK(strcmp(buf, "abcd") == 0, "strcat");

    strcpy(buf, "ab");
    strncat(buf, "cdef", 2);
    CHECK(strcmp(buf, "abcd") == 0, "strncat truncates");

    {
        const char *s = "hello world";
        CHECK(strchr(s, 'o') == s + 4, "strchr");
        CHECK(strchr(s, 'z') == 0, "strchr missing");
        CHECK(strrchr(s, 'o') == s + 7, "strrchr");
        CHECK(strstr(s, "wor") == s + 6, "strstr");
        CHECK(strstr(s, "nope") == 0, "strstr missing");
        CHECK(strstr(s, "") == s, "strstr empty needle");
    }

    TEST_REPORT();
}
