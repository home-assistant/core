"""Tests for the lifx integration."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.common import mock_device_registry, mock_registry


@pytest.fixture
def mock_effect_conductor():
    """Mock the effect conductor."""

    class MockConductor:
        def __init__(self, *args, **kwargs) -> None:
            """Mock the conductor."""
            self.start = AsyncMock()
            self.stop = AsyncMock()

        def effect(self, bulb):
            """Mock effect."""
            return MagicMock()

    mock_conductor = MockConductor()

    with patch(
        "homeassistant.components.lifx.manager.aiolifx_effects.Conductor",
        return_value=mock_conductor,
    ):
        yield mock_conductor


@pytest.fixture(autouse=True)
def lifx_mock_get_source_ip(mock_get_source_ip):
    """Mock network util's async_get_source_ip."""


@pytest.fixture(autouse=True)
def lifx_mock_async_get_ipv4_broadcast_addresses():
    """Mock network util's async_get_ipv4_broadcast_addresses."""
    with patch(
        "homeassistant.components.network.async_get_ipv4_broadcast_addresses",
        return_value=["255.255.255.255"],
    ):
        yield


@pytest.fixture(name="device_reg")
def device_reg_fixture(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture(name="entity_reg")
def entity_reg_fixture(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)
