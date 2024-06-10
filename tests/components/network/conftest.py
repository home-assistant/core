"""Tests for the Network Configuration integration."""

from unittest.mock import _patch

import pytest
from typing_extensions import Generator


@pytest.fixture(autouse=True)
def mock_network():
    """Override mock of network util's async_get_adapters."""


@pytest.fixture(autouse=True)
def override_mock_get_source_ip(
    mock_get_source_ip: _patch,
) -> Generator[None]:
    """Override mock of network util's async_get_source_ip."""
    mock_get_source_ip.stop()
    yield
    mock_get_source_ip.start()
