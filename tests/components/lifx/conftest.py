"""Tests for the lifx integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from lifx import Conductor, Light
import pytest

from homeassistant.components.lifx import manager as lifx_manager

from . import _patch_discovery
from .helpers import create_mock_light


@pytest.fixture
def mock_light() -> Light:
    """Return a deterministic lifx-async light."""
    return create_mock_light()


@pytest.fixture
def mock_discovery():
    """Mock discovery."""
    with _patch_discovery():
        yield


@pytest.fixture
def mock_effect_conductor() -> MagicMock:
    """Mock the effect conductor."""
    mock_conductor = MagicMock(spec=Conductor)
    mock_conductor.start = AsyncMock()
    mock_conductor.stop = AsyncMock()
    # No software effect is running unless a test says otherwise
    mock_conductor.effect = MagicMock(return_value=None)

    with patch.object(lifx_manager, "Conductor", return_value=mock_conductor):
        yield mock_conductor


@pytest.fixture(autouse=True)
def lifx_mock_async_get_ipv4_broadcast_addresses():
    """Mock network util's async_get_ipv4_broadcast_addresses."""
    with patch(
        "homeassistant.components.network.async_get_ipv4_broadcast_addresses",
        return_value=["255.255.255.255"],
    ):
        yield
