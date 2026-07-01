from memmap import (VIDEO_CONTROL, VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FORMAT,
                    VIDEO_BASE, VIDEO_PALETTE_INDEX, VIDEO_PALETTE_DATA,
                    VIDEO_FORMAT_INDEXED8, VIDEO_FORMAT_RGB565,
                    VIDEO_FORMAT_RGB888, VIDEO_BYTES_PER_PIXEL)


class VideoDevice:
    def __init__(self):
        self.vram = None
        self.control = 0
        self.width = 0
        self.height = 0
        self.format = VIDEO_FORMAT_INDEXED8
        self.base = 0
        self.palette = [0] * 256
        self._palette_index = 0

    def attach_vram(self, vram):
        self.vram = vram

    def read32(self, offset):
        if offset == VIDEO_CONTROL:
            return self.control
        if offset == VIDEO_WIDTH:
            return self.width
        if offset == VIDEO_HEIGHT:
            return self.height
        if offset == VIDEO_FORMAT:
            return self.format
        if offset == VIDEO_BASE:
            return self.base
        if offset == VIDEO_PALETTE_DATA:
            return self.palette[self._palette_index]
        return 0

    def write32(self, offset, value):
        if offset == VIDEO_CONTROL:
            self.control = value & 1
        elif offset == VIDEO_WIDTH:
            self.width = value
        elif offset == VIDEO_HEIGHT:
            self.height = value
        elif offset == VIDEO_FORMAT:
            self.format = value
        elif offset == VIDEO_BASE:
            self.base = value
        elif offset == VIDEO_PALETTE_INDEX:
            self._palette_index = value & 0xff
        elif offset == VIDEO_PALETTE_DATA:
            self.palette[self._palette_index] = value & 0xffffff

    def bytes_per_pixel(self):
        return VIDEO_BYTES_PER_PIXEL[self.format]

    def pixel(self, x, y):
        bpp = self.bytes_per_pixel()
        offset = self.base + (y * self.width + x) * bpp
        if self.format == VIDEO_FORMAT_INDEXED8:
            rgb = self.palette[self.vram[offset]]
            return (rgb >> 16) & 0xff, (rgb >> 8) & 0xff, rgb & 0xff
        if self.format == VIDEO_FORMAT_RGB565:
            value = int.from_bytes(self.vram[offset:offset + 2], "big")
            r, g, b = (value >> 11) & 0x1f, (value >> 5) & 0x3f, value & 0x1f
            return r * 255 // 31, g * 255 // 63, b * 255 // 31
        r, g, b = self.vram[offset:offset + 3]
        return r, g, b

    def to_ppm(self):
        header = b"P6\n%d %d\n255\n" % (self.width, self.height)
        body = bytearray()
        for y in range(self.height):
            for x in range(self.width):
                body += bytes(self.pixel(x, y))
        return header + bytes(body)
