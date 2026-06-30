int main(void) {
    int sieve[100];
    for (int i = 0; i < 100; i++)
        sieve[i] = 1;
    int count = 0;
    for (int p = 2; p < 100; p++)
        if (sieve[p]) {
            count++;
            for (int k = p * p; k < 100; k += p)
                sieve[k] = 0;
        }
    return count;
}
