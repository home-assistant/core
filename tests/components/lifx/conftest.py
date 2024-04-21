"""Tests for the lifx integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.lifx import config_flow, coordinator, util

from . import _patch_discovery

from tests.common import mock_device_registry, mock_registry


@pytest.fixture
def mock_discovery():
    """Mock discovery."""
    with _patch_discovery():
        yield


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
def lifx_no_wait_for_timeouts():
    """Avoid waiting for timeouts in tests."""
    with (
        patch.object(util, "OVERALL_TIMEOUT", 0),
        patch.object(config_flow, "OVERALL_TIMEOUT", 0),
        patch.object(coordinator, "OVERALL_TIMEOUT", 0),
        patch.object(coordinator, "MAX_UPDATE_TIME", 0),
    ):
        yield


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
