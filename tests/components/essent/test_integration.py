"""Full integration tests for Essent."""

from __future__ import annotations

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

pytestmark = [
    pytest.mark.freeze_time("2025-11-16 10:30:00+01:00"),
    pytest.mark.usefixtures("disable_coordinator_schedules"),
]


async def test_full_integration_setup(
    hass: HomeAssistant, aioclient_mock, essent_api_response: dict
) -> None:
    """Test complete integration setup and unload."""
    entry = await setup_integration(hass, aioclient_mock, essent_api_response)

    assert entry.state == ConfigEntryState.LOADED

    assert hass.states.get("sensor.essent_electricity_current_price") is not None
    assert hass.states.get("sensor.essent_electricity_next_price") is not None
    assert hass.states.get("sensor.essent_gas_current_price") is not None
    assert hass.states.get("sensor.essent_gas_next_price") is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.NOT_LOADED
