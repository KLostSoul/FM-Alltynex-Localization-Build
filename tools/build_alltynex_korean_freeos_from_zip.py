#!/usr/bin/env python3
"""Build the Korean opening and CSV SPR UI FreeTOWNSOS ISO from source assets.

The Japanese game ZIP is the sole source of game files.  The FreeTOWNSOS
release CD image supplies the bootable OS files; this script adds the game
directory, applies the existing Korean opening hook and all 77 SPR UI fields to
the ZIP's Japanese ALLTYNEX.EXP, installs HANME.FNT, and boots RUN386 directly.
"""
from __future__ import annotations

import argparse
import hashlib
import csv
import re
import shutil
import struct
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import alltynex_font as activity  # noqa: E402
import alltynex_egb as opening  # noqa: E402
import alltynex_binary as iso_util  # noqa: E402
import build_hangul_composition_token_table as composition  # noqa: E402
import build_alltynex_ui_strings as ui  # noqa: E402
import alltynex_xdelta as xdelta  # noqa: E402
from alltynex_lock import exclusive_workspace, WorkspaceBusyError  # noqa: E402

IMPORT_DIR = ROOT / "Import"
IMPORT_STRINGS = IMPORT_DIR / "Strings"
ZIP_PATH = IMPORT_DIR / "Img" / "alltynex_fmtowns.zip"
TRANSLATION_CSV = IMPORT_STRINGS / "Alltynex_Korean.csv"
TOKEN_CSV = IMPORT_STRINGS / "Alltynex_Hangul_Tokens.csv"
FREEOS_ISO = IMPORT_DIR / "Img" / "CDIMG.ISO"
OUTPUT_DIR = ROOT / "Output"
OUTPUT_ISO = OUTPUT_DIR / "Alltynex (Kor v1.0).iso"
OUTPUT_XDELTA = OUTPUT_DIR / "Alltynex (Kor v1.0).xdelta"

ZIP_SHA256 = "19b662f038e50e99535f60dbe6e07a77e269f574ed9250d46fc0655bb2aa6b3a"
FREEOS_ISO_SHA256 = "cf05150bb1db4e82dc2fd7b617cf4dd8f222f88b36b06589054748b2097e7142"
SECTOR = iso_util.SECTOR
PVD_LBA = iso_util.PVD_LBA
GAME_DIR = b"ALLTYNEX"
GAME_PREFIX = "alltynex_fmtowns"
KRSTART_NAME = b"KRSTART.BAT;1"
KRSTART = (b"FORCE31K.COM\r\n"
           b"CD \\ALLTYNEX\r\n"
           b"RUN386.EXE -nocrt ALLTYNEX\r\n")
AUTOEXEC_OLD = b"/K FORCE31K.COM"
AUTOEXEC_NEW = b"/K KRSTART.BAT "
DOS_83 = re.compile(r"^[A-Z0-9_]{1,8}\.[A-Z0-9_]{1,3}$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_sha256(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    actual = sha256(data)
    if actual != expected:
        raise ValueError(f"unexpected SHA-256 for {path}: {actual} (expected {expected})")
    return data


def read_iso_path(iso: bytes, components: tuple[bytes, ...]) -> bytes:
    pvd_off = PVD_LBA * SECTOR
    pvd = iso[pvd_off:pvd_off + SECTOR]
    if pvd[:7] != b"\x01CD001\x01":
        raise ValueError("input does not have an ISO9660 primary volume descriptor")
    record = pvd[156:156 + pvd[156]]
    lba, size = iso_util.extent_size(record)
    for component in components:
        _, record, _ = iso_util.find_child(iso, lba, size, component)
        lba, size = iso_util.extent_size(record)
    start = lba * SECTOR
    end = start + size
    if end > len(iso):
        raise ValueError(f"ISO path {components!r} points outside the image")
    return iso[start:end]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def token_data() -> tuple[dict[str, bytes], list[dict[str, str]]]:
    return composition.read_token_table(TOKEN_CSV)


def translation_rows() -> list[dict[str, str]]:
    required = {"type", "exp_offset", "x", "y", "korean_patch"}
    rows = read_csv(TRANSLATION_CSV)
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"{TRANSLATION_CSV} is missing required translation columns")
    return rows


def opening_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    opening_rows = [row for row in rows
                    if row["type"] == "EGB_STRING" and
                    0x3E910 <= int(row["exp_offset"], 16) <= 0x3F278]
    opening_rows.sort(key=lambda row: int(row["exp_offset"], 16))
    if (len(opening_rows) != 29 or
            int(opening_rows[0]["exp_offset"], 16) != 0x3E910 or
            int(opening_rows[-1]["exp_offset"], 16) != 0x3F278):
        raise ValueError(f"{TRANSLATION_CSV} must contain the 29 verified opening rows")
    return opening_rows


def ending_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    expected = {0x3C41C + index * opening.RECORD_SIZE for index in range(6)}
    selected = [row for row in rows if row['type'] == 'EGB_STRING'
                and int(row['exp_offset'], 16) in expected]
    selected.sort(key=lambda row: int(row['exp_offset'], 16))
    if len(selected) != 6 or {int(row['exp_offset'], 16) for row in selected} != expected:
        raise ValueError('CSV must contain the six verified ending EGB rows')
    return selected


def staff_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = [row for row in rows if row['type'] == 'EGB_STRING'
                and 0x3C6B8 <= int(row['exp_offset'], 16) < 0x3C6B8 + 80 * opening.RECORD_SIZE]
    selected.sort(key=lambda row: int(row['exp_offset'], 16))
    offsets = [int(row['exp_offset'], 16) for row in selected]
    if len(offsets) != 39 or len(set(offsets)) != 39:
        raise ValueError('CSV must contain the 39 verified staff-roll translation rows')
    if any((offset - 0x3C6B8) % opening.RECORD_SIZE for offset in offsets):
        raise ValueError('Staff-roll row is not aligned to its 86-byte record')
    return selected


def zip_game_files(path: Path) -> dict[bytes, bytes]:
    require_sha256(path, ZIP_SHA256)
    result: dict[bytes, bytes] = {}
    with zipfile.ZipFile(path, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"ZIP CRC check failed for {bad_member}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if info.is_dir():
                if pure.parts != (GAME_PREFIX,):
                    raise ValueError(f"unexpected ZIP directory: {info.filename!r}")
                continue
            if len(pure.parts) != 2 or pure.parts[0] != GAME_PREFIX:
                raise ValueError(f"unexpected path in game ZIP: {info.filename!r}")
            filename = pure.parts[1].upper()
            if not DOS_83.fullmatch(filename):
                raise ValueError(f"game filename is not DOS 8.3: {filename!r}")
            iso_name = filename.encode("ascii") + b";1"
            if iso_name in result:
                raise ValueError(f"duplicate game filename: {filename}")
            result[iso_name] = archive.read(info)
    if len(result) != 96 or b"ALLTYNEX.EXP;1" not in result:
        raise ValueError(f"expected 96 game files including ALLTYNEX.EXP, got {len(result)}")
    return result


def patch_original_exp(game_files: dict[bytes, bytes], font: bytes,
                       token_by_syllable: dict[str, bytes],
                       component_rows: list[dict[str, str]],
                       rows: list[dict[str, str]],
                       ui_rows: list[dict[str, str]]) -> tuple[dict[bytes, bytes], bytes, list[dict]]:
    exp_name = b"ALLTYNEX.EXP;1"
    original_exp = game_files[exp_name]
    if sha256(original_exp) != "f3b029b22423611a05daae5cec65a8d387bb16ea60286b5c4aead062d2fcb4e1":
        raise ValueError("ZIP ALLTYNEX.EXP does not match the inspected Japanese original")
    runtime_image, code = opening.make_hook_image(
        original_exp, rows, token_by_syllable, component_rows)
    runtime_image, ui_manifest = ui.apply_ui_strings(runtime_image, original_exp, ui_rows)
    sprite_cleanup = opening.TRAMPOLINE - 0x80
    if opening.HOOK + len(code) > sprite_cleanup:
        raise ValueError('EGB hook overlaps the reserved sprite cleanup space')
    runtime_image = ui.clear_last_area_unused_sprite(runtime_image, sprite_cleanup)
    patched_exp = iso_util.make_p3(original_exp, runtime_image)
    round_trip = iso_util.expand_p3(patched_exp)
    stack = struct.unpack_from('<I', patched_exp, 0x62)[0]
    expected_stack = struct.unpack_from('<I', original_exp, 0x62)[0]
    if stack != expected_stack or len(runtime_image) >= stack - opening.PMB_STACK_BUDGET:
        raise ValueError('EXP must preserve the original stack and avoid the PMB loading reservation')
    for row in rows:
        offset = row['record_address']
        if round_trip[offset:offset + opening.RECORD_SIZE] != runtime_image[offset:offset + opening.RECORD_SIZE]:
            raise ValueError(f"EXP round-trip lost EGB record at {row['exp_offset']}")
    for item in ui_manifest:
        offset = int(item['runtime_offset'], 16)
        expected = item['stored_text'].encode('ascii') + b'\0'
        if round_trip[offset:offset + len(expected)] != expected:
            raise ValueError(f"EXP round-trip lost UI text at {item['exp_offset']}")
    if len(code) >= opening.TRAMPOLINE - opening.HOOK:
        raise AssertionError("opening hook collided with its trampoline")
    result = dict(game_files)
    result[exp_name] = patched_exp
    result[b"HANME.FNT;1"] = font
    if len(rows) != 74:
        raise AssertionError("the opening, staff-roll and ending patch must contain 74 EGB rows")
    return result, patched_exp, ui_manifest


def round_up(value: int, alignment: int = SECTOR) -> int:
    return (value + alignment - 1) // alignment * alignment


def directory_record(name: bytes, lba: int, size: int, is_dir: bool = False) -> bytearray:
    record = bytearray(iso_util.iso_record(name, lba, size))
    if is_dir:
        record[25] |= 0x02
    return record


def set_record_extent(record: bytearray, lba: int, size: int) -> None:
    iso_util.write_dual32(record, 2, lba)
    iso_util.write_dual32(record, 10, size)


def serialize_directory(entries: list[tuple[bytes, bytearray]]) -> bytes:
    out = bytearray()
    for _name, record in sorted(entries, key=lambda pair: pair[0]):
        if (len(out) % SECTOR) + len(record) > SECTOR:
            out.extend(bytes(SECTOR - len(out) % SECTOR))
        out.extend(record)
    return bytes(out + bytes(round_up(len(out)) - len(out)))


def path_table(entries: list[tuple[bytes, int, int]], endian: str) -> bytes:
    out = bytearray()
    for identifier, lba, parent in entries:
        if len(identifier) > 255:
            raise ValueError("ISO directory identifier is too long")
        out.extend((len(identifier), 0))
        out.extend(struct.pack(endian + "I", lba))
        out.extend(struct.pack(endian + "H", parent))
        out.extend(identifier)
        if len(identifier) & 1:
            out.append(0)
    return bytes(out)


def patch_path_tables(image: bytearray, game_lba: int) -> None:
    entries = [(b"\x00", 20, 1), (GAME_DIR, game_lba, 1), (b"TESTS", 21, 1)]
    entries.sort(key=lambda item: item[0])
    little = path_table(entries, "<")
    big = path_table(entries, ">")
    if len(little) != len(big):
        raise AssertionError("primary path table endian encodings differ in size")
    if round_up(len(little)) != SECTOR or round_up(len(big)) != SECTOR:
        raise ValueError("primary path tables no longer fit in their planned single sectors")

    little_lba = len(image) // SECTOR
    image.extend(little)
    image.extend(bytes(round_up(len(little)) - len(little)))
    big_lba = len(image) // SECTOR
    image.extend(big)
    image.extend(bytes(round_up(len(big)) - len(big)))

    pvd_off = PVD_LBA * SECTOR
    iso_util.write_dual32(image, pvd_off + 132, len(little))
    struct.pack_into("<I", image, pvd_off + 140, little_lba)
    struct.pack_into(">I", image, pvd_off + 148, big_lba)
    struct.pack_into("<I", image, pvd_off + 144, 0)
    struct.pack_into(">I", image, pvd_off + 152, 0)


def build_image(os_iso: bytes, files: dict[bytes, bytes]) -> bytes:
    if len(os_iso) % SECTOR:
        raise ValueError("FreeTOWNSOS base ISO is not sector aligned")
    image = bytearray(os_iso)
    pvd_off = PVD_LBA * SECTOR
    pvd = image[pvd_off:pvd_off + SECTOR]
    if pvd[:7] != b"\x01CD001\x01":
        raise ValueError("FreeTOWNSOS base has no ISO9660 primary descriptor")

    root_record = bytearray(pvd[156:156 + pvd[156]])
    root_lba, original_root_size = iso_util.extent_size(root_record)
    if root_lba != 20:
        raise ValueError(f"unexpected FreeTOWNSOS root location {root_lba}")
    root_sector_size = round_up(original_root_size)
    if root_sector_size != SECTOR:
        raise ValueError("expected FreeTOWNSOS root directory to occupy one sector")

    root_entries: list[tuple[bytes, bytearray]] = []
    root_data = image[root_lba * SECTOR:root_lba * SECTOR + original_root_size]
    for _pos, record, name in iso_util.records(root_data):
        mutable = bytearray(record)
        if name in (b"\x00", b"\x01"):
            set_record_extent(mutable, root_lba, root_sector_size)
        elif name.split(b";", 1)[0].upper() == b"AUTOEXEC.BAT":
            lba, size = iso_util.extent_size(mutable)
            start = lba * SECTOR
            old_auto = bytes(image[start:start + size])
            if len(AUTOEXEC_OLD) != len(AUTOEXEC_NEW) or old_auto.count(AUTOEXEC_OLD) != 1:
                raise ValueError("FreeTOWNSOS AUTOEXEC does not match the reviewed boot command")
            image[start:start + size] = old_auto.replace(AUTOEXEC_OLD, AUTOEXEC_NEW)
        root_entries.append((name, mutable))

    existing_names = {name.split(b";", 1)[0].upper() for name, _ in root_entries}
    if GAME_DIR in existing_names or b"KRSTART.BAT" in existing_names:
        raise ValueError("FreeTOWNSOS seed unexpectedly already contains game startup files")
    tests_record = next((record for name, record in root_entries if name == b"TESTS"), None)
    if tests_record is None:
        raise ValueError("FreeTOWNSOS source image has no expected TESTS directory")

    # Preserve FreeTOWNSOS test files and fix the parent directory size because
    # the root extent is expanded to its full reserved sector.
    tests_lba, tests_size = iso_util.extent_size(tests_record)
    tests_dir = bytearray(image[tests_lba * SECTOR:tests_lba * SECTOR + tests_size])
    for pos, record, name in iso_util.records(tests_dir):
        if name == b"\x01":
            mutable = bytearray(record)
            set_record_extent(mutable, root_lba, root_sector_size)
            tests_dir[pos:pos + len(mutable)] = mutable
            break
    else:
        raise ValueError("FreeTOWNSOS TESTS directory has no '..' entry")
    image[tests_lba * SECTOR:tests_lba * SECTOR + tests_size] = tests_dir

    # Allocate path tables first, then one multi-sector game directory.
    game_lba = len(image) // SECTOR + 2  # each path-table copy fits in one sector
    patch_path_tables(image, game_lba)
    game_names = sorted(files)
    provisional = [(b"\x00", directory_record(b"\x00", game_lba, 0, True)),
                   (b"\x01", directory_record(b"\x01", root_lba, root_sector_size, True))]
    provisional.extend((name, directory_record(name, 0, len(files[name]))) for name in game_names)
    game_dir_size = len(serialize_directory(provisional))
    game_dir_sectors = game_dir_size // SECTOR
    data_lba = game_lba + game_dir_sectors
    image.extend(bytes(game_dir_size))

    game_entries = [
        (b"\x00", directory_record(b"\x00", game_lba, game_dir_size, True)),
        (b"\x01", directory_record(b"\x01", root_lba, root_sector_size, True)),
    ]
    file_records: dict[bytes, bytearray] = {}
    for name in game_names:
        payload = files[name]
        file_records[name] = directory_record(name, data_lba, len(payload))
        image.extend(payload)
        image.extend(bytes(round_up(len(payload)) - len(payload)))
        data_lba += round_up(len(payload)) // SECTOR
        game_entries.append((name, file_records[name]))

    game_directory = serialize_directory(game_entries)
    if len(game_directory) != game_dir_size:
        raise AssertionError("game directory size changed after assigning file extents")
    image[game_lba * SECTOR:game_lba * SECTOR + game_dir_size] = game_directory

    # Put the game startup chain in the FreeTOWNSOS root.
    krstart_lba = len(image) // SECTOR
    image.extend(KRSTART)
    image.extend(bytes(round_up(len(KRSTART)) - len(KRSTART)))
    root_entries.append((KRSTART_NAME, directory_record(KRSTART_NAME, krstart_lba, len(KRSTART))))
    root_entries.append((GAME_DIR, directory_record(GAME_DIR, game_lba, game_dir_size, True)))
    root_directory = serialize_directory(root_entries)
    if len(root_directory) > root_sector_size:
        raise ValueError("FreeTOWNSOS root directory has no room for startup entries")
    image[root_lba * SECTOR:root_lba * SECTOR + root_sector_size] = root_directory
    set_record_extent(root_record, root_lba, root_sector_size)
    image[pvd_off + 156:pvd_off + 156 + len(root_record)] = root_record
    iso_util.write_dual32(image, pvd_off + 80, len(image) // SECTOR)

    verify_iso(image, os_iso, files, krstart_lba, game_lba, game_dir_size)
    return bytes(image)


def walk_directory(iso: bytes, record: bytes) -> list[tuple[int, bytes, bytes]]:
    lba, size = iso_util.extent_size(record)
    start = lba * SECTOR
    if start + size > len(iso):
        raise ValueError("directory extent points outside the ISO")
    directory = iso[start:start + size]
    result = list(iso_util.records(directory))
    for pos, entry, _name in result:
        if pos // SECTOR != (pos + len(entry) - 1) // SECTOR:
            raise ValueError("ISO9660 directory record crosses a sector boundary")
    return result


def extract_path(iso: bytes, components: tuple[bytes, ...]) -> bytes:
    pvd = iso[PVD_LBA * SECTOR:(PVD_LBA + 1) * SECTOR]
    record = pvd[156:156 + pvd[156]]
    lba, size = iso_util.extent_size(record)
    for component in components:
        _, record, _ = iso_util.find_child(iso, lba, size, component)
        lba, size = iso_util.extent_size(record)
    return iso[lba * SECTOR:lba * SECTOR + size]


def verify_iso(output: bytearray, os_iso: bytes, files: dict[bytes, bytes],
               krstart_lba: int, game_lba: int, game_dir_size: int) -> None:
    pvd_off = PVD_LBA * SECTOR
    pvd = output[pvd_off:pvd_off + SECTOR]
    if pvd[:7] != b"\x01CD001\x01":
        raise ValueError("final ISO lost its primary volume descriptor")
    if iso_util.read_dual32(output, pvd_off + 80) != len(output) // SECTOR:
        raise ValueError("PVD volume space size does not match final ISO size")
    if output[:16 * SECTOR] != os_iso[:16 * SECTOR]:
        raise ValueError("FreeTOWNSOS boot/lead-in sectors changed")

    root = pvd[156:156 + pvd[156]]
    root_lba, root_size = iso_util.extent_size(root)
    if (root_lba, root_size) != (20, SECTOR):
        raise ValueError("unexpected final root directory extent")
    root_records = walk_directory(output, root)
    root_names = [name for _, _, name in root_records]
    if len(root_names) != len(set(root_names)):
        raise ValueError("duplicate entry in final root directory")
    game_record = iso_util.find_child(output, root_lba, root_size, GAME_DIR)[1]
    if iso_util.extent_size(game_record) != (game_lba, game_dir_size):
        raise ValueError("root ALLTYNEX record has the wrong extent")

    game_records = walk_directory(output, game_record)
    found = {name: record for _, record, name in game_records if name not in (b"\x00", b"\x01")}
    if set(found) != set(files):
        raise ValueError(f"game directory inventory mismatch: missing={set(files)-set(found)}, extra={set(found)-set(files)}")
    for name, expected in files.items():
        lba, size = iso_util.extent_size(found[name])
        actual = output[lba * SECTOR:lba * SECTOR + size]
        if size != len(expected) or actual != expected:
            raise ValueError(
                f"final ISO payload mismatch for ALLTYNEX/{name!r}: "
                f"LBA={lba}, size={size}/{len(expected)}, "
                f"actual SHA-256={sha256(actual)}, expected SHA-256={sha256(expected)}")

    autoexec = extract_path(output, (b"AUTOEXEC.BAT",))
    original_autoexec = read_iso_path(os_iso, (b"AUTOEXEC.BAT",))
    if autoexec != original_autoexec.replace(AUTOEXEC_OLD, AUTOEXEC_NEW):
        raise ValueError("root AUTOEXEC differs from the verified FreeTOWNSOS chain")
    if extract_path(output, (b"KRSTART.BAT",)) != KRSTART:
        raise ValueError("KRSTART.BAT does not directly launch the game")
    if iso_util.extent_size(iso_util.find_child(output, root_lba, root_size, b"KRSTART.BAT")[1])[0] != krstart_lba:
        raise ValueError("KRSTART.BAT root directory LBA mismatch")
    if b"ALLTYNEX.EXE;1" in found or b"CFGDAT.SAV;1" in found:
        raise ValueError("non-ZIP game files unexpectedly entered the game directory")

    # Validate relocated ISO9660 little/big endian path tables and directory extents.
    table_size = iso_util.read_dual32(output, pvd_off + 132)
    little_lba = struct.unpack_from("<I", output, pvd_off + 140)[0]
    big_lba = struct.unpack_from(">I", output, pvd_off + 148)[0]
    little = bytes(output[little_lba * SECTOR:little_lba * SECTOR + table_size])
    big = bytes(output[big_lba * SECTOR:big_lba * SECTOR + table_size])
    expected_little = path_table([(b"\x00", root_lba, 1), (GAME_DIR, game_lba, 1),
                                  (b"TESTS", iso_util.extent_size(iso_util.find_child(output, root_lba, root_size, b"TESTS")[1])[0], 1)], "<")
    expected_big = path_table([(b"\x00", root_lba, 1), (GAME_DIR, game_lba, 1),
                               (b"TESTS", iso_util.extent_size(iso_util.find_child(output, root_lba, root_size, b"TESTS")[1])[0], 1)], ">")
    if little != expected_little or big != expected_big:
        raise ValueError("final ISO path tables do not match the directory tree")
    if little_lba * SECTOR + table_size > len(output) or big_lba * SECTOR + table_size > len(output):
        raise ValueError("final ISO path table extent is outside the image")

    # Every original FreeTOWNSOS file remains byte-identical except AUTOEXEC,
    # whose fixed-size boot command is redirected to KRSTART.BAT.
    base_root = os_iso[PVD_LBA * SECTOR + 156:]
    base_root_record = base_root[:base_root[0]]
    base_root_entries = walk_directory(os_iso, base_root_record)
    for _pos, record, name in base_root_entries:
        if name in (b"\x00", b"\x01", b"TESTS") or record[25] & 0x02:
            continue
        if name.split(b";", 1)[0].upper() == b"AUTOEXEC.BAT":
            continue
        base_bytes = read_iso_path(os_iso, (name.split(b";", 1)[0],))
        output_bytes = extract_path(output, (name.split(b";", 1)[0],))
        if output_bytes != base_bytes:
            raise ValueError(f"FreeTOWNSOS system file changed: {name!r}")

    base_tests_record = iso_util.find_child(os_iso, 20, 844, b"TESTS")[1]
    output_tests_record = iso_util.find_child(output, root_lba, root_size, b"TESTS")[1]
    base_tests_entries = walk_directory(os_iso, base_tests_record)
    output_tests_entries = walk_directory(output, output_tests_record)
    base_test_names = [name for _, _, name in base_tests_entries]
    output_test_names = [name for _, _, name in output_tests_entries]
    if base_test_names != output_test_names:
        raise ValueError("FreeTOWNSOS TESTS directory inventory changed")
    for _pos, record, name in base_tests_entries:
        if name in (b"\x00", b"\x01") or record[25] & 0x02:
            continue
        base_bytes = read_iso_path(os_iso, (b"TESTS", name.split(b";", 1)[0]))
        output_bytes = extract_path(output, (b"TESTS", name.split(b";", 1)[0]))
        if output_bytes != base_bytes:
            raise ValueError(f"FreeTOWNSOS test payload changed: {name!r}")


@exclusive_workspace
def write_outputs(output: bytes, executable: Path) -> None:
    """Publish prepared outputs, retaining recovery files if rollback fails."""
    OUTPUT_ISO.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="alltynex-build-", dir=OUTPUT_ISO.parent)).resolve()
    if staging.parent != OUTPUT_ISO.parent.resolve():
        raise ValueError("build staging directory is outside the output directory")
    keep_staging = False
    try:
        staged_iso = staging / OUTPUT_ISO.name
        staged_patch = staging / OUTPUT_XDELTA.name
        staged_iso.write_bytes(output)
        print(f"Creating xdelta from original ZIP: {ZIP_PATH}", flush=True)
        xdelta.create_patch(executable, ZIP_PATH, staged_iso, staged_patch)
        pairs = [(staged_iso, OUTPUT_ISO), (staged_patch, OUTPUT_XDELTA)]
        backups = {}
        for _, destination in pairs:
            if destination.exists():
                backup = staging / (destination.name + ".previous")
                shutil.copy2(destination, backup)
                backups[destination] = backup
        # Keep all original copies until every rollback operation succeeds.
        recovery = []
        for _, destination in pairs:
            if destination in backups:
                recovery.append(f"Restore {backups[destination].name} to {destination.resolve()}")
            else:
                recovery.append(f"Remove {destination.resolve()} (did not exist before this build)")
        (staging / "RECOVERY.txt").write_text("\n".join(recovery) + "\n", encoding="utf-8")
        published = []
        try:
            for staged, destination in pairs:
                staged.replace(destination)
                published.append(destination)
        except BaseException as publish_error:
            recovery_errors = []
            for destination in reversed(published):
                try:
                    if destination in backups:
                        restoration = staging / (destination.name + ".restore")
                        shutil.copy2(backups[destination], restoration)
                        restoration.replace(destination)
                    else:
                        destination.unlink(missing_ok=True)
                except BaseException as recovery_error:
                    recovery_errors.append(f"{destination}: {recovery_error}")
            if recovery_errors:
                keep_staging = True
                raise RuntimeError(
                    "Output rollback failed; recovery files preserved at "
                    f"{staging}. See RECOVERY.txt. " + "; ".join(recovery_errors)
                ) from publish_error
            raise
    finally:
        if not keep_staging:
            shutil.rmtree(staging)


@exclusive_workspace
def main() -> None:
    global TRANSLATION_CSV
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--translation-csv', type=Path, default=TRANSLATION_CSV,
                        help='translation CSV (defaults to Import/Strings/Alltynex_Korean.csv)')
    parser.add_argument('--xdelta3', type=Path,
                        help='xdelta3 executable (otherwise tools/xdelta3.exe on Windows x64 or PATH)')
    args = parser.parse_args()
    TRANSLATION_CSV = args.translation_csv.resolve()
    zip_files = zip_game_files(ZIP_PATH)
    xdelta_executable = xdelta.find_xdelta(args.xdelta3)
    os_iso = require_sha256(FREEOS_ISO, FREEOS_ISO_SHA256)
    font = activity.make_font()
    added_tokens, generated_rows = composition.ensure_token_table(TRANSLATION_CSV, TOKEN_CSV, font)
    print(f"Hangul token table refreshed: {len(generated_rows)} entries; {added_tokens} new tokens")
    token_by_syllable, component_rows = token_data()
    all_translation_rows = translation_rows()
    story_rows = opening_rows(all_translation_rows)
    credits_rows = staff_rows(all_translation_rows)
    final_rows = ending_rows(all_translation_rows)
    rows = story_rows + credits_rows + final_rows
    ui_rows = ui.ui_rows(all_translation_rows)
    output_files, patched_exp, ui_manifest = patch_original_exp(
        zip_files, font, token_by_syllable, component_rows, rows, ui_rows)
    output = build_image(os_iso, output_files)
    write_outputs(output, xdelta_executable)

    print(f"Input ZIP: {ZIP_PATH} ({len(zip_files)} game files; SHA-256={ZIP_SHA256})")
    print(f"Translation table: {TRANSLATION_CSV} ({sha256(TRANSLATION_CSV.read_bytes())})")
    print(f"Token table: {TOKEN_CSV} ({sha256(TOKEN_CSV.read_bytes())})")
    print(f"FreeTOWNSOS boot seed: {FREEOS_ISO} (SHA-256={FREEOS_ISO_SHA256})")
    print(f"Japanese EXP source: {sha256(zip_files[b'ALLTYNEX.EXP;1'])}")
    print(f"Korean opening patch: {len(story_rows)} EGB rows; staff roll: {len(credits_rows)} EGB rows")
    print(f"Korean ending patch: {len(final_rows)} EGB rows")
    print(f"SPR UI patch: {len(ui_manifest)} unique fields, through PROJECT RAID WIND 2")
    print(f"Output ISO: {OUTPUT_ISO}")
    print(f"Output bytes: {len(output)}; SHA-256={sha256(output)}")
    print(f"Output xdelta: {OUTPUT_XDELTA}")
    print(f"xdelta bytes: {OUTPUT_XDELTA.stat().st_size}; SHA-256={sha256(OUTPUT_XDELTA.read_bytes())}")
    print(f"Patched EXP bytes: {len(patched_exp)}; HANME.FNT bytes: {len(font)}")
    stack = struct.unpack_from('<I', patched_exp, 0x62)[0]
    print(f"EXP initial ESP: {stack:#x}; PMB stack budget: {opening.PMB_STACK_BUDGET:#x}")
    print("ISO9660 directory boundaries, path tables, ZIP payloads, FreeTOWNSOS boot files, and auto-start chain verified.")
    print("Scope: 29 opening, 39 staff-roll and 6 ending EGB rows plus all 77 ASCII SPR UI fields including the title.")
    print("The final ISO is ready for the user's emulator check.")


if __name__ == "__main__":
    try:
        main()
    except WorkspaceBusyError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
