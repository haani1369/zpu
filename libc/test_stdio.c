#include "stdio.h"
#include "string.h"
#include "test_support.h"

int main(void) {
    char buf[64];

    int n = sprintf(buf, "%d-%u-%x-%c-%s", -7, 42u, 255, 'q', "hi");
    CHECK(strcmp(buf, "-7-42-ff-q-hi") == 0, "sprintf mixed conversions");
    CHECK(n == (int)strlen(buf), "sprintf return is length written");

    sprintf(buf, "%%");
    CHECK(strcmp(buf, "%") == 0, "sprintf literal percent");

    sprintf(buf, "[%5d][%-5d][%05d]", 3, 3, 3);
    CHECK(strcmp(buf, "[    3][3    ][00003]") == 0, "sprintf width/pad");

    sprintf(buf, "%08x", 0xabu);
    CHECK(strcmp(buf, "000000ab") == 0, "sprintf zero-padded hex");

    n = snprintf(buf, 4, "%s", "hello");
    CHECK(strcmp(buf, "hel") == 0, "snprintf truncates and terminates");
    CHECK(n == 5, "snprintf return is untruncated length");

    puts("PUTS-LINE");
    printf("PRINTF %d %s %c\n", 99, "abc", 'z');

    int c = getchar();
    CHECK(c == 'Q', "getchar reads fed byte");

    TEST_REPORT();
}
