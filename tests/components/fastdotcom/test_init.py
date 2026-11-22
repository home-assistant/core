"""Test for Fast.com component Init."""

from unittest.mock import AsyncMock

from fastdotcom import FastDotComConnectionError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_async_fast_com: AsyncMock,
) -> None:
    """Test unload an entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_async_fast_com.assert_awaited_once_with(session=async_get_clientsession(hass))
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_delayed_speedtest_during_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_async_fast_com: AsyncMock,
) -> None:
    """Test delayed speedtest during startup."""
    mock_config_entry.add_to_hass(hass)

    original_state = hass.state
    hass.set_state(CoreState.starting)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    hass.set_state(original_state)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_async_fast_com.assert_not_awaited()
    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    # Assert state is Unknown as fast.com isn't starting until HA has started
    assert state.state == STATE_UNKNOWN

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    mock_async_fast_com.assert_awaited_once_with(session=async_get_clientsession(hass))
    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == "100.0"
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_startup_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_async_fast_com: AsyncMock,
) -> None:
    """Test startup speedtest handles FastDotComError gracefully."""
    mock_config_entry.add_to_hass(hass)
    mock_async_fast_com.side_effect = FastDotComConnectionError("network unreachable")

    original_state = hass.state
    hass.set_state(CoreState.starting)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    hass.set_state(original_state)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_async_fast_com.assert_not_awaited()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    mock_async_fast_com.assert_awaited_once_with(session=async_get_clientsession(hass))
    assert mock_config_entry.runtime_data.last_update_success is False
    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
