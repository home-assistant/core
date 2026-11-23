"""Tests for the AsusWrt device tracker."""

from aioasuswrt.asuswrt import Device as LegacyDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import device_tracker
from homeassistant.components.asuswrt.const import CONF_TRACK_UNKNOWN, DOMAIN
from homeassistant.const import CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import CONFIG_DATA_TELNET, MOCK_MACS, ROUTER_MAC_ADDR, new_device


@pytest.mark.usefixtures("connect_legacy")
async def test_unnamed_client_device_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an unnamed client only names a new device by its MAC address."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_TELNET, unique_id=ROUTER_MAC_ADDR
    )
    config_entry.add_to_hass(hass)
    existing_mac = dr.format_mac(MOCK_MACS[2])
    new_mac = dr.format_mac(MOCK_MACS[3])
    # Offline clients restored from registry entries without a name
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        DOMAIN,
        existing_mac,
        config_entry=config_entry,
        original_name=existing_mac.replace(":", "_"),
    )
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN, DOMAIN, new_mac, config_entry=config_entry
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, existing_mac)},
        name="My phone",
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    existing_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, existing_mac), config_entry.entry_id
    )
    assert existing_device is not None
    assert existing_device.name == "My phone"
    new_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, new_mac), config_entry.entry_id
    )
    assert new_device is not None
    assert new_device.name == new_mac


@pytest.mark.usefixtures("connect_legacy")
async def test_connected_unnamed_client_device_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_devices_legacy: dict[str, LegacyDevice],
) -> None:
    """Test a connected unnamed client only names a new device by its MAC address."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_TELNET,
        options={CONF_TRACK_UNKNOWN: True},
        unique_id=ROUTER_MAC_ADDR,
    )
    config_entry.add_to_hass(hass)
    existing_mac = dr.format_mac(MOCK_MACS[2])
    new_mac = dr.format_mac(MOCK_MACS[3])
    for mac, ip in ((MOCK_MACS[2], "192.168.1.4"), (MOCK_MACS[3], "192.168.1.5")):
        mock_devices_legacy[mac] = new_device(
            CONFIG_DATA_TELNET[CONF_PROTOCOL], mac, ip, None
        )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, existing_mac)},
        name="My phone",
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    existing_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, existing_mac), config_entry.entry_id
    )
    assert existing_device is not None
    assert existing_device.name == "My phone"
    new_device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, new_mac), config_entry.entry_id
    )
    assert new_device_entry is not None
    assert new_device_entry.name == new_mac
    # The tracker of an unnamed client keeps its legacy name
    entity_id = entity_registry.async_get_entity_id(
        device_tracker.DOMAIN, DOMAIN, new_mac
    )
    assert entity_id is not None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.original_name == new_mac.replace(":", "_")
