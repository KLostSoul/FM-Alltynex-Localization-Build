"""Hanme component mapping and 16x16 to 24x24 font conversion."""
from __future__ import annotations
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCE_FONT = ROOT / "font" / "han_hanme.fnt"


FONT_MAGIC = b"HMEFNT01"


FONT_CELLS = 360


GLYPH_BYTES = 72


FONT_SIZE = 16 + FONT_CELLS * GLYPH_BYTES


NO_FINAL = (0, 0, 0, 0, 0, 0, 0, 0, 1, 3, 3, 3, 1, 2, 4, 4, 4, 2, 1, 3, 0)


WITH_FINAL = (5, 5, 5, 5, 5, 5, 5, 5, 6, 7, 7, 7, 6, 6, 7, 7, 7, 6, 6, 7, 5)


FINAL_PROFILE = (0, 2, 0, 2, 1, 2, 1, 2, 3, 0, 2, 1, 3, 3, 1, 2, 1, 3, 3, 1, 1)


def component_indices(syllable: str) -> tuple[int, int, int | None]:
    n = ord(syllable) - 0xAC00
    if not 0 <= n < 11172:
        raise ValueError(f"not a precomposed Hangul syllable: {syllable!r}")
    initial, rem = divmod(n, 588)
    medial, final = divmod(rem, 28)
    ip = (WITH_FINAL if final else NO_FINAL)[medial]
    mp = (2 if final else 0) + (initial not in (0, 15))
    fp = FINAL_PROFILE[medial]
    return (ip * 20 + initial + 1,
            160 + mp * 22 + medial + 1,
            248 + fp * 28 + final if final else None)


def scale_component(cell: bytes) -> bytes:
    if len(cell) != 32:
        raise ValueError("expected one 16x16 1bpp component")
    out = bytearray(72)
    for y in range(24):
        sy = y * 2 // 3
        bits = int.from_bytes(cell[sy * 2:sy * 2 + 2], "big")
        for x in range(24):
            if bits & (0x8000 >> (x * 2 // 3)):
                out[y * 3 + x // 8] |= 0x80 >> (x % 8)
    return bytes(out)


def make_font() -> bytes:
    source = SOURCE_FONT.read_bytes()
    if len(source) != FONT_CELLS * 32:
        raise ValueError(f"unexpected han_hanme.fnt size: {len(source)}")
    body = b"".join(scale_component(source[i * 32:i * 32 + 32])
                    for i in range(FONT_CELLS))
    font = struct.pack("<8sHBBI", FONT_MAGIC, FONT_CELLS, 24, 24,
                       GLYPH_BYTES) + body
    if len(font) != FONT_SIZE:
        raise AssertionError("derived component font has wrong length")
    return font
