"""Tests for the lifx integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.lifx import config_flow, coordinator, util

from . import _patch_discovery


@pytest.fixture
def mock_discovery():
    """Mock discovery."""
    with _patch_discovery():
        yield


@pytest.fixture
def mock_effect_conductor():
    """Mock the effect conductor."""

    class MockConductor:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
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
