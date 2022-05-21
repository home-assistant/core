"""Tests for the Network Configuration integration."""

import pytest


@pytest.fixture(autouse=True)
def mock_get_source_ip():
    """Override mock of network util's async_get_source_ip."""
    return
