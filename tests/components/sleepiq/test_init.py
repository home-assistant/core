"""Tests for the SleepIQ integration."""
from asyncsleepiq import (
    SleepIQAPIException,
    SleepIQLoginException,
    SleepIQTimeoutException,
)

from homeassistant.components.sleepiq.const import DOMAIN
from homeassistant.components.sleepiq.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed
from tests.components.sleepiq.conftest import setup_platform


async def test_unload_entry(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test unloading the SleepIQ entry."""
    entry = await setup_platform(hass, "sensor")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_entry_setup_login_error(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test when sleepiq client is unable to login."""
    mock_asyncsleepiq.login.side_effect = SleepIQLoginException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_entry_setup_timeout_error(
    hass: HomeAssistant, mock_asyncsleepiq
) -> None:
    """Test when sleepiq client timeout."""
    mock_asyncsleepiq.login.side_effect = SleepIQTimeoutException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_update_interval(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test update interval."""
    await setup_platform(hass, "sensor")
    assert mock_asyncsleepiq.fetch_bed_statuses.call_count == 1

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert mock_asyncsleepiq.fetch_bed_statuses.call_count == 2


async def test_api_error(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test when sleepiq client is unable to login."""
    mock_asyncsleepiq.init_beds.side_effect = SleepIQAPIException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_api_timeout(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test when sleepiq client timeout."""
    mock_asyncsleepiq.init_beds.side_effect = SleepIQTimeoutException
    entry = await setup_platform(hass, None)
    assert not await hass.config_entries.async_setup(entry.entry_id)
