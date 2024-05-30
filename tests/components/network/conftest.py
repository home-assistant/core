"""Tests for the Network Configuration integration."""

from collections.abc import Generator

import pytest

from tests.typing import Patcher


@pytest.fixture(autouse=True)
def mock_network():
    """Override mock of network util's async_get_adapters."""


@pytest.fixture(autouse=True)
def override_mock_get_source_ip(
    mock_get_source_ip: Patcher,
) -> Generator[None, None, None]:
    """Override mock of network util's async_get_source_ip."""
    mock_get_source_ip.stop()
    yield
    mock_get_source_ip.start()
