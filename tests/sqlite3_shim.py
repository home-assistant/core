"""Run tests against a custom-built SQLite instead of the interpreter's own.

script/vendor_sqlite3.py builds CPython's own Modules/_sqlite sources against
a chosen SQLite amalgamation as the ha_sqlite3_vendor package. Loading this
module with `pytest -p tests.sqlite3_shim` rebinds the stdlib sqlite3 package
to that build. It must be loaded with `-p` instead of being imported from
conftest.py because plugins load before conftest.py, which already imports
sqlite3 at the top of the file.
"""

import sys

from ha_sqlite3_vendor import _sqlite3

if "sqlite3" in sys.modules:
    raise RuntimeError(
        "sqlite3 was already imported, load this module earlier with "
        "pytest -p tests.sqlite3_shim"
    )
sys.modules["_sqlite3"] = _sqlite3
