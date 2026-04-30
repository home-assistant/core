"""Tests for the devolo Home Network device tracker."""

from itertools import cycle
from unittest.mock import AsyncMock, patch

from devolo_plc_api.exceptions.device import DeviceUnavailable
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.devolo_home_network.const import (
    DOMAIN,
    LONG_UPDATE_INTERVAL,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import configure_integration
from .const import CONNECTED_STATIONS, DISCOVERY_INFO, IP, IP_ALT, NO_CONNECTED_STATIONS
from .mock import MockAltDevice, MockDevice

from tests.common import MockConfigEntry, async_fire_time_changed

STATION = CONNECTED_STATIONS[0]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device tracker states."""
    entity_id = (
        f"{DEVICE_TRACKER_DOMAIN}.{STATION.mac_address.lower().replace(':', '_')}"
    )
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) == snapshot

    # Emulate state change
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME

    # Emulate device failure
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        side_effect=DeviceUnavailable
    )
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_restoring_clients(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test restoring existing device_tracker entities."""
    entity_id = (
        f"{DEVICE_TRACKER_DOMAIN}.{STATION.mac_address.lower().replace(':', '_')}"
    )
    entry = configure_integration(hass)
    entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        f"{STATION.mac_address}",
        config_entry=entry,
    )

    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME


async def test_multi_ap_clients_merged(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Verify a client seen by multiple APs is merged into one device."""
    device_ap1 = MockDevice(ip=IP)
    device_ap2 = MockAltDevice(ip=IP_ALT)

    with patch(
        "homeassistant.components.devolo_home_network.Device",
        side_effect=cycle([device_ap1, device_ap2]),
    ):
        entry_ap1 = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_IP_ADDRESS: IP, CONF_PASSWORD: "test"},
            entry_id="ap1",
            unique_id=DISCOVERY_INFO.properties["SN"],
        )
        entry_ap1.add_to_hass(hass)
        await hass.config_entries.async_setup(entry_ap1.entry_id)
        await hass.async_block_till_done()

        entry_ap2 = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_IP_ADDRESS: IP_ALT, CONF_PASSWORD: "test"},
            entry_id="ap2",
            unique_id="0987654321",
        )
        entry_ap2.add_to_hass(hass)
        await hass.config_entries.async_setup(entry_ap2.entry_id)
        await hass.async_block_till_done()

    # Exactly one device for the client MAC
    client_device = device_registry.async_get_device(
        identifiers={(DOMAIN, STATION.mac_address)}
    )
    assert client_device is not None
    assert entry_ap1.entry_id in client_device.config_entries
    assert entry_ap2.entry_id in client_device.config_entries

    # Two scanner entities at this device, one per AP
    entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.device_id == client_device.id
        and entity.domain == DEVICE_TRACKER_DOMAIN
    ]
    assert len(entities) == 2
    assert {entity.config_entry_id for entity in entities} == {
        entry_ap1.entry_id,
        entry_ap2.entry_id,
    }
