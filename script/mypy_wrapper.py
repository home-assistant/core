#!/usr/bin/env python3

"""
Wrapper script for mypy to exit without error when it's not available.

For use in pre-commit.
"""

import sys

if __name__ == "__main__":
    try:
        from mypy.__main__ import console_entry
    except ImportError:
        print("mypy is not available, skipping it")
        sys.exit(0)
    sys.exit(console_entry())
