"""Tests for the Network Configuration integration."""

import pytest


@pytest.fixture(autouse=True)
def mock_network():
    """Override mock of network util's async_get_adapters."""


@pytest.fixture(autouse=True)
def override_mock_get_source_ip(mock_get_source_ip):
    """Override mock of network util's async_get_source_ip."""
    mock_get_source_ip.stop()
    yield
    mock_get_source_ip.start()
