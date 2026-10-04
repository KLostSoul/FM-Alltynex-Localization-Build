"""Apply the 77 verified ASCII SPR UI fields without moving adjacent data."""
from __future__ import annotations

import re
import struct

TYPES = {'ASCII_UI', 'SPR_TITLE'}
TITLE = 0x3F32E
FORMAT = re.compile(r'%(?:[-+ #0]*\d*(?:\.\d+)?[hlL]?[diuoxXscfegpn]|%)')
# Padding in the English reference that differs from the Japanese source.
TEXT_PADDING = {(0x3BFEC, 'ATTACK THE ENEMY'): (b'@@@@', b''),
                (0x3E89C, 'HIGH SCORE TABLE'): (b'@@@@@', b'@@@@@')}


def validate_sprite_text(text: str) -> None:
    if not text.isascii() or any(ord(char) < 0x20 or ord(char) == 0x7F for char in text):
        raise ValueError('SPR UI requires printable ASCII characters')


def encode_sprite_ascii(text: str) -> bytes:
    validate_sprite_text(text)
    output = bytearray()
    position = 0
    for match in FORMAT.finditer(text):
        output.extend(text[position:match.start()].replace(' ', '@').replace('.', ':').encode('ascii'))
        output.extend(match.group().encode('ascii'))
        position = match.end()
    output.extend(text[position:].replace(' ', '@').replace('.', ':').encode('ascii'))
    return bytes(output)


def image_offsets(exp: bytes, wanted: set[int]) -> dict[int, int]:
    """Map offsets in P3 literal blocks to their decompressed image addresses."""
    start = struct.unpack_from('<I', exp, 0x26)[0]
    packed_size = struct.unpack_from('<I', exp, 0x2A)[0]
    if not struct.unpack_from('<H', exp, 0x72)[0] & 1:
        return {offset: offset - start for offset in wanted if start <= offset < start + packed_size}
    result = {}
    position, out = start, 0
    while position < start + packed_size:
        control = struct.unpack_from('<H', exp, position)[0]
        position += 2
        if control & 0x8000:
            count, block_size = control & 0x7FFF, exp[position]
            position += 1 + block_size
            out += count
        else:
            for offset in wanted:
                if position <= offset < position + control:
                    result[offset] = out + offset - position
            position += control
            out += control
    if result.keys() != wanted:
        raise ValueError(f'UI offsets outside P3 literal blocks: {wanted - result.keys()}')
    return result


def ui_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = {}
    ascii_rows = [row for row in rows if row['type'] == 'ASCII_UI']
    if len(ascii_rows) != 77 or len({int(row['exp_offset'], 16) for row in ascii_rows}) != 77:
        raise ValueError('CSV must contain the 77 verified ASCII_UI addresses')
    for row in rows:
        if row['type'] not in TYPES:
            continue
        offset = int(row['exp_offset'], 16)
        if row['type'] == 'SPR_TITLE' and offset != TITLE:
            raise ValueError(f'Unknown SPR title offset: {offset:#x}')
        old = selected.get(offset)
        if old is None:
            selected[offset] = row
        elif old['korean_patch'] != row['korean_patch']:
            if old['japanese_original'] != row['japanese_original']:
                raise ValueError(f'Duplicate source text differs at {offset:#x}')
            old_changed = old['korean_patch'] != old['japanese_original']
            new_changed = row['korean_patch'] != row['japanese_original']
            if old_changed and new_changed:
                raise ValueError(f'ASCII_UI and SPR_TITLE translations conflict at {offset:#x}')
            if new_changed:
                selected[offset] = row
    return [selected[key] for key in sorted(selected)]


def apply_ui_strings(image: bytes, exp: bytes, rows: list[dict[str, str]]) -> tuple[bytes, list[dict]]:
    offsets = image_offsets(exp, {int(row['exp_offset'], 16) for row in rows})
    patched = bytearray(image)
    manifest = []
    for row in rows:
        raw = int(row['exp_offset'], 16)
        offset = offsets[raw]
        end = image.find(b'\0', offset)
        if end < offset:
            raise ValueError(f'UI source terminator missing at {raw:#x}')
        source = image[offset:end]
        expected = row['japanese_original'].replace(' ', '@').encode('ascii')
        if source.strip(b'@') != expected:
            raise ValueError(f'UI source mismatch at {raw:#x}: {source!r}')
        text = row['korean_patch']
        try:
            validate_sprite_text(text)
        except ValueError as exc:
            raise ValueError(f'{raw:#x}: {exc}') from exc
        if (FORMAT.findall(text) != FORMAT.findall(row['japanese_original'])
                or '%' in FORMAT.sub('', text)):
            raise ValueError(f'{raw:#x}: replacement must preserve printf format specifiers')
        if text == row['japanese_original']:
            replacement = source
        else:
            leading = source[:len(source) - len(source.lstrip(b'@'))]
            trailing = source[len(source.rstrip(b'@')):]
            if (raw, text) in TEXT_PADDING:
                leading, trailing = TEXT_PADDING[raw, text]
            # The sprite font uses ':' for the glyph visually displayed as '.'.
            replacement = leading + encode_sprite_ascii(text) + trailing
        # Option values live in fixed 32-byte records. Other fields have at most
        # verified zero padding up to the next four-byte boundary.
        fixed_table = (0x3E31C <= raw <= 0x3E49C and (raw - 0x3E31C) % 32 == 0
                       or 0x3E7BC <= raw <= 0x3E87C and (raw - 0x3E7BC) % 32 == 0)
        limit = offset + 32 if fixed_table else (end + 4) & ~3
        safe_end = end + 1
        while safe_end < limit and image[safe_end] == 0:
            safe_end += 1
        capacity = safe_end - offset
        if len(replacement) + 1 > capacity:
            raise ValueError(f'{raw:#x}: SPR text needs {len(replacement) + 1} bytes including NUL; slot holds {capacity}')
        patched[offset:safe_end] = replacement + bytes(capacity - len(replacement))
        manifest.append({'exp_offset': row['exp_offset'], 'runtime_offset': f'0x{offset:X}',
                         'capacity': capacity, 'encoded_bytes': len(replacement),
                         'korean_patch': text, 'stored_text': replacement.decode('ascii')})
    # The score footer and RANKING share a contiguous sprite allocation.
    # Spaces advance X but do not consume a sprite in the 0x26C9C loop.
    footer = next(item for item in manifest if int(item['exp_offset'], 16) == 0x3E89C)
    sprite_count = sum(char != '@' for char in footer['stored_text'])
    footer_start = min(0x2E7, 0x2FD - sprite_count)
    # 0x2E6 is the spare slot immediately preceding this screen's footer.
    if footer_start < 0x2E6:
        raise ValueError('Score footer exceeds its 23 available sprite slots')
    instruction = bytes.fromhex('68 E7 02 00 00 68 8C E6 03 00')
    call_offset = 0x2D227
    if image[call_offset:call_offset + len(instruction)] != instruction:
        raise ValueError('Score footer sprite allocation instruction differs from the verified source')
    struct.pack_into('<I', patched, call_offset + 1, footer_start)
    return bytes(patched), manifest


def clear_last_area_unused_sprite(image: bytes, scratch: int) -> bytes:
    """Clear loading's leftover slot before the shorter LAST AREA title draws."""
    import alltynex_binary as binary
    patched = bytearray(image)
    site = 0x13C88
    original = bytes.fromhex('A1 94 EE 08 00')
    if patched[site:site + 5] != original:
        raise ValueError('Last-area title entry differs from the verified source')
    a = binary.Asm(scratch)
    a.emit(0x9C, 0x60)  # preserve flags and all general registers
    # Use the original game's removal attributes: blank pattern 0x80,
    # color/attribute 0xA100, a single cell at sprite slot 0x3C2.
    for value in (0xA100, 0x80, 1, 1, 0x3C2):
        a.emit(0x68)
        a.dword(value)
    a.call(0x33D7C)
    a.emit(0x83, 0xC4, 0x14, 0x61, 0x9D)
    a.emit(*original)  # displaced MOV EAX,[0x8EE94]
    a.emit(0xC3)
    code = a.finish()
    if len(code) > 0x80 or any(patched[scratch:scratch + len(code)]):
        raise ValueError('Sprite cleanup code must fit the reserved empty hook space')
    patched[scratch:scratch + len(code)] = code
    patched[site:site + 5] = b'\xE8' + struct.pack('<i', scratch - site - 5)
    return bytes(patched)
