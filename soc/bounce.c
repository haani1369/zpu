#include "stdio.h"
#include "zpu_console.h"

#define WIDTH 24
#define HEIGHT 8
#define NUM_FRAMES 40
#define DELAY 500

static void delay(void) {
    for (volatile int i = 0; i < DELAY; i++)
        ;
}

static void draw_frame(int x, int y, int frame) {
    printf("\x1b[2J\x1b[H");
    for (int col = 0; col < WIDTH + 2; col++)
        putchar('-');
    putchar('\n');
    for (int row = 0; row < HEIGHT; row++) {
        putchar('|');
        for (int col = 0; col < WIDTH; col++)
            putchar((row == y && col == x) ? 'O' : ' ');
        putchar('|');
        putchar('\n');
    }
    for (int col = 0; col < WIDTH + 2; col++)
        putchar('-');
    putchar('\n');
    printf("frame %d/%d\n", frame + 1, NUM_FRAMES);
}

int main(void) {
    zpu_console_init();
    int x = 1, y = 1;
    int dx = 1, dy = 1;

    for (int frame = 0; frame < NUM_FRAMES; frame++) {
        draw_frame(x, y, frame);

        x += dx;
        y += dy;
        if (x <= 0 || x >= WIDTH - 1)
            dx = -dx;
        if (y <= 0 || y >= HEIGHT - 1)
            dy = -dy;

        delay();
    }

    printf("\x1b[2J\x1b[Hdone bouncing\n");
    return 0;
}
