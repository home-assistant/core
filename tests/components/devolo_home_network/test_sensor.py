"""Tests for the devolo Home Network sensors."""
from unittest.mock import AsyncMock, patch

from devolo_plc_api.exceptions.device import DeviceUnavailable
import pytest

from homeassistant.components.devolo_home_network.sensor import MIN_TIME_BETWEEN_UPDATES
from homeassistant.components.sensor import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from . import configure_integration
from .const import CONNECTED_STATIONS, NEIGHBOR_ACCESS_POINTS, PLCNET


@pytest.mark.usefixtures("mock_device")
@pytest.mark.usefixtures("mock_zeroconf")
async def test_sensor_setup(hass: HomeAssistant):
    """Test default setup of the sensor component."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.connected_wifi_clients") is not None
    assert hass.states.get(f"{DOMAIN}.connected_plc_devices") is None
    assert hass.states.get(f"{DOMAIN}.neighboring_wifi_networks") is None

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_device")
@pytest.mark.usefixtures("mock_zeroconf")
async def test_update_connected_wifi_clients(hass: HomeAssistant):
    """Test state change of a connected_wifi_clients sensor device."""
    state_key = f"{DOMAIN}.connected_wifi_clients"
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == "0"

    # Emulate device failure
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_connected_station",
        side_effect=DeviceUnavailable,
    ):
        await hass.helpers.entity_component.async_update_entity(state_key)
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE

    # Emulate state change
    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_connected_station",
        new=AsyncMock(return_value=CONNECTED_STATIONS),
    ):
        await hass.helpers.entity_component.async_update_entity(state_key)
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == "1"

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_device")
@pytest.mark.usefixtures("mock_zeroconf")
async def test_update_neighboring_wifi_networks(hass: HomeAssistant):
    """Test state change of a neighboring_wifi_networks sensor device."""
    state_key = f"{DOMAIN}.neighboring_wifi_networks"
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_network.device.DevoloDevice.entity_registry_enabled_default",
        return_value=True,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == "0"

        # Emulate device failure
        with patch(
            "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_neighbor_access_points",
            side_effect=DeviceUnavailable,
        ):
            await hass.helpers.entity_component.async_update_entity(state_key)
            await hass.async_block_till_done()

            state = hass.states.get(state_key)
            assert state is not None
            assert state.state == STATE_UNAVAILABLE

        # Emulate state change
        with patch(
            "devolo_plc_api.device_api.deviceapi.DeviceApi.async_get_wifi_neighbor_access_points",
            new=AsyncMock(return_value=NEIGHBOR_ACCESS_POINTS),
        ), patch(
            "homeassistant.util.utcnow",
            return_value=dt.utcnow() + MIN_TIME_BETWEEN_UPDATES,
        ):
            await hass.helpers.entity_component.async_update_entity(state_key)
            await hass.async_block_till_done()

            state = hass.states.get(state_key)
            assert state is not None
            assert state.state == "1"

        await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_device")
@pytest.mark.usefixtures("mock_zeroconf")
async def test_update_connected_plc_devices(hass: HomeAssistant):
    """Test state change of a connected_plc_devices sensor device."""
    state_key = f"{DOMAIN}.connected_plc_devices"
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_network.device.DevoloDevice.entity_registry_enabled_default",
        return_value=True,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == "0"

        # Emulate device failure
        with patch(
            "devolo_plc_api.plcnet_api.plcnetapi.PlcNetApi.async_get_network_overview",
            side_effect=DeviceUnavailable,
        ):
            await hass.helpers.entity_component.async_update_entity(state_key)
            await hass.async_block_till_done()

            state = hass.states.get(state_key)
            assert state is not None
            assert state.state == STATE_UNAVAILABLE

        # Emulate state change
        with patch(
            "devolo_plc_api.plcnet_api.plcnetapi.PlcNetApi.async_get_network_overview",
            new=AsyncMock(return_value=PLCNET),
        ), patch(
            "homeassistant.util.utcnow",
            return_value=dt.utcnow() + MIN_TIME_BETWEEN_UPDATES,
        ):
            await hass.helpers.entity_component.async_update_entity(state_key)
            await hass.async_block_till_done()

            state = hass.states.get(state_key)
            assert state is not None
            assert state.state == "1"

        await hass.config_entries.async_unload(entry.entry_id)
