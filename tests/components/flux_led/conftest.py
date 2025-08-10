"""Tests for the flux_led integration."""

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_single_broadcast_address() -> Generator[None]:
    """Mock network's async_async_get_ipv4_broadcast_addresses."""
    with patch(
        "homeassistant.components.network.async_get_ipv4_broadcast_addresses",
        return_value={"10.255.255.255"},
    ):
        yield


@pytest.fixture
def mock_multiple_broadcast_addresses() -> Generator[None]:
    """Mock network's async_async_get_ipv4_broadcast_addresses to return multiple addresses."""
    with patch(
        "homeassistant.components.network.async_get_ipv4_broadcast_addresses",
        return_value={"10.255.255.255", "192.168.0.255"},
    ):
        yield
