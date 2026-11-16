"""Tests for the Miele coordinator."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.parametrize("load_device_file", ["4_devices.json"])
async def test_update_cancels_outstanding_action_requests(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed action request cancels the requests of the other devices."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
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

    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.last_update_success is False
    assert cancelled.is_set()
