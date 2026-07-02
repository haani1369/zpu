#include "stdio.h"
#include "stdlib.h"
#include "zpu_console.h"

#define VRAM_BASE 0x20000000u
#define VIDEO0_BASE 0x10010000u

#define VIDEO_CONTROL 0x00u
#define VIDEO_WIDTH 0x04u
#define VIDEO_HEIGHT 0x08u
#define VIDEO_FORMAT 0x0cu
#define VIDEO_BASE_REG 0x10u
#define VIDEO_PALETTE_INDEX 0x14u
#define VIDEO_PALETTE_DATA 0x18u

#define VIDEO_CONTROL_ENABLE 1u
#define VIDEO_FORMAT_INDEXED8 0u

#define video_reg(offset) (*(volatile unsigned int *)(VIDEO0_BASE + (offset)))
#define vram_byte(offset) (*(volatile unsigned char *)(VRAM_BASE + (offset)))

#define WIDTH 24
#define HEIGHT 18
#define MAX_ITER 16

static int escape_iterations(double cr, double ci) {
    double zr = 0.0, zi = 0.0;
    int i;
    for (i = 0; i < MAX_ITER; i++) {
        double zr2 = zr * zr;
        double zi2 = zi * zi;
        if (zr2 + zi2 > 4.0)
            break;
        double next_zi = 2.0 * zr * zi + ci;
        zr = zr2 - zi2 + cr;
        zi = next_zi;
    }
    return i;
}

static void set_palette(void) {
    for (int i = 0; i < 256; i++) {
        unsigned int shade = (unsigned int)i;
        unsigned int blue = (unsigned int)((i * 4) & 0xff);
        unsigned int rgb = (shade << 16) | (shade << 8) | blue;
        video_reg(VIDEO_PALETTE_INDEX) = (unsigned int)i;
        video_reg(VIDEO_PALETTE_DATA) = rgb;
    }
}

int main(void) {
    zpu_console_init();
    printf("mandelbrot: %dx%d, %d iterations max\n", WIDTH, HEIGHT, MAX_ITER);

    video_reg(VIDEO_WIDTH) = WIDTH;
    video_reg(VIDEO_HEIGHT) = HEIGHT;
    video_reg(VIDEO_FORMAT) = VIDEO_FORMAT_INDEXED8;
    video_reg(VIDEO_BASE_REG) = 0;
    set_palette();
    video_reg(VIDEO_CONTROL) = VIDEO_CONTROL_ENABLE;

    int *histogram = calloc(MAX_ITER + 1, sizeof(int));
    int escaped_at_max = 0;

    double x0 = -2.5, x1 = 1.0;
    double y0 = -1.2, y1 = 1.2;

    for (int py = 0; py < HEIGHT; py++) {
        double ci = y0 + (y1 - y0) * py / (HEIGHT - 1);
        for (int px = 0; px < WIDTH; px++) {
            double cr = x0 + (x1 - x0) * px / (WIDTH - 1);
            int iter = escape_iterations(cr, ci);
            histogram[iter]++;
            if (iter == MAX_ITER)
                escaped_at_max++;
            vram_byte(py * WIDTH + px) = (unsigned char)(iter % 256);
        }
        if ((py & 7) == 0)
            printf("row %d/%d\n", py, HEIGHT);
    }

    int busiest_bucket = 0;
    for (int i = 1; i <= MAX_ITER; i++)
        if (histogram[i] > histogram[busiest_bucket])
            busiest_bucket = i;

    printf("done: %d pixels never escaped, %d pixels in the busiest bucket "
          "(iteration count %d)\n",
          escaped_at_max, histogram[busiest_bucket], busiest_bucket);

    free(histogram);
    return 0;
}
