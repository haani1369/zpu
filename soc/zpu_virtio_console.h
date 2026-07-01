#ifndef ZPU_VIRTIO_CONSOLE_H
#define ZPU_VIRTIO_CONSOLE_H

void zpu_virtio_console_init(void);
void zpu_virtio_console_putc(char c);
void zpu_virtio_console_write(const char *data, int len);
void zpu_virtio_console_puts(const char *s);
int zpu_virtio_console_getc(void);

#endif
