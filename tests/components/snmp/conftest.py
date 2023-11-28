"""Skip test collection for Python 3.12."""
import sys

if sys.version_info >= (3, 12):
    collect_ignore_glob = ["test_*.py"]
