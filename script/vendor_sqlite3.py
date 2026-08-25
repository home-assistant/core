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

Usage: python3 script/vendor_sqlite3.py --version 3.40.1 --year 2022

The year is part of the sqlite.org amalgamation download URL and can be found
at https://www.sqlite.org/chronology.html.
"""

import argparse
import io
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile

DOWNLOAD_ATTEMPTS = 3

SETUP_PY = '''\
"""Build CPython's own Modules/_sqlite against a bundled SQLite amalgamation."""

from pathlib import Path
import sysconfig

from setuptools import Extension, setup

setup(
    name="ha-sqlite3-vendor",
    version="0.1.0",
    packages=["ha_sqlite3_vendor"],
    ext_modules=[
        Extension(
            # The extension must be named _sqlite3 to match the sources'
            # PyInit__sqlite3, hence the wrapping package
            "ha_sqlite3_vendor._sqlite3",
            sources=sorted(str(p) for p in Path("src").glob("*.c"))
            + ["sqlite3.c"],
            include_dirs=[
                "src",
                ".",
                str(Path(sysconfig.get_paths()["include"]) / "internal"),
            ],
            define_macros=[
                ("Py_BUILD_CORE_MODULE", "1"),
                # Feature flags matching common distro builds
                ("SQLITE_ENABLE_FTS5", "1"),
                ("SQLITE_ENABLE_RTREE", "1"),
                ("SQLITE_ENABLE_MATH_FUNCTIONS", "1"),
            ],
        )
    ],
)
'''

PYPROJECT_TOML = """\
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"
"""


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
        for member in tar:
            if not member.isfile() or not member.name.startswith(prefix):
                continue
            target = src / member.name.removeprefix(prefix)
            target.parent.mkdir(parents=True, exist_ok=True)
            extracted = tar.extractfile(member)
            assert extracted is not None
            target.write_bytes(extracted.read())


def fetch_amalgamation(workdir: Path, version: str, year: str) -> None:
    """Extract the SQLite amalgamation for the given version into workdir."""
    major, minor, patch = (int(part) for part in version.split("."))
    release = f"{major}{minor:02d}{patch:02d}00"
    url = f"https://www.sqlite.org/{year}/sqlite-amalgamation-{release}.zip"
    with open_url(url) as response:
        archive_bytes = response.read()
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for filename in ("sqlite3.c", "sqlite3.h"):
            data = archive.read(f"sqlite-amalgamation-{release}/{filename}")
            (workdir / filename).write_bytes(data)


def main() -> None:
    """Build and install ha_sqlite3_vendor."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="SQLite version, e.g. 3.40.1")
    parser.add_argument(
        "--year", required=True, help="Release year in the sqlite.org download URL"
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        fetch_module_sources(workdir)
        fetch_amalgamation(workdir, args.version, args.year)
        (workdir / "setup.py").write_text(SETUP_PY)
        (workdir / "pyproject.toml").write_text(PYPROJECT_TOML)
        package = workdir / "ha_sqlite3_vendor"
        package.mkdir()
        (package / "__init__.py").write_text(
            '"""CPython sqlite3 C module built against a custom SQLite."""\n'
        )
        subprocess.run(
            ["uv", "pip", "install", "--python", sys.executable, "--reinstall", tmpdir],
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
