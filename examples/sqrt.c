int main(void) {
    float x = 2.0f, g = x;
    for (int i = 0; i < 25; i++)
        g = (g + x / g) * 0.5f;
    return (int)(g * 100000);
}
