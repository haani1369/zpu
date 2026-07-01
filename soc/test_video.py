import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from video import VideoDevice
from memmap import (VIDEO_CONTROL, VIDEO_CONTROL_ENABLE, VIDEO_WIDTH,
                    VIDEO_HEIGHT, VIDEO_FORMAT, VIDEO_BASE,
                    VIDEO_PALETTE_INDEX, VIDEO_PALETTE_DATA,
                    VIDEO_FORMAT_INDEXED8, VIDEO_FORMAT_RGB565,
                    VIDEO_FORMAT_RGB888, VRAM_WINDOW_SIZE)


class VideoRegisterTests(unittest.TestCase):
    def make(self):
        video = VideoDevice()
        video.attach_vram(bytearray(VRAM_WINDOW_SIZE))
        return video

    def test_control_defaults_disabled(self):
        video = self.make()
        self.assertEqual(video.read32(VIDEO_CONTROL), 0)

    def test_control_roundtrip(self):
        video = self.make()
        video.write32(VIDEO_CONTROL, VIDEO_CONTROL_ENABLE)
        self.assertEqual(video.read32(VIDEO_CONTROL), VIDEO_CONTROL_ENABLE)

    def test_mode_registers_roundtrip(self):
        video = self.make()
        video.write32(VIDEO_WIDTH, 320)
        video.write32(VIDEO_HEIGHT, 240)
        video.write32(VIDEO_FORMAT, VIDEO_FORMAT_RGB565)
        video.write32(VIDEO_BASE, 0x1000)
        self.assertEqual(video.read32(VIDEO_WIDTH), 320)
        self.assertEqual(video.read32(VIDEO_HEIGHT), 240)
        self.assertEqual(video.read32(VIDEO_FORMAT), VIDEO_FORMAT_RGB565)
        self.assertEqual(video.read32(VIDEO_BASE), 0x1000)

    def test_palette_roundtrip(self):
        video = self.make()
        video.write32(VIDEO_PALETTE_INDEX, 5)
        video.write32(VIDEO_PALETTE_DATA, 0x00ff8040)
        video.write32(VIDEO_PALETTE_INDEX, 5)
        self.assertEqual(video.read32(VIDEO_PALETTE_DATA), 0x00ff8040)

    def test_palette_entries_are_independent(self):
        video = self.make()
        video.write32(VIDEO_PALETTE_INDEX, 1)
        video.write32(VIDEO_PALETTE_DATA, 0x00112233)
        video.write32(VIDEO_PALETTE_INDEX, 2)
        video.write32(VIDEO_PALETTE_DATA, 0x00445566)
        video.write32(VIDEO_PALETTE_INDEX, 1)
        self.assertEqual(video.read32(VIDEO_PALETTE_DATA), 0x00112233)


class VideoPixelTests(unittest.TestCase):
    def make(self, width, height, fmt):
        video = VideoDevice()
        video.attach_vram(bytearray(VRAM_WINDOW_SIZE))
        video.write32(VIDEO_WIDTH, width)
        video.write32(VIDEO_HEIGHT, height)
        video.write32(VIDEO_FORMAT, fmt)
        video.write32(VIDEO_BASE, 0)
        return video

    def test_indexed_pixel_resolves_through_palette(self):
        video = self.make(2, 1, VIDEO_FORMAT_INDEXED8)
        video.write32(VIDEO_PALETTE_INDEX, 7)
        video.write32(VIDEO_PALETTE_DATA, 0x00aabbcc)
        video.vram[0] = 7
        self.assertEqual(video.pixel(0, 0), (0xaa, 0xbb, 0xcc))

    def test_rgb565_pixel(self):
        video = self.make(1, 1, VIDEO_FORMAT_RGB565)
        video.vram[0:2] = (0b11111_000000_00000).to_bytes(2, "big")
        r, g, b = video.pixel(0, 0)
        self.assertEqual((r, g, b), (255, 0, 0))

    def test_rgb888_pixel(self):
        video = self.make(1, 1, VIDEO_FORMAT_RGB888)
        video.vram[0:3] = bytes([10, 20, 30])
        self.assertEqual(video.pixel(0, 0), (10, 20, 30))

    def test_pixel_offset_uses_row_major_stride(self):
        video = self.make(2, 2, VIDEO_FORMAT_RGB888)
        video.vram[3 * (1 * 2 + 1):3 * (1 * 2 + 1) + 3] = bytes([1, 2, 3])
        self.assertEqual(video.pixel(1, 1), (1, 2, 3))

    def test_base_register_offsets_the_framebuffer(self):
        video = self.make(1, 1, VIDEO_FORMAT_RGB888)
        video.write32(VIDEO_BASE, 0x100)
        video.vram[0x100:0x103] = bytes([9, 8, 7])
        self.assertEqual(video.pixel(0, 0), (9, 8, 7))

    def test_to_ppm_header_and_size(self):
        video = self.make(2, 1, VIDEO_FORMAT_RGB888)
        video.vram[0:6] = bytes([1, 2, 3, 4, 5, 6])
        ppm = video.to_ppm()
        self.assertTrue(ppm.startswith(b"P6\n2 1\n255\n"))
        self.assertTrue(ppm.endswith(bytes([1, 2, 3, 4, 5, 6])))


if __name__ == "__main__":
    unittest.main()
