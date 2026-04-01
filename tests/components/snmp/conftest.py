"""Conftest for SNMP tests."""

import socket
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def patch_gethostbyname():
    """Patch gethostbyname to avoid DNS lookups in SNMP tests."""
    with patch.object(socket, "gethostbyname"):
        yield
