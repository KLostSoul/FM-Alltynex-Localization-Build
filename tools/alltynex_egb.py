"""Current Korean EGB composition hook and runtime data layout."""
from __future__ import annotations
import struct

import alltynex_binary as binary
import alltynex_font as activity

IMAGE_SIZE = binary.IMAGE_SIZE


WRAPPER = binary.EGB_STRING_WRAPPER


WRAPPER_HEAD = binary.WRAPPER_HEAD


RECORD_SIZE = 86


TEXT_CAPACITY = 80


RAW_TO_IMAGE_DELTA = 0x210


FONT_SIZE = activity.FONT_SIZE


FONT_BUFFER = IMAGE_SIZE


COMPOSE_BUFFER = (FONT_BUFFER + FONT_SIZE + 15) & ~15


STATE = (COMPOSE_BUFFER + activity.GLYPH_BYTES + 15) & ~15


LOAD_STARTED = STATE


LOAD_OK = STATE + 1


CURRENT_SANITIZED = STATE + 4


CURRENT_META = STATE + 8


CURRENT_COUNT = STATE + 12


DRAW_META = STATE + 16


DRAW_COUNT = STATE + 20


CURRENT_SEGCOUNT = STATE + 24


DRAW_SEGMENT = STATE + 28


DRAW_SEGCOUNT = STATE + 32


HOOK = (STATE + 48 + 15) & ~15


TRAMPOLINE = HOOK + 0x2000


FILENAME = TRAMPOLINE + 16


RUNTIME_DATA_BASE = (FILENAME + 16 + 15) & ~15


PMB_STACK_BUDGET = 0x16000


def encode_cp932_character(char: str) -> bytes:
    """Encode non-Hangul text without control bytes or reserved token leads."""
    if ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F:
        raise ValueError(f"control character is not allowed in EGB text: U+{ord(char):04X}")
    normalized = "\u30fb" if char == "\u00b7" else char
    try:
        part = normalized.encode("cp932")
    except UnicodeEncodeError as exc:
        raise ValueError(f"character has no CP932 representation: U+{ord(char):04X}") from exc
    if not 1 <= len(part) <= 2:
        raise ValueError(f"unexpected CP932 character width for {char!r}: {part.hex()}")
    if part[0] in (0xF0, 0xF1):
        raise ValueError(f"CP932 character conflicts with Hangul tokens: U+{ord(char):04X}")
    return part


def encode_text(text: str, token_by_syllable: dict[str, bytes]) -> tuple[bytes, list[tuple[int, int]], int]:
    encoded = bytearray()
    glyphs: list[tuple[int, int]] = []
    x_advance = 0
    for char in text:
        if "\uac00" <= char <= "\ud7a3":
            try:
                pair = token_by_syllable[char]
            except KeyError as exc:
                raise ValueError(f"no composition token for {char!r}") from exc
            encoded.extend(pair)
            glyphs.append((int.from_bytes(pair, "big"), x_advance))
            x_advance += 24
            continue
        part = encode_cp932_character(char)
        encoded.extend(part)
        x_advance += 12 if char in (' ', '\u3000') else 24
    if len(encoded) >= TEXT_CAPACITY:
        raise ValueError(f"encoded row uses {len(encoded)} bytes; record allows {TEXT_CAPACITY - 1} plus NUL")
    return bytes(encoded), glyphs, x_advance


class Code:
    """Small 32-bit x86 assembler with the same calling conventions as binary.Asm."""
    def __init__(self, origin: int):
        self.a = binary.Asm(origin)

    def e(self, *values: int) -> None:
        self.a.emit(*values)

    def d(self, value: int) -> None:
        self.a.dword(value)

    def label(self, name: str) -> None:
        self.a.label(name)

    def jcc(self, condition: int, name: str) -> None:
        self.a.jcc(condition, name)

    def jmp(self, name: str) -> None:
        self.a.jmp(name)

    def call(self, target: int) -> None:
        self.a.call(target)

    def call_label(self, name: str) -> None:
        self.e(0xE8)
        self.a.fixups.append((len(self.a.code), name))
        self.d(0)

    def finish(self) -> bytes:
        return self.a.finish()


def component_table(rows: list[dict[str, str]]) -> bytes:
    data = bytearray()
    for row in rows:
        syllable = row["syllable"]
        for slot in activity.component_indices(syllable):
            address = (FONT_BUFFER + 16 + slot * activity.GLYPH_BYTES
                       if slot is not None else 0)
            data.extend(struct.pack("<I", address))
    if len(data) != len(rows) * 12:
        raise AssertionError("component pointer table size mismatch")
    return bytes(data)


def compose_code(a: Code) -> None:
    # ESI points to a 3-pointer record; OR its component cells into one 24x24 bitmap.
    a.label("compose")
    a.e(0x53, 0x89, 0xF3)  # preserve EBX; EBX = stable component record
    a.e(0x06, 0x1E, 0x07)  # save ES; use DS for the composition buffer
    a.e(0xBF); a.d(COMPOSE_BUFFER)
    a.e(0xB9); a.d(activity.GLYPH_BYTES // 4)
    a.e(0x31, 0xC0, 0xFC, 0xF3, 0xAB)  # zero buffer
    a.e(0x07)
    for part in range(3):
        a.e(0x8B, 0x73, part * 4)  # mov esi,[ebx+part*4]
        a.e(0x85, 0xF6)
        a.jcc(4, f"compose_skip_{part}")
        a.e(0xBF); a.d(COMPOSE_BUFFER)
        a.e(0xB9); a.d(activity.GLYPH_BYTES // 4)
        a.label(f"compose_loop_{part}")
        a.e(0x8B, 0x06, 0x09, 0x07)  # OR component dword into output
        a.e(0x83, 0xC6, 0x04, 0x83, 0xC7, 0x04, 0x49)
        a.jcc(5, f"compose_loop_{part}")
        a.label(f"compose_skip_{part}")
    a.e(0x5B, 0xC3)


def hook_code(row_items: list[dict], meta_addresses: list[int]) -> bytes:
    a = Code(HOOK)
    a.e(0x9C, 0x60)  # preserve incoming flags and all general registers
    a.e(0x8B, 0x54, 0x24, 0x2C)  # EDX = actual EGB record argument
    # The game copies the story table to its stack before rendering it.
    # Compare record bytes, not the address of the source table entry.
    a.e(0x06, 0x1E, 0x07, 0xFC)  # preserve ES; ES=DS; CLD
    for i, row in enumerate(row_items):
        a.e(0x89, 0xD6)  # ESI = caller's copied record
        a.e(0xBF); a.d(row["record_address"])
        a.e(0xB9); a.d(RECORD_SIZE)
        a.e(0xF3, 0xA6)  # REPE CMPSB: DS:ESI against ES:EDI
        a.jcc(5, f"next_record_{i}")
        a.e(0x07)  # restore ES before touching the original frame
        a.jmp(f"select_{i}")
        a.label(f"next_record_{i}")
    a.e(0x07)
    a.jmp("passthrough")

    for i, row in enumerate(row_items):
        a.label(f"select_{i}")
        a.e(0xC7, 0x05); a.d(CURRENT_SANITIZED); a.d(row["segment_list_address"])
        a.e(0xC7, 0x05); a.d(CURRENT_SEGCOUNT); a.d(len(row["segments"]))
        a.e(0xC7, 0x05); a.d(CURRENT_META); a.d(meta_addresses[i])
        a.e(0xC7, 0x05); a.d(CURRENT_COUNT); a.d(len(row["glyphs"]))
        a.jmp("process_row")

    a.label("process_row")
    # Load the sidecar once, after AUTOEXEC has started the game in its directory.
    a.e(0x80, 0x3D); a.d(LOAD_STARTED); a.e(0)
    a.jcc(5, "font_checked")
    a.e(0xC6, 0x05); a.d(LOAD_STARTED); a.e(1)
    for value in (1, FONT_SIZE, FONT_BUFFER, FILENAME):
        if value == 1:
            a.e(0x6A, 1)
        else:
            a.e(0x68); a.d(value)
    a.call(binary.LOADER)
    a.e(0x83, 0xC4, 0x10)
    for offset in (0, 4):
        a.e(0x81, 0x3D); a.d(FONT_BUFFER + offset)
        a.d(int.from_bytes(activity.FONT_MAGIC[offset:offset + 4], "little"))
        a.jcc(5, "font_checked")
    a.e(0x66, 0x81, 0x3D); a.d(FONT_BUFFER + 8)
    a.e(activity.FONT_CELLS & 0xFF, activity.FONT_CELLS >> 8)
    a.jcc(5, "font_checked")
    a.e(0x80, 0x3D); a.d(FONT_BUFFER + 10); a.e(24)
    a.jcc(5, "font_checked")
    a.e(0x80, 0x3D); a.d(FONT_BUFFER + 11); a.e(24)
    a.jcc(5, "font_checked")
    a.e(0x81, 0x3D); a.d(FONT_BUFFER + 12); a.d(activity.GLYPH_BYTES)
    a.jcc(5, "font_checked")
    a.e(0xC6, 0x05); a.d(LOAD_OK); a.e(1)

    a.label("font_checked")
    # Render non-space runs separately, positioned with 12-pixel space advance.
    a.e(0xA1); a.d(CURRENT_SANITIZED)
    a.e(0xA3); a.d(DRAW_SEGMENT)
    a.e(0xA1); a.d(CURRENT_SEGCOUNT)
    a.e(0xA3); a.d(DRAW_SEGCOUNT)
    a.label("render_segment")
    a.e(0xFF, 0x74, 0x24, 0x20, 0x9D)  # restore caller flags before delegation
    a.e(0x8B, 0x44, 0x24, 0x28)  # original arg1: game's EGB work buffer
    a.e(0x8B, 0x1D); a.d(DRAW_SEGMENT)
    a.e(0xFF, 0x33)  # push current run's EGB record pointer
    a.e(0x50)
    a.call(TRAMPOLINE)
    a.e(0x8D, 0x64, 0x24, 0x08)  # drop arguments without changing flags
    a.e(0x89, 0x44, 0x24, 0x1C)  # preserve renderer EAX in PUSHAD frame
    a.e(0x9C, 0x58, 0x89, 0x44, 0x24, 0x20)  # preserve renderer flags
    a.e(0x83, 0x05); a.d(DRAW_SEGMENT); a.e(4)
    a.e(0xFF, 0x0D); a.d(DRAW_SEGCOUNT)
    a.jcc(5, "render_segment")
    a.e(0x80, 0x3D); a.d(LOAD_OK); a.e(1)
    a.jcc(5, "target_return")
    a.e(0x8B, 0x1D); a.d(CURRENT_META)
    a.e(0x89, 0x1D); a.d(DRAW_META)
    a.e(0x8B, 0x0D); a.d(CURRENT_COUNT)
    a.e(0x89, 0x0D); a.d(DRAW_COUNT)
    a.e(0x83, 0xF9, 0)
    a.jcc(4, "target_return")

    a.label("draw_loop")
    a.e(0x8B, 0x1D); a.d(DRAW_META)  # EBX = component/descriptor pair
    a.e(0x8B, 0x33)  # ESI = component triple
    a.call_label("compose")
    a.e(0x8B, 0x7C, 0x24, 0x28)  # EDI = original EGB work buffer
    a.e(0x06)  # preserve ES
    a.e(0x68); a.d(0x110)
    a.e(0x07)  # ES=0110h
    a.e(0xB8); a.d(0x2301)  # EGB AH=23h, PSET bitmap
    a.e(0x8B, 0x73, 0x04)  # ESI = prebuilt descriptor
    a.e(0x26, 0xFF, 0x1D, 0x20, 0, 0, 0)
    a.e(0x07)  # restore ES
    a.e(0x83, 0x05); a.d(DRAW_META); a.e(8)
    a.e(0xFF, 0x0D); a.d(DRAW_COUNT)
    a.e(0x83, 0x3D); a.d(DRAW_COUNT); a.e(0)
    a.jcc(5, "draw_loop")

    a.label("target_return")
    a.e(0x61, 0x9D, 0xC3)
    a.label("passthrough")
    a.e(0x61, 0x9D, 0xE9)
    jump_opcode = len(a.a.code) - 1
    a.a.dword(0)
    compose_code(a)
    code = bytearray(a.finish())
    struct.pack_into("<i", code, jump_opcode + 1,
                     TRAMPOLINE - (HOOK + jump_opcode + 5))
    if len(code) > TRAMPOLINE - HOOK:
        raise ValueError(f"opening EGB hook is too large: {len(code):#x}")
    return bytes(code)


def build_records(image: bytes, rows: list[dict[str, str]], token_by_syllable: dict[str, bytes], component_rows: list[dict[str, str]]):
    patched = bytearray(image)
    overlays_per_row: list[list[tuple[int, int, int]]] = []
    token_index = {row["token"]: int(row["token_index"]) for row in component_rows}
    for row in rows:
        rec = int(row["exp_offset"], 16) - RAW_TO_IMAGE_DELTA
        original = bytes(image[rec:rec + RECORD_SIZE])
        # CSV x is editable. Validate the source layout and unedited y/length
        # independently from the new display position.
        if len(original) != RECORD_SIZE:
            raise ValueError(f"EGB record size mismatch at {row['exp_offset']}")
        source_y, source_length = struct.unpack_from('<HH', original, 2)
        if source_length != 40 or source_y != int(row['y']):
            raise ValueError(f"EGB record mismatch at {row['exp_offset']}: {original[:6].hex()}")
        target_x = int(row['x'])
        if not 0 <= target_x <= 32767:
            raise ValueError(f"{row['exp_offset']}: X must be 0..32767")
        data, glyph_offsets, _ = encode_text(row["korean_patch"], token_by_syllable)
        # EGB_String.len is a byte count. The original records use 40 bytes,
        # but the fixed str[80] payload can hold longer translated rows.
        record_head = struct.pack("<HHH", target_x, int(row["y"]), len(data))
        record = bytearray(record_head + data + bytes(TEXT_CAPACITY - len(data)))
        clean = bytearray(record)
        row_overlays = []
        x = target_x
        y = int(row["y"])
        encoded_text, scan_overlays, _ = encode_text(row["korean_patch"], token_by_syllable)
        if encoded_text != data or len(scan_overlays) != len(glyph_offsets):
            raise AssertionError("text encoder was not deterministic")
        scan_x = x
        segments = []
        run_start, run_x = 0, x
        def flush_run(end):
            if end > run_start:
                payload = bytes(clean[6 + run_start:6 + end])
                segments.append(struct.pack('<HHH', run_x, y, len(payload)) +
                                payload + bytes(TEXT_CAPACITY - len(payload)))
        # Spaces are omitted from BIOS runs; their 12-pixel advance is explicit.
        i = 0
        while i < len(data):
            lead = data[i]
            if lead == 0x20 or data[i:i + 2] == b'\x81\x40':
                flush_run(i)
                i += 1 if lead == 0x20 else 2
                scan_x += 12
                run_start, run_x = i, scan_x
            elif lead in (0xF0, 0xF1):
                trail = data[i + 1]
                key = f"{lead:02X}{trail:02X}"
                row_overlays.append((token_index[key], scan_x, y))
                clean[6 + i:6 + i + 2] = b"\x81\x40"
                scan_x += 24
                i += 2
            elif not (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC):
                # CP932 halfwidth kana (A1..DF) and ANK use one byte.
                scan_x += 24
                i += 1
            else:
                if i + 1 >= len(data):
                    raise ValueError(f"dangling CP932 lead byte at {row['exp_offset']}")
                scan_x += 24
                i += 2
        flush_run(len(data))
        if not segments:
            # Empty staff-roll translations retain their table slot and timing.
            # Delegate a zero-length record so the common render loop stays valid.
            segments.append(struct.pack('<HHH', x, y, 0) + bytes(TEXT_CAPACITY))
        patched[rec:rec + RECORD_SIZE] = record
        overlays_per_row.append(row_overlays)
        row["record_address"] = rec
        row["glyphs"] = row_overlays
        row["encoded"] = data
        row["right_edge"] = scan_x
        row["segments"] = segments
    return patched, overlays_per_row


def add_runtime_data(patched: bytearray, rows: list[dict], overlays: list[list[tuple[int, int, int]]], component_rows: list[dict[str, str]]) -> None:
    # The renderer delegates the per-run segments below.  Full sanitized row
    # copies are never referenced by the hook and must not occupy EXP memory.
    table_address = RUNTIME_DATA_BASE
    table = component_table(component_rows)
    descriptor_base = (table_address + len(table) + 15) & ~15
    metadata_base = (descriptor_base + sum(len(r) for r in overlays) * 14 + 15) & ~15
    current = descriptor_base
    metadata_by_row: list[tuple[int, bytes]] = []
    for row, row_overlays in zip(rows, overlays):
        meta = bytearray()
        for token, x, y in row_overlays:
            descriptor_address = current
            descriptor = struct.pack("<IHhhhh", COMPOSE_BUFFER, 0x14,
                                     x, y - 23, x + 23, y)
            if x < 0 or x + 23 > 0x7FFF or y - 23 < -0x8000:
                raise ValueError(f"overlay coordinates exceed signed EGB range at {row['exp_offset']}")
            patched.extend(bytes(max(0, descriptor_address + 14 - len(patched))))
            patched[descriptor_address:descriptor_address + 14] = descriptor
            meta.extend(struct.pack("<II", table_address + token * 12, descriptor_address))
            current += 14
        metadata_by_row.append((metadata_base + sum(len(meta) for _, meta in metadata_by_row), bytes(meta)))
    patched.extend(bytes(max(0, table_address + len(table) - len(patched))))
    patched[table_address:table_address + len(table)] = table
    for address, meta in metadata_by_row:
        if meta:
            patched.extend(bytes(max(0, address + len(meta) - len(patched))))
            patched[address:address + len(meta)] = meta
    cursor = (max(table_address + len(table),
                  metadata_base + sum(len(meta) for _, meta in metadata_by_row)) + 15) & ~15
    for row in rows:
        addresses = []
        for segment in row['segments']:
            addresses.append(cursor)
            patched.extend(bytes(max(0, cursor + RECORD_SIZE - len(patched))))
            patched[cursor:cursor + RECORD_SIZE] = segment
            cursor += RECORD_SIZE
        row['segment_list_address'] = cursor
        pointers = struct.pack('<' + 'I' * len(addresses), *addresses)
        patched.extend(bytes(max(0, cursor + len(pointers) - len(patched))))
        patched[cursor:cursor + len(pointers)] = pointers
        cursor += len(pointers)
    patched.extend(bytes((len(patched) + 15) // 16 * 16 - len(patched)))
    for row, meta in zip(rows, metadata_by_row):
        row["meta_address"] = meta[0]


def make_hook_image(exp_file: bytes, rows: list[dict], token_by_syllable: dict[str, bytes], component_rows: list[dict[str, str]]):
    image = binary.expand_p3(exp_file)
    if len(image) != IMAGE_SIZE or image[WRAPPER:WRAPPER + len(WRAPPER_HEAD)] != WRAPPER_HEAD:
        raise ValueError("EXP image size or EGB wrapper prologue differs from verified build")
    patched, overlays = build_records(image, rows, token_by_syllable, component_rows)
    add_runtime_data(patched, rows, overlays, component_rows)
    code = hook_code(rows, [row["meta_address"] for row in rows])
    patched[HOOK:HOOK + len(code)] = code
    trampoline = WRAPPER_HEAD + b"\xE9" + struct.pack(
        "<i", (WRAPPER + len(WRAPPER_HEAD)) - (TRAMPOLINE + len(WRAPPER_HEAD) + 5))
    patched[TRAMPOLINE:TRAMPOLINE + len(trampoline)] = trampoline
    patched[FILENAME:FILENAME + 10] = b"HANME.FNT\0"
    patched[LOAD_STARTED:LOAD_STARTED + 8] = bytes(8)
    patched[WRAPPER:WRAPPER + 6] = b"\xE9" + struct.pack("<i", HOOK - (WRAPPER + 5)) + b"\x90"
    stack = struct.unpack_from('<I', exp_file, 0x62)[0]
    if len(patched) >= stack - PMB_STACK_BUDGET:
        raise ValueError(
            f"runtime image end {len(patched):#x} overlaps the reserved PMB "
            f"stack range starting at {stack - PMB_STACK_BUDGET:#x}")
    for row in rows:
        rec = row["record_address"]
        expected_head = struct.pack("<HHH", int(row["x"]), int(row["y"]), len(row["encoded"]))
        if patched[rec:rec + RECORD_SIZE] != expected_head + row["encoded"] + bytes(TEXT_CAPACITY - len(row["encoded"])):
            raise AssertionError(f"opening row data mismatch at {row['exp_offset']}")
    return bytes(patched), code
