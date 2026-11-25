"""Tests Starlink integration init/unload."""

from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonArrayType

from . import setup_integration


def _status_with_uptime(status_data: JsonArrayType, uptime: int) -> JsonArrayType:
    """Return status data with the given uptime."""
    status = deepcopy(status_data)
    status[0]["uptime"] = uptime
    return status


async def test_successful_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test configuring Starlink."""
    assert init_integration.runtime_data
    assert init_integration.runtime_data.data
    assert init_integration.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test removing Starlink."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_restore_cache_with_accumulation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Starlink accumulation."""
    entity_id = "sensor.starlink_energy"

    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    entity_id,
                    "",
                ),
                {
                    "native_value": 1,
                    "native_unit_of_measurement": None,
                },
            ),
        ),
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.runtime_data
    assert mock_config_entry.runtime_data.data

    assert hass.states.get(entity_id).state == str(1 + 0.00786231368489)

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == str(1 + 0.00786231368489)

    with patch.object(
        mock_config_entry.runtime_data, "always_update", return_value=True
    ):
        freezer.tick(timedelta(seconds=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == str(1 + 0.01572462736977)


async def test_last_restart_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_status_data: MagicMock,
    status_data: JsonArrayType,
) -> None:
    """Test Starlink last restart state."""
    entity_id = "sensor.starlink_last_restart"
    utc_now = datetime.fromisoformat("2025-10-22T13:31:29+00:00")

    with freeze_time(utc_now):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

    with patch.object(
        mock_config_entry.runtime_data, "always_update", return_value=True
    ):
        mock_status_data.return_value = _status_with_uptime(status_data, 804144)

        with freeze_time(utc_now + timedelta(seconds=5)):
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
            await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

        mock_status_data.return_value = _status_with_uptime(status_data, 804134)

        with freeze_time(utc_now + timedelta(seconds=10)):
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
            await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

        mock_status_data.return_value = _status_with_uptime(status_data, 100)

        with freeze_time(utc_now + timedelta(seconds=15)):
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15))
            await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get(entity_id).state == "2025-10-22T13:30:04+00:00"
