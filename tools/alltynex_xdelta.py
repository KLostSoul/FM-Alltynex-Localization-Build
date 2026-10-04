"""Create a ZIP-to-ISO xdelta with the bundled xdelta3 executable."""
from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "tools" / "xdelta3.exe"


def find_xdelta(explicit: Path | None = None) -> Path:
    if explicit is not None:
        executable = explicit.resolve()
        if not executable.is_file():
            raise FileNotFoundError(f"xdelta3 executable not found: {executable}")
        return executable
    if os.name == "nt" and platform.machine().lower() in ("amd64", "x86_64"):
        if EXECUTABLE.is_file():
            return EXECUTABLE
    installed = shutil.which("xdelta3")
    if installed:
        return Path(installed)
    raise FileNotFoundError("xdelta3 not found: use tools/xdelta3.exe on Windows x64, "
                            "install xdelta3 on PATH, or pass --xdelta3 PATH.")


def create_patch(executable: Path, source_zip: Path, target_iso: Path,
                 patch_path: Path) -> None:
    """Use the original ZIP bytes as source; publish only a completed patch."""
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="alltynex-xdelta-", dir=patch_path.parent) as directory:
        temporary = Path(directory) / patch_path.name
        environment = dict(os.environ)
        environment.pop("XDELTA", None)
        # -D keeps the ZIP compressed bytes as the source. Disable automatic
        # file headers so the patch does not contain local absolute paths.
        subprocess.run([str(executable), "-e", "-9", "-D", "-A=", "-s",
                        str(source_zip), str(target_iso), str(temporary)],
                       check=True, env=environment)
        temporary.replace(patch_path)
