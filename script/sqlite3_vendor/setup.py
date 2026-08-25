"""Build CPython's own Modules/_sqlite against a bundled SQLite amalgamation."""

# ruff: noqa: INP001

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
            sources=[*sorted(str(p) for p in Path("src").glob("*.c")), "sqlite3.c"],
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
