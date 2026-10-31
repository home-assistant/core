"""Test SenseCAP integration setup."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from lorawan_connection import ConnectionUnavailable
from lorawan_connection.mock import MockConnection
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


async def test_setup_retries_after_connection_recovers(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Retry a failed subscription and create sensors once the backend recovers."""
    await hass.async_start()
    assert await hass.config_entries.async_setup(connection_entry.entry_id)

    with patch.object(
        mock_connection,
        "async_subscribe",
        side_effect=ConnectionUnavailable("Backend unavailable"),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.states.async_all("sensor")

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.greenhouse_temperature").state == "unknown"
    assert len(hass.states.async_all("sensor")) == 3
