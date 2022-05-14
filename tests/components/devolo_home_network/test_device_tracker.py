"""Tests for the devolo Home Network device tracker."""
from unittest.mock import AsyncMock, patch

from devolo_plc_api.exceptions.device import DeviceUnavailable
import pytest

from homeassistant.components.device_tracker import DOMAIN as PLATFORM
from homeassistant.components.devolo_home_network.const import (
    DOMAIN,
    LONG_UPDATE_INTERVAL,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.util import dt

from . import configure_integration
from .const import CONNECTED_STATIONS, NO_CONNECTED_STATIONS

from tests.common import async_fire_time_changed

STATION = (
    CONNECTED_STATIONS["connected_stations"][0]["mac_address"].lower().replace(":", "_")
)


@pytest.mark.usefixtures("mock_device", "mock_zeroconf")
async def test_device_tracker_home(hass: HomeAssistant):
    """Test device being home."""
    state_key = f"{PLATFORM}.{DOMAIN}_{STATION}"
    entry = configure_integration(hass)

    er = entity_registry.async_get(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Enable entity
    er.async_update_entity(state_key, disabled_by=None)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt.utcnow() + LONG_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_HOME

    # Emulate state change
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_connected_station",
        new=AsyncMock(return_value=NO_CONNECTED_STATIONS),
    ):
        async_fire_time_changed(hass, dt.utcnow() + LONG_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_NOT_HOME

    # Emulate device failure
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_connected_station",
        side_effect=DeviceUnavailable,
    ):
        async_fire_time_changed(hass, dt.utcnow() + LONG_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_device", "mock_zeroconf")
async def test_restoring_clients(hass: HomeAssistant):
    """Test restoring existing device_tracker entities if not detected on startup."""
    state_key = f"{PLATFORM}.{DOMAIN}_{STATION}"
    entry = configure_integration(hass)

    er = entity_registry.async_get(hass)
    er.async_get_or_create(
        PLATFORM,
        DOMAIN,
        STATION,
        config_entry=entry,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_NOT_HOME
