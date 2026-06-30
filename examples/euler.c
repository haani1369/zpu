int main(void) {
    float e = 1.0f, term = 1.0f;
    for (int i = 1; i < 15; i++) {
        term /= i;
        e += term;
    }
    return (int)(e * 100000);
}
