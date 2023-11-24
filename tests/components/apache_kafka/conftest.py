"""Skip test collection."""
import sys

if sys.version_info >= (3, 12):
    collect_ignore_glob = ["test_*.py"]
