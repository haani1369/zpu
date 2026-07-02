#include "ctype.h"
#include "test_support.h"

int main(void) {
    CHECK(isalpha('a') && isalpha('Z'), "isalpha letters");
    CHECK(!isalpha('5') && !isalpha(' '), "isalpha non-letters");

    CHECK(isdigit('0') && isdigit('9'), "isdigit digits");
    CHECK(!isdigit('a'), "isdigit non-digit");

    CHECK(isalnum('a') && isalnum('5') && !isalnum('!'), "isalnum");

    CHECK(isupper('A') && !isupper('a'), "isupper");
    CHECK(islower('a') && !islower('A'), "islower");

    CHECK(isspace(' ') && isspace('\t') && isspace('\n'), "isspace");
    CHECK(!isspace('a'), "isspace non-space");

    CHECK(ispunct('!') && ispunct('.') && !ispunct('a'), "ispunct");
    CHECK(iscntrl('\n') && iscntrl('\0') && !iscntrl('a'), "iscntrl");

    CHECK(isxdigit('a') && isxdigit('F') && isxdigit('9'), "isxdigit hex");
    CHECK(!isxdigit('g'), "isxdigit non-hex");

    CHECK(isprint('a') && isprint(' ') && !isprint('\n'), "isprint");
    CHECK(isgraph('a') && !isgraph(' ') && !isgraph('\n'), "isgraph");

    CHECK(toupper('a') == 'A' && toupper('A') == 'A', "toupper");
    CHECK(tolower('A') == 'a' && tolower('a') == 'a', "tolower");
    CHECK(toupper('5') == '5', "toupper non-letter");

    TEST_REPORT();
}
