"""Tests for the dhcp integration."""

import os
import pathlib


def pytest_sessionstart(session):
    """Try to avoid flaky FileExistsError in CI.

    Called after the Session object has been created and
    before performing collection and entering the run test loop.

    This is needed due to a race condition in scapy v2.6.0
    See https://github.com/secdev/scapy/pull/4558

    Can be removed when scapy 2.6.1 is released.
    """
    for sub_dir in (".cache", ".config"):
        path = pathlib.Path(os.path.join(os.path.expanduser("~"), sub_dir))
        if not path.exists():
            path.mkdir(mode=0o700, exist_ok=True)
