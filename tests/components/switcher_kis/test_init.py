"""Test cases for the switcher_kis component."""

from datetime import timedelta

import pytest

from homeassistant.components.switcher_kis.const import MAX_UPDATE_INTERVAL_SEC
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util, slugify

from . import init_integration
from .consts import DUMMY_SWITCHER_DEVICES

from tests.common import async_fire_time_changed


async def test_update_fail(
    hass: HomeAssistant, mock_bridge, caplog: pytest.LogCaptureFixture
) -> None:
    """Test entities state unavailable when updates fail.."""
    entry = await init_integration(hass)
    assert mock_bridge

    mock_bridge.mock_callbacks(DUMMY_SWITCHER_DEVICES)
    await hass.async_block_till_done()

    assert mock_bridge.is_running is True
    assert len(entry.runtime_data) == 2

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=MAX_UPDATE_INTERVAL_SEC + 1)
    )
    await hass.async_block_till_done()

    for device in DUMMY_SWITCHER_DEVICES:
        assert (
            f"Device {device.name} did not send update for {MAX_UPDATE_INTERVAL_SEC} seconds"
            in caplog.text
        )

        entity_id = f"switch.{slugify(device.name)}"
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE

        entity_id = f"sensor.{slugify(device.name)}_power"
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE

    mock_bridge.mock_callbacks(DUMMY_SWITCHER_DEVICES)
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=MAX_UPDATE_INTERVAL_SEC - 2)
    )
    await hass.async_block_till_done()

    for device in DUMMY_SWITCHER_DEVICES:
        entity_id = f"switch.{slugify(device.name)}"
        state = hass.states.get(entity_id)
        assert state.state != STATE_UNAVAILABLE

        entity_id = f"sensor.{slugify(device.name)}_power"
        state = hass.states.get(entity_id)
        assert state.state != STATE_UNAVAILABLE


async def test_entry_unload(hass: HomeAssistant, mock_bridge) -> None:
    """Test entry unload."""
    entry = await init_integration(hass)
    assert mock_bridge

    assert entry.state is ConfigEntryState.LOADED
    assert mock_bridge.is_running is True

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert mock_bridge.is_running is False
