int main(void) {
    long long f = 1;
    for (int i = 2; i <= 20; i++)
        f *= i;
    return (int)(f % 1000000);
}
