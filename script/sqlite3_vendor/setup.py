"""Build CPython's own Modules/_sqlite against a bundled SQLite amalgamation."""

import os
from pathlib import Path
import sysconfig

from setuptools import Extension, setup

# Staged by script/vendor_sqlite3.py next to this file
sources = sorted(str(p) for p in Path("src").glob("*.c"))
if not sources or not Path("sqlite3.c").exists():
    raise FileNotFoundError("Build via script/vendor_sqlite3.py to stage the sources")

setup(
    name="ha-sqlite3-vendor",
    # Version the wheel by the SQLite it bundles
    version=os.environ["SQLITE_VERSION"],
    packages=["ha_sqlite3_vendor"],
    ext_modules=[
        Extension(
            # The extension must be named _sqlite3 to match the sources'
            # PyInit__sqlite3, hence the wrapping package
            "ha_sqlite3_vendor._sqlite3",
            sources=[*sources, "sqlite3.c"],
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
            # Override the interpreter's -O3 -g, which make compiling the
            # amalgamation much slower for no runtime gain
            extra_compile_args=["-O2", "-g0"],
        )
    ],
)
