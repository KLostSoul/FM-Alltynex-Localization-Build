#!/usr/bin/env python3
"""Build Alltynex's explicit Hangul composition-token table from translations."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = ROOT / "Import" / "Strings" / "Alltynex_Korean.csv"
OUTPUT_CSV = ROOT / "Import" / "Strings" / "Alltynex_Hangul_Tokens.csv"
FONT_PATH = ROOT / "font" / "HANME.FNT"

sys.path.insert(0, str(ROOT / "tools"))
from alltynex_font import component_indices, make_font  # noqa: E402
from alltynex_lock import exclusive_workspace  # noqa: E402


CHOSEONG = tuple("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")
JUNGSEONG = tuple("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")
JONGSEONG = (
    "", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ",
    "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ",
    "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
)

# Shift-JIS user-defined lead bytes and valid trail-byte ranges. This table
# assigns lookup IDs; the L/V/T indices and payload are stored explicitly.
TOKEN_LEADS = (0xF0, 0xF1)
TOKEN_TRAILS = tuple(range(0x40, 0x7F)) + tuple(range(0x80, 0xFD))

FIELDS = (
    "token_index", "token", "token_hi", "token_lo", "syllable", "unicode",
    "frequency", "source_rows", "initial", "medial", "final",
    "initial_index", "medial_index", "final_index", "composition_payload",
    "hanme_initial_slot", "hanme_medial_slot", "hanme_final_slot",
    "font_components_nonempty", "source",
)


def load_source(path: Path = SOURCE_CSV) -> tuple[Counter[str], dict[str, set[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "korean_patch" not in rows[0]:
        raise RuntimeError(f"Missing Korean translation column in {path}")

    frequencies: Counter[str] = Counter()
    row_ids: dict[str, set[str]] = defaultdict(set)
    for row_number, row in enumerate(rows, start=2):
        text = row.get("korean_patch") or ""
        row_id = row.get("exp_offset") or str(row_number)
        for character in text:
            if "\uac00" <= character <= "\ud7a3":
                frequencies[character] += 1
                row_ids[character].add(row_id)
    return frequencies, row_ids


def load_previous_tokens(path: Path = OUTPUT_CSV) -> dict[str, tuple[int, int]]:
    if not path.exists():
        return {}
    by_syllable, _rows = read_token_table(path)
    return {syllable: tuple(token) for syllable, token in by_syllable.items()}


def read_token_table(path: Path) -> tuple[dict[str, bytes], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: int(row["token_index"]))
    if not rows or [int(row["token_index"]) for row in rows] != list(range(len(rows))):
        raise ValueError(f"{path}: token indexes must be consecutive from zero")
    valid = {bytes(token) for token in valid_tokens()}
    by_syllable: dict[str, bytes] = {}
    seen: set[bytes] = set()
    for row in rows:
        syllable, token = row["syllable"], bytes.fromhex(row["token"])
        if (len(syllable) != 1 or not "가" <= syllable <= "힣"
                or token not in valid or syllable in by_syllable or token in seen):
            raise ValueError(f"{path}: invalid or duplicate token row: {row}")
        by_syllable[syllable] = token
        seen.add(token)
    return by_syllable, rows


def valid_tokens() -> list[tuple[int, int]]:
    return [(lead, trail) for lead in TOKEN_LEADS for trail in TOKEN_TRAILS]


def assign_tokens(syllables: set[str], previous: dict[str, tuple[int, int]]) -> dict[str, tuple[int, int]]:
    assignments: dict[str, tuple[int, int]] = {}
    for syllable, token in previous.items():
        if syllable in syllables and token in valid_tokens():
            assignments[syllable] = token

    occupied = set(assignments.values())
    available = (token for token in valid_tokens() if token not in occupied)
    for syllable in sorted(syllables - assignments.keys(), key=ord):
        try:
            assignments[syllable] = next(available)
        except StopIteration as exc:
            raise RuntimeError("Exhausted the configured two-byte token space") from exc

    if len(set(assignments.values())) != len(assignments):
        raise RuntimeError("Duplicate token assignment")
    return assignments


def decompose(syllable: str) -> tuple[int, int, int]:
    offset = ord(syllable) - 0xAC00
    initial, remainder = divmod(offset, 21 * 28)
    medial, final = divmod(remainder, 28)
    return initial, medial, final


def check_font(data: bytes | None = None) -> tuple[bytes, int]:
    if data is None:
        data = FONT_PATH.read_bytes()
    if len(data) != 16 + 360 * 72:
        raise RuntimeError(f"Unexpected HANME.FNT length: {len(data)}")
    if data[:8] != b"HMEFNT01" or int.from_bytes(data[8:10], "little") != 360:
        raise RuntimeError("HANME.FNT header does not match the 360-cell 24x24 format")
    if data[10:12] != bytes((24, 24)) or int.from_bytes(data[12:16], "little") != 72:
        raise RuntimeError("HANME.FNT glyph dimensions or stride differ")
    return data, int.from_bytes(data[12:16], "little")


def build_rows(
    frequencies: Counter[str],
    row_ids: dict[str, set[str]],
    tokens: dict[str, tuple[int, int]],
    font: bytes,
    glyph_bytes: int,
) -> list[dict[str, object]]:
    all_syllables = set(tokens)
    rows: list[dict[str, object]] = []
    for syllable in sorted(all_syllables, key=lambda item: tokens[item]):
        initial, medial, final = decompose(syllable)
        initial_slot, medial_slot, final_slot = component_indices(syllable)
        slots = [initial_slot, medial_slot] + ([] if final_slot is None else [final_slot])
        nonempty = all(
            any(font[16 + slot * glyph_bytes:16 + (slot + 1) * glyph_bytes])
            for slot in slots
        )
        if any(slot < 0 or slot >= 360 for slot in slots):
            raise RuntimeError(f"FNT component slot out of range for U+{ord(syllable):04X}")
        if not nonempty:
            raise RuntimeError(f"Empty HANME.FNT component used by U+{ord(syllable):04X}")

        hi, lo = tokens[syllable]
        frequency = frequencies[syllable]
        source = "translation-csv"
        if frequency == 0:
            source = "previous-table-retained"
        payload = (initial << 10) | (medial << 5) | final
        rows.append({
            "token_index": len(rows),
            "token": f"{hi:02X}{lo:02X}",
            "token_hi": f"{hi:02X}",
            "token_lo": f"{lo:02X}",
            "syllable": syllable,
            "unicode": f"U+{ord(syllable):04X}",
            "frequency": frequency,
            "source_rows": len(row_ids.get(syllable, set())),
            "initial": CHOSEONG[initial],
            "medial": JUNGSEONG[medial],
            "final": JONGSEONG[final],
            "initial_index": initial,
            "medial_index": medial,
            "final_index": final,
            "composition_payload": f"0x{payload:04X}",
            "hanme_initial_slot": initial_slot,
            "hanme_medial_slot": medial_slot,
            "hanme_final_slot": "" if final_slot is None else final_slot,
            "font_components_nonempty": "yes",
            "source": source,
        })
    return rows


@exclusive_workspace
def ensure_token_table(source: Path, destination: Path, font: bytes) -> tuple[int, list[dict[str, object]]]:
    """Preserve previous IDs and append tokens for newly used Hangul syllables."""
    old_tokens = load_previous_tokens(destination)
    frequencies, row_ids = load_source(source)
    # Keep prior token IDs stable even if a syllable is temporarily removed
    # from the translation source and reintroduced later.
    syllables = set(frequencies) | set(old_tokens)
    tokens = assign_tokens(syllables, old_tokens)
    font, glyph_bytes = check_font(font)
    rows = build_rows(frequencies, row_ids, tokens, font, glyph_bytes)
    # CSV presentation order is independent of the runtime table index.
    rows.sort(key=lambda row: row["syllable"])
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    output = stream.getvalue().encode("utf-8-sig")
    if not destination.exists() or destination.read_bytes() != output:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(output)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return len(tokens.keys() - old_tokens.keys()), rows


def main() -> None:
    font = make_font()
    added, rows = ensure_token_table(SOURCE_CSV, OUTPUT_CSV, font)
    print(f"Created: {OUTPUT_CSV}")
    print(f"Added tokens: {added}")
    print(f"Token rows: {len(rows)}")
    print(f"All referenced HANME.FNT cells nonempty: {all(r['font_components_nonempty'] == 'yes' for r in rows)}")
    print(f"HANME.FNT MD5: {hashlib.md5(font).hexdigest().upper()}")


if __name__ == "__main__":
    main()
