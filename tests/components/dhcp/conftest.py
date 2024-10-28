"""Tests for the dhcp integration."""

import os
import pathlib

import pytest


@pytest.fixture(autouse=True)
def _ensure_path_exists():
    """Fixture to avoid CI flaky race condition in scapy v2.6.0.

    See https://github.com/secdev/scapy/pull/4558
    """
    for file in (".cache", ".config"):
        path = pathlib.Path(os.path.join(os.path.expanduser("~"), file))
        if not path.exists():
            path.mkdir(mode=0o700, exist_ok=True)
