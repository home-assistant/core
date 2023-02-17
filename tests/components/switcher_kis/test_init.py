"""Test cases for the switcher_kis component."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.switcher_kis.const import (
    DATA_DEVICE,
    DOMAIN,
    MAX_UPDATE_INTERVAL_SEC,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt, slugify

from . import init_integration
from .consts import DUMMY_SWITCHER_DEVICES, YAML_CONFIG

from tests.common import async_fire_time_changed


@pytest.mark.parametrize("mock_bridge", [DUMMY_SWITCHER_DEVICES], indirect=True)
async def test_async_setup_yaml_config(hass: HomeAssistant, mock_bridge) -> None:
    """Test setup started by configuration from YAML."""
    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert mock_bridge.is_running is True
    assert len(hass.data[DOMAIN]) == 2
    assert len(hass.data[DOMAIN][DATA_DEVICE]) == 2


@pytest.mark.parametrize("mock_bridge", [DUMMY_SWITCHER_DEVICES], indirect=True)
async def test_async_setup_user_config_flow(hass: HomeAssistant, mock_bridge) -> None:
    """Test setup started by user config flow."""
    with patch("homeassistant.components.switcher_kis.utils.DISCOVERY_TIME_SEC", 0):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert mock_bridge.is_running is True
    assert len(hass.data[DOMAIN]) == 2
    assert len(hass.data[DOMAIN][DATA_DEVICE]) == 2


async def test_update_fail(
    hass: HomeAssistant, mock_bridge, caplog: pytest.LogCaptureFixture
) -> None:
    """Test entities state unavailable when updates fail.."""
    await init_integration(hass)
    assert mock_bridge

    mock_bridge.mock_callbacks(DUMMY_SWITCHER_DEVICES)
    await hass.async_block_till_done()

    assert mock_bridge.is_running is True
    assert len(hass.data[DOMAIN]) == 2
    assert len(hass.data[DOMAIN][DATA_DEVICE]) == 2

    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=MAX_UPDATE_INTERVAL_SEC + 1)
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

        entity_id = f"sensor.{slugify(device.name)}_power_consumption"
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE

    mock_bridge.mock_callbacks(DUMMY_SWITCHER_DEVICES)
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=MAX_UPDATE_INTERVAL_SEC - 1)
    )

    for device in DUMMY_SWITCHER_DEVICES:
        entity_id = f"switch.{slugify(device.name)}"
        state = hass.states.get(entity_id)
        assert state.state != STATE_UNAVAILABLE

        entity_id = f"sensor.{slugify(device.name)}_power_consumption"
        state = hass.states.get(entity_id)
        assert state.state != STATE_UNAVAILABLE


async def test_entry_unload(hass: HomeAssistant, mock_bridge) -> None:
    """Test entry unload."""
    entry = await init_integration(hass)
    assert mock_bridge

    assert entry.state is ConfigEntryState.LOADED
    assert mock_bridge.is_running is True
    assert len(hass.data[DOMAIN]) == 2

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert mock_bridge.is_running is False
    assert len(hass.data[DOMAIN]) == 0
