"""Conftest for SNMP tests."""

import socket
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def patch_getaddrinfo():
    """Patch getaddrinfo to avoid DNS lookups in SNMP tests."""
    with patch.object(socket, "getaddrinfo"):
        yield
