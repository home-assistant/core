"""Tests for the Zeroconf component."""

import pytest


@pytest.fixture(autouse=True)
def zc_mock_get_source_ip(mock_get_source_ip):
    """Enable the mock_get_source_ip fixture for all zeroconf tests."""
    return mock_get_source_ip
