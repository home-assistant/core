#!/usr/bin/env python3
"""Build the running interpreter's sqlite3 C module against a chosen SQLite.

Downloads the Modules/_sqlite sources for the exact CPython version that is
running plus the requested SQLite amalgamation from sqlite.org, compiles them
into the ha_sqlite3_vendor package, and installs it into the current
environment. Combined with `pytest -p tests.sqlite3_shim` this lets the test
suite run against any SQLite version, independent of the one bundled with the
interpreter. Rebuilding the module is required because uv managed interpreters
statically link SQLite with hidden symbols, so it cannot be replaced with
LD_PRELOAD.
"""

import argparse
import io
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile

DOWNLOAD_ATTEMPTS = 3
FIXTURE_DIR = Path(__file__).parent / "sqlite3_vendor"


def open_url(url: str) -> io.BufferedIOBase:
    """Open a URL for reading, retrying transient failures."""
    print(f"Downloading {url}")
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            return urllib.request.urlopen(url, timeout=60)
        except OSError as err:
            if attempt == DOWNLOAD_ATTEMPTS:
                raise
            print(f"Download failed ({err}), retrying")
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def fetch_module_sources(workdir: Path) -> None:
    """Extract Modules/_sqlite for the running CPython version into workdir/src."""
    python_version = platform.python_version()
    url = (
        f"https://github.com/python/cpython/archive/refs/tags/v{python_version}.tar.gz"
    )
    prefix = f"cpython-{python_version}/Modules/_sqlite/"
    src = workdir / "src"
    with (
        open_url(url) as response,
        tarfile.open(fileobj=response, mode="r|gz") as tar,
    ):
        seen = False
        for member in tar:
            if member.name.startswith(prefix):
                seen = True
                if member.isfile():
                    member.name = member.name.removeprefix(prefix)
                    tar.extract(member, src, filter="data")
            elif seen:
                # Tar entries are sorted, so everything wanted has been seen
                break


def fetch_amalgamation(workdir: Path, version: str, year: str) -> None:
    """Extract the SQLite amalgamation for the given version into workdir."""
    major, minor, patch = (int(part) for part in version.split("."))
    release = f"{major}{minor:02d}{patch:02d}00"
    url = f"https://www.sqlite.org/{year}/sqlite-amalgamation-{release}.zip"
    with (
        open_url(url) as response,
        zipfile.ZipFile(io.BytesIO(response.read())) as archive,
    ):
        for filename in ("sqlite3.c", "sqlite3.h"):
            data = archive.read(f"sqlite-amalgamation-{release}/{filename}")
            (workdir / filename).write_bytes(data)


def build_wheel(wheel_dir: Path, version: str, year: str) -> None:
    """Build a ha_sqlite3_vendor wheel for the given SQLite version."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir) / "build"
        shutil.copytree(FIXTURE_DIR, workdir)
        fetch_module_sources(workdir)
        fetch_amalgamation(workdir, version, year)
        subprocess.run(
            ["uv", "build", "--wheel", str(workdir), "--out-dir", str(wheel_dir)],
            check=True,
            env={**os.environ, "SQLITE_VERSION": version},
        )


def main() -> None:
    """Build and install ha_sqlite3_vendor."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="SQLite version, e.g. 3.40.1")
    parser.add_argument(
        "--year",
        required=True,
        help="Release year in the sqlite.org download URL, "
        "see https://www.sqlite.org/chronology.html",
    )
    parser.add_argument(
        "--wheel-dir",
        type=Path,
        help="Keep the built wheel here and reuse it if one already exists",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmpdir:
        wheel_dir = args.wheel_dir or Path(tmpdir)
        pattern = f"ha_sqlite3_vendor-{args.version}-*.whl"
        if wheels := sorted(wheel_dir.glob(pattern)):
            print(f"Using cached wheel {wheels[0]}")
        else:
            build_wheel(wheel_dir, args.version, args.year)
            wheels = sorted(wheel_dir.glob(pattern))
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                sys.executable,
                "--reinstall",
                str(wheels[0]),
            ],
            check=True,
        )

    subprocess.run(
        [
            sys.executable,
            "-c",
            "from ha_sqlite3_vendor import _sqlite3;"
            f"assert _sqlite3.sqlite_version == '{args.version}', _sqlite3.sqlite_version;"
            "print('ha_sqlite3_vendor provides SQLite', _sqlite3.sqlite_version)",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
