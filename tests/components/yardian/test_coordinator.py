"""Tests for Yardian coordinator error handling."""

from unittest.mock import AsyncMock

import pytest
from pyyardian import NetworkException

from homeassistant.components.yardian.coordinator import YardianUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_update_handles_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Raise UpdateFailed on timeout."""
    client = AsyncMock()
    client.fetch_device_state.side_effect = TimeoutError
    coordinator = YardianUpdateCoordinator(hass, mock_config_entry, client)

    with pytest.raises(UpdateFailed, match="Timeout communicating with device"):
        await coordinator._async_update_data()


async def test_update_handles_network_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Raise UpdateFailed on network errors."""
    client = AsyncMock()
    client.fetch_device_state.side_effect = NetworkException
    coordinator = YardianUpdateCoordinator(hass, mock_config_entry, client)

    with pytest.raises(UpdateFailed, match="Failed to communicate with device"):
        await coordinator._async_update_data()


async def test_update_handles_unexpected_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Raise UpdateFailed with details on unexpected errors."""
    client = AsyncMock()
    client.fetch_device_state.side_effect = RuntimeError("boom")
    coordinator = YardianUpdateCoordinator(hass, mock_config_entry, client)

    with pytest.raises(UpdateFailed, match=r"Unexpected error: RuntimeError: boom"):
        await coordinator._async_update_data()
