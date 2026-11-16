"""Tests for the Miele coordinator."""

import asyncio
from unittest.mock import MagicMock

from aiohttp import ClientConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.miele.coordinator import MieleDataUpdateCoordinator
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize("load_device_file", ["4_devices.json"])
async def test_update_cancels_outstanding_action_requests(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failed action request cancels the requests of the other devices."""
    cancelled = asyncio.Event()

    async def _get_actions(device_id: str) -> dict:
        if device_id == "Dummy_Appliance_1":
            raise ClientConnectionError
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return {}

    mock_miele_client.get_actions.side_effect = _get_actions
    coordinator = MieleDataUpdateCoordinator(hass, mock_config_entry, mock_miele_client)

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert cancelled.is_set()
