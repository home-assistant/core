"""Tests for the flux_led integration."""

from unittest.mock import patch

import pytest

from tests.common import mock_device_registry


@pytest.fixture(name="device_reg")
def device_reg_fixture(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def mock_single_broadcast_address():
    """Mock network's async_async_get_ipv4_broadcast_addresses."""
    with patch(
        "homeassistant.components.network.async_get_ipv4_broadcast_addresses",
        return_value={"10.255.255.255"},
    ):
        yield


@pytest.fixture
def mock_multiple_broadcast_addresses():
    """Mock network's async_async_get_ipv4_broadcast_addresses to return multiple addresses."""
    with patch(
        "homeassistant.components.network.async_get_ipv4_broadcast_addresses",
        return_value={"10.255.255.255", "192.168.0.255"},
    ):
        yield
