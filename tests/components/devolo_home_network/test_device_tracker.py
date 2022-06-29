"""Tests for the devolo Home Network device tracker."""
from unittest.mock import AsyncMock, patch

from devolo_plc_api.exceptions.device import DeviceUnavailable
import pytest

from homeassistant.components.device_tracker import DOMAIN as PLATFORM
from homeassistant.components.devolo_home_network.const import (
    DOMAIN,
    LONG_UPDATE_INTERVAL,
    WIFI_APTYPE,
    WIFI_BANDS,
)
from homeassistant.const import (
    FREQUENCY_GIGAHERTZ,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.util import dt

from . import configure_integration
from .const import CONNECTED_STATIONS, DISCOVERY_INFO, NO_CONNECTED_STATIONS

from tests.common import async_fire_time_changed

STATION = CONNECTED_STATIONS["connected_stations"][0]
SERIAL = DISCOVERY_INFO.properties["SN"]


@pytest.mark.usefixtures("mock_device")
async def test_device_tracker(hass: HomeAssistant):
    """Test device tracker states."""
    state_key = f"{PLATFORM}.{DOMAIN}_{SERIAL}_{STATION['mac_address'].lower().replace(':', '_')}"
    entry = configure_integration(hass)
    er = entity_registry.async_get(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt.utcnow() + LONG_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    # Enable entity
    er.async_update_entity(state_key, disabled_by=None)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt.utcnow() + LONG_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["wifi"] == WIFI_APTYPE[STATION["vap_type"]]
    assert (
        state.attributes["band"]
        == f"{WIFI_BANDS[STATION['band']]} {FREQUENCY_GIGAHERTZ}"
    )

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


@pytest.mark.usefixtures("mock_device")
async def test_restoring_clients(hass: HomeAssistant):
    """Test restoring existing device_tracker entities."""
    state_key = f"{PLATFORM}.{DOMAIN}_{SERIAL}_{STATION['mac_address'].lower().replace(':', '_')}"
    entry = configure_integration(hass)
    er = entity_registry.async_get(hass)
    er.async_get_or_create(
        PLATFORM,
        DOMAIN,
        f"{SERIAL}_{STATION['mac_address']}",
        config_entry=entry,
    )

    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_connected_station",
        new=AsyncMock(return_value=NO_CONNECTED_STATIONS),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_NOT_HOME
