"""Tests for the devolo Home Network sensors."""
from unittest.mock import patch

from devolo_plc_api.exceptions.device import DeviceUnavailable
import pytest

from homeassistant.components.devolo_home_network.const import (
    LONG_UPDATE_INTERVAL,
    SHORT_UPDATE_INTERVAL,
)
from homeassistant.components.sensor import DOMAIN, SensorStateClass
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt

from . import configure_integration

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("mock_device")
async def test_sensor_setup(hass: HomeAssistant):
    """Test default setup of the sensor component."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.{device_name}_connected_wifi_clients") is not None
    assert hass.states.get(f"{DOMAIN}.{device_name}_connected_plc_devices") is None
    assert hass.states.get(f"{DOMAIN}.{device_name}_neighboring_wifi_networks") is None

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_device")
async def test_update_connected_wifi_clients(hass: HomeAssistant):
    """Test state change of a connected_wifi_clients sensor device."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{DOMAIN}.{device_name}_connected_wifi_clients"
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == "1"
    assert (
        state.attributes[ATTR_FRIENDLY_NAME] == f"{entry.title} Connected Wifi clients"
    )
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT

    # Emulate device failure
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_connected_station",
        side_effect=DeviceUnavailable,
    ):
        async_fire_time_changed(hass, dt.utcnow() + SHORT_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE

    # Emulate state change
    async_fire_time_changed(hass, dt.utcnow() + SHORT_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == "1"

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_device")
async def test_update_neighboring_wifi_networks(hass: HomeAssistant):
    """Test state change of a neighboring_wifi_networks sensor device."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{DOMAIN}.{device_name}_neighboring_wifi_networks"
    er = entity_registry.async_get(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == "1"
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == f"{entry.title} Neighboring Wifi networks"
    )
    assert er.async_get(state_key).entity_category is EntityCategory.DIAGNOSTIC

    # Emulate device failure
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_neighbor_access_points",
        side_effect=DeviceUnavailable,
    ):
        async_fire_time_changed(hass, dt.utcnow() + LONG_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE

    # Emulate state change
    async_fire_time_changed(hass, dt.utcnow() + LONG_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == "1"

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_device")
async def test_update_connected_plc_devices(hass: HomeAssistant):
    """Test state change of a connected_plc_devices sensor device."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{DOMAIN}.{device_name}_connected_plc_devices"
    er = entity_registry.async_get(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == "1"
    assert (
        state.attributes[ATTR_FRIENDLY_NAME] == f"{entry.title} Connected PLC devices"
    )
    assert er.async_get(state_key).entity_category is EntityCategory.DIAGNOSTIC

    # Emulate device failure
    with patch(
        "devolo_plc_api.plcnet_api.plcnetapi.PlcNetApi.async_get_network_overview",
        side_effect=DeviceUnavailable,
    ):
        async_fire_time_changed(hass, dt.utcnow() + LONG_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE

    # Emulate state change
    async_fire_time_changed(hass, dt.utcnow() + LONG_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == "1"

    await hass.config_entries.async_unload(entry.entry_id)
