int main(void) {
    int a[8];
    a[0] = 5; a[1] = 2; a[2] = 8; a[3] = 1;
    a[4] = 9; a[5] = 3; a[6] = 7; a[7] = 4;
    for (int i = 0; i < 8; i++)
        for (int j = 0; j < 7 - i; j++)
            if (a[j] > a[j + 1]) {
                int t = a[j];
                a[j] = a[j + 1];
                a[j + 1] = t;
            }
    return a[0] * 100 + a[7];
}
