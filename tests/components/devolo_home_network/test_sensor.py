"""Tests for the devolo Home Network sensors."""
from datetime import timedelta
from unittest.mock import AsyncMock

from devolo_plc_api.exceptions.device import DeviceUnavailable
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.devolo_home_network.const import (
    LONG_UPDATE_INTERVAL,
    SHORT_UPDATE_INTERVAL,
)
from homeassistant.components.sensor import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import configure_integration
from .const import PLCNET
from .mock import MockDevice

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("mock_device")
async def test_sensor_setup(hass: HomeAssistant) -> None:
    """Test default setup of the sensor component."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.{device_name}_connected_wifi_clients") is not None
    assert hass.states.get(f"{DOMAIN}.{device_name}_connected_plc_devices") is None
    assert hass.states.get(f"{DOMAIN}.{device_name}_neighboring_wifi_networks") is None
    assert (
        hass.states.get(
            f"{DOMAIN}.{device_name}_plc_downlink_phy_rate_{PLCNET.devices[1].user_device_name}"
        )
        is not None
    )
    assert (
        hass.states.get(
            f"{DOMAIN}.{device_name}_plc_uplink_phy_rate_{PLCNET.devices[1].user_device_name}"
        )
        is not None
    )
    assert (
        hass.states.get(
            f"{DOMAIN}.{device_name}_plc_downlink_phyrate_{PLCNET.devices[2].user_device_name}"
        )
        is None
    )
    assert (
        hass.states.get(
            f"{DOMAIN}.{device_name}_plc_uplink_phyrate_{PLCNET.devices[2].user_device_name}"
        )
        is None
    )

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("name", "get_method", "interval"),
    [
        [
            "connected_wifi_clients",
            "async_get_wifi_connected_station",
            SHORT_UPDATE_INTERVAL,
        ],
        [
            "neighboring_wifi_networks",
            "async_get_wifi_neighbor_access_points",
            LONG_UPDATE_INTERVAL,
        ],
        [
            "connected_plc_devices",
            "async_get_network_overview",
            LONG_UPDATE_INTERVAL,
        ],
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    name: str,
    get_method: str,
    interval: timedelta,
) -> None:
    """Test state change of a sensor device."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{DOMAIN}.{device_name}_{name}"
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(state_key) == snapshot
    assert entity_registry.async_get(state_key) == snapshot

    # Emulate device failure
    setattr(mock_device.device, get_method, AsyncMock(side_effect=DeviceUnavailable))
    setattr(mock_device.plcnet, get_method, AsyncMock(side_effect=DeviceUnavailable))
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Emulate state change
    mock_device.reset()
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == "1"

    await hass.config_entries.async_unload(entry.entry_id)


async def test_update_plc_phyrates(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test state change of plc_downlink_phyrate and plc_uplink_phyrate sensor devices."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key_downlink = f"{DOMAIN}.{device_name}_plc_downlink_phy_rate_{PLCNET.devices[1].user_device_name}"
    state_key_uplink = f"{DOMAIN}.{device_name}_plc_uplink_phy_rate_{PLCNET.devices[1].user_device_name}"
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(state_key_downlink) == snapshot
    assert entity_registry.async_get(state_key_downlink) == snapshot
    assert hass.states.get(state_key_downlink) == snapshot
    assert entity_registry.async_get(state_key_downlink) == snapshot

    # Emulate device failure
    mock_device.plcnet.async_get_network_overview = AsyncMock(
        side_effect=DeviceUnavailable
    )
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key_downlink)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get(state_key_uplink)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Emulate state change
    mock_device.reset()
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key_downlink)
    assert state is not None
    assert state.state == str(PLCNET.data_rates[0].rx_rate)

    state = hass.states.get(state_key_uplink)
    assert state is not None
    assert state.state == str(PLCNET.data_rates[0].tx_rate)

    await hass.config_entries.async_unload(entry.entry_id)
