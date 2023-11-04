"""Tests for the devolo Home Network device tracker."""
from unittest.mock import AsyncMock

from devolo_plc_api.exceptions.device import DeviceUnavailable
from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import DOMAIN as PLATFORM
from homeassistant.components.devolo_home_network.const import (
    DOMAIN,
    LONG_UPDATE_INTERVAL,
)
from homeassistant.const import STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import configure_integration
from .const import CONNECTED_STATIONS, DISCOVERY_INFO, NO_CONNECTED_STATIONS
from .mock import MockDevice

from tests.common import async_fire_time_changed

STATION = CONNECTED_STATIONS[0]
SERIAL = DISCOVERY_INFO.properties["SN"]


async def test_device_tracker(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device tracker states."""
    state_key = (
        f"{PLATFORM}.{DOMAIN}_{SERIAL}_{STATION.mac_address.lower().replace(':', '_')}"
    )
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Enable entity
    entity_registry.async_update_entity(state_key, disabled_by=None)
    await hass.async_block_till_done()
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(state_key) == snapshot

    # Emulate state change
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_NOT_HOME

    # Emulate device failure
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        side_effect=DeviceUnavailable
    )
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_unload(entry.entry_id)


async def test_restoring_clients(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test restoring existing device_tracker entities."""
    state_key = (
        f"{PLATFORM}.{DOMAIN}_{SERIAL}_{STATION.mac_address.lower().replace(':', '_')}"
    )
    entry = configure_integration(hass)
    entity_registry.async_get_or_create(
        PLATFORM,
        DOMAIN,
        f"{SERIAL}_{STATION.mac_address}",
        config_entry=entry,
    )

    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_NOT_HOME
