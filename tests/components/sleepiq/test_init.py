"""Tests for the SleepIQ integration."""
from unittest.mock import patch

from homeassistant.components.sleepiq.const import DOMAIN
from homeassistant.components.sleepiq.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed
from tests.components.sleepiq.conftest import (
    mock_bed_family_status,
    mock_beds,
    mock_sleepers,
)


async def test_unload_entry(hass: HomeAssistant, setup_entry) -> None:
    """Test unloading the SleepIQ entry."""
    entry = setup_entry["mock_entry"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_entry_setup_login_error(hass: HomeAssistant, config_entry) -> None:
    """Test when sleepyq client is unable to login."""
    with patch("sleepyq.Sleepyq.login", side_effect=ValueError):
        config_entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(config_entry.entry_id)


async def test_update_interval(hass: HomeAssistant, setup_entry) -> None:
    """Test update interval."""
    with patch("sleepyq.Sleepyq.beds", return_value=mock_beds("")) as beds, patch(
        "sleepyq.Sleepyq.sleepers", return_value=mock_sleepers()
    ) as sleepers, patch(
        "sleepyq.Sleepyq.bed_family_status",
        return_value=mock_bed_family_status(""),
    ) as bed_family_status, patch(
        "sleepyq.Sleepyq.login", return_value=True
    ):
        assert beds.call_count == 0
        assert sleepers.call_count == 0
        assert bed_family_status.call_count == 0

        async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
        await hass.async_block_till_done()

        assert beds.call_count == 1
        assert sleepers.call_count == 1
        assert bed_family_status.call_count == 1
