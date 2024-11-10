"""Skip test collection for Python 3.13."""

import sys

if sys.version_info >= (3, 13):
    collect_ignore_glob = ["test_*.py"]
