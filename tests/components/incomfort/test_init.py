"""Tests for Intergas InComfort integration."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from aiohttp import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
from incomfortclient import IncomfortError
import pytest

from homeassistant.components.incomfort.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import async_fire_time_changed


async def test_setup_platforms(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test the incomfort integration is set up correctly."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_coordinator_updates(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test the incomfort coordinator is updating."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    state = hass.states.get("climate.thermostat_1")
    assert state is not None
    assert state.attributes["current_temperature"] == 21.4
    mock_incomfort().mock_room_status["room_temp"] = 20.91

    state = hass.states.get("sensor.boiler_pressure")
    assert state is not None
    assert state.state == "1.86"
    mock_incomfort().mock_heater_status["pressure"] = 1.84

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL + 5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("climate.thermostat_1")
    assert state is not None
    assert state.attributes["current_temperature"] == 20.9

    state = hass.states.get("sensor.boiler_pressure")
    assert state is not None
    assert state.state == "1.84"


@pytest.mark.parametrize(
    "exc",
    [
        IncomfortError(ClientResponseError(None, None, status=401)),
        IncomfortError(ClientResponseError(None, None, status=500)),
        IncomfortError(ValueError("some_error")),
        TimeoutError,
    ],
)
async def test_coordinator_update_fails(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    freezer: FrozenDateTimeFactory,
    exc: Exception,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test the incomfort coordinator update fails."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    state = hass.states.get("sensor.boiler_pressure")
    assert state is not None
    assert state.state == "1.86"

    with patch.object(
        mock_incomfort().heaters.return_value[0], "update", side_effect=exc
    ):
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL + 5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.boiler_pressure")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
