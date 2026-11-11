"""Tests for the AsusWrt integration."""

from datetime import timedelta

from aioasuswrt.asuswrt import Device as LegacyDevice
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import device_tracker, sensor
from homeassistant.components.asuswrt.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PROTOCOL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from .common import (
    CONFIG_DATA_HTTP,
    CONFIG_DATA_TELNET,
    HOST,
    MOCK_MACS,
    ROUTER_MAC_ADDR,
    new_device,
)


async def test_disconnect_on_stop(hass: HomeAssistant, connect_legacy) -> None:
    """Test we close the connection with the router when Home Assistants stops."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_TELNET,
        unique_id=ROUTER_MAC_ADDR,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert connect_legacy.return_value.async_disconnect.await_count == 1
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("connect_http", "connect_http_sens_detect")
async def test_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the router device registry entry, including the network MAC connection."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_HTTP,
        unique_id=ROUTER_MAC_ADDR,
    )
    config_entry.add_to_hass(hass)

    # Router sensors are disabled by default; pre-enable one so the router
    # device is registered in the device registry.
    unique_id_prefix = slugify(ROUTER_MAC_ADDR)
    sensor_id = slugify("sensor_rx_bytes")
    entity_registry.async_get_or_create(
        sensor.DOMAIN,
        DOMAIN,
        f"{unique_id_prefix}_{sensor_id}",
        suggested_object_id=f"{slugify(HOST)}_{sensor_id}",
        config_entry=config_entry,
        disabled_by=None,
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, ROUTER_MAC_ADDR), config_entry.entry_id
    )
    assert device_entry == snapshot


@pytest.mark.usefixtures("connect_legacy")
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mock_devices_legacy: dict[str, LegacyDevice],
) -> None:
    """Test only the devices of disconnected clients can be removed."""
    assert await async_setup_component(hass, "config", {})
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_TELNET, unique_id=ROUTER_MAC_ADDR
    )
    config_entry.add_to_hass(hass)
    router_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, ROUTER_MAC_ADDR)},
    )
    connected_mac = dr.format_mac(MOCK_MACS[0])
    offline_mac = dr.format_mac(MOCK_MACS[2])
    # A client tracked before, which is restored from the registry
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        DOMAIN,
        offline_mac,
        config_entry=config_entry,
        original_name="Offline",
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    ws_client = await hass_ws_client(hass)

    response = await ws_client.remove_device(router_device.id)
    assert not response["success"]

    connected_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, connected_mac), config_entry.entry_id
    )
    assert connected_device is not None
    response = await ws_client.remove_device(connected_device.id)
    assert not response["success"]

    offline_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, offline_mac), config_entry.entry_id
    )
    assert offline_device is not None
    response = await ws_client.remove_device(offline_device.id)
    assert response["success"]
    # Clients are restored from tracker registry entries on the next start
    assert not entity_registry.async_get_entity_id(
        device_tracker.DOMAIN, DOMAIN, offline_mac
    )

    # The removed client is tracked again when it reconnects
    mock_devices_legacy[MOCK_MACS[2]] = new_device(
        CONFIG_DATA_TELNET[CONF_PROTOCOL], MOCK_MACS[2], "192.168.1.4", "Back"
    )
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(
        device_tracker.DOMAIN, DOMAIN, offline_mac
    )
    readded_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, offline_mac), config_entry.entry_id
    )
    assert readded_device is not None
    assert readded_device.name == "Back"


@pytest.mark.usefixtures("connect_legacy")
async def test_remove_config_entry_device_not_loaded(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test removing devices of an unloaded config entry."""
    assert await async_setup_component(hass, "config", {})
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_TELNET, unique_id=ROUTER_MAC_ADDR
    )
    config_entry.add_to_hass(hass)
    router_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, ROUTER_MAC_ADDR)},
    )
    offline_mac = dr.format_mac(MOCK_MACS[2])
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        DOMAIN,
        offline_mac,
        config_entry=config_entry,
        original_name="Offline",
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    ws_client = await hass_ws_client(hass)

    response = await ws_client.remove_device(router_device.id)
    assert not response["success"]

    offline_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, offline_mac), config_entry.entry_id
    )
    assert offline_device is not None
    response = await ws_client.remove_device(offline_device.id)
    assert response["success"]

    # The client is not restored, its tracker was removed with the device
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert not entity_registry.async_get_entity_id(
        device_tracker.DOMAIN, DOMAIN, offline_mac
    )
    assert not device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, offline_mac), config_entry.entry_id
    )
