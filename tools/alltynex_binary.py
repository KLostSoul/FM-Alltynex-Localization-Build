"""Shared ISO9660, P3 EXP and x86 assembly helpers for Alltynex."""
from __future__ import annotations
import struct

SECTOR = 2048
PVD_LBA = 16

IMAGE_SIZE = 0xD0E00


EGB_STRING_WRAPPER = 0x33C94


WRAPPER_HEAD = bytes.fromhex("56 57 8B 7C 24 0C")


LOADER = 0x2AA10

def read_dual32(b, o):
    le, be = struct.unpack_from("<I", b, o)[0], struct.unpack_from(">I", b, o + 4)[0]
    if le != be:
        raise ValueError(f"invalid dual-endian ISO field {o:#x}")
    return le


def write_dual32(b, o, value):
    struct.pack_into("<I", b, o, value)
    struct.pack_into(">I", b, o + 4, value)


def expand_p3(exp):
    if exp[:4] != b"P3\x01\x00":
        raise ValueError("not a flat P3 EXP")
    image_off = struct.unpack_from("<I", exp, 0x26)[0]
    packed_size = struct.unpack_from("<I", exp, 0x2A)[0]
    image_size = struct.unpack_from("<I", exp, 0x74)[0]
    packed = bool(struct.unpack_from("<H", exp, 0x72)[0] & 1)
    if image_off + packed_size > len(exp):
        raise ValueError("P3 load image exceeds file")
    src = exp[image_off:image_off + packed_size]
    if not packed:
        if len(src) != image_size:
            raise ValueError("unpacked P3 image size mismatch")
        return bytearray(src)
    out = bytearray()
    p = 0
    while p < len(src) and len(out) < image_size:
        if p + 2 > len(src):
            raise ValueError("truncated P3 control word")
        control = struct.unpack_from("<H", src, p)[0]
        p += 2
        if control & 0x8000:
            count = control & 0x7FFF
            if p >= len(src):
                raise ValueError("truncated P3 repeat length")
            block_len = src[p]
            p += 1
            if block_len == 0:
                out.extend(bytes(count))
            else:
                if p + block_len > len(src):
                    raise ValueError("truncated P3 repeat block")
                block = src[p:p + block_len]
                p += block_len
                out.extend((block * ((count + block_len - 1) // block_len))[:count])
        else:
            if p + control > len(src):
                raise ValueError("truncated P3 literal block")
            out.extend(src[p:p + control])
            p += control
        if len(out) > image_size:
            raise ValueError("P3 expansion exceeds declared image size")
    if len(out) != image_size or p != len(src):
        raise ValueError("P3 expansion size/stream mismatch")
    return out


def records(data):
    p = 0
    while p < len(data):
        n = data[p]
        if n == 0:
            p = (p // SECTOR + 1) * SECTOR
            continue
        if p + n > len(data):
            raise ValueError("directory record exceeds directory")
        r = data[p:p + n]
        name = bytes(r[33:33 + r[32]])
        yield p, r, name
        p += n


def extent_size(record):
    return read_dual32(record, 2), read_dual32(record, 10)


def find_child(iso, lba, size, wanted):
    directory = iso[lba * SECTOR:lba * SECTOR + size]
    for p, record, name in records(directory):
        if name not in (b"\0", b"\1") and name.split(b";", 1)[0].upper() == wanted.upper():
            return p, record, name
    raise FileNotFoundError(wanted.decode("ascii"))


def iso_record(name, lba, size):
    length = 33 + len(name) + (1 if len(name) % 2 == 0 else 0)
    record = bytearray(length)
    record[0] = length
    write_dual32(record, 2, lba)
    write_dual32(record, 10, size)
    record[18:25] = bytes((126, 10, 2, 0, 0, 0, 0))
    struct.pack_into("<H", record, 28, 1)
    struct.pack_into(">H", record, 30, 1)
    record[32] = len(name)
    record[33:33 + len(name)] = name
    return bytes(record)


def make_p3(exp, image):
    image_off = struct.unpack_from("<I", exp, 0x26)[0]
    header = bytearray(exp[:image_off])
    struct.pack_into("<I", header, 0x06, len(header) + len(image))
    struct.pack_into("<I", header, 0x2A, len(image))
    flags = struct.unpack_from("<H", header, 0x72)[0] & ~1
    struct.pack_into("<H", header, 0x72, flags)
    struct.pack_into("<I", header, 0x74, len(image))
    # Keep the original initial ESP and CRT heap placement.  Patch builders
    # must keep appended data below the game's deepest stack reservation.
    return bytes(header) + bytes(image)

class Asm:
    def __init__(self, origin: int):
        self.origin = origin
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []

    def emit(self, *values: int) -> None:
        self.code.extend(values)

    def dword(self, value: int) -> None:
        self.code.extend(struct.pack("<I", value))

    def rel32(self, value: int) -> None:
        self.code.extend(struct.pack("<i", value))

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label: {name}")
        self.labels[name] = len(self.code)

    def jcc(self, cc: int, name: str) -> None:
        self.emit(0x0F, 0x80 | cc)
        self.fixups.append((len(self.code), name))
        self.dword(0)

    def jmp(self, name: str) -> None:
        self.emit(0xE9)
        self.fixups.append((len(self.code), name))
        self.dword(0)

    def call(self, target: int) -> None:
        self.emit(0xE8)
        displacement_at = len(self.code)
        self.rel32(target - (self.origin + displacement_at + 4))

    def finish(self) -> bytes:
        for displacement_at, name in self.fixups:
            if name not in self.labels:
                raise ValueError(f"missing label: {name}")
            target = self.origin + self.labels[name]
            delta = target - (self.origin + displacement_at + 4)
            struct.pack_into("<i", self.code, displacement_at, delta)
        return bytes(self.code)
