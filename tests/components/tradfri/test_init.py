"""Tests for Tradfri setup."""

from unittest.mock import MagicMock

from pytradfri.const import ATTR_FIRMWARE_VERSION, ATTR_GATEWAY_ID
from pytradfri.gateway import Gateway

from homeassistant.components import tradfri
from homeassistant.components.tradfri.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import GATEWAY_ID, GATEWAY_ID1, GATEWAY_ID2
from .common import CommandStore

from tests.common import MockConfigEntry, load_json_object_fixture


async def test_entry_setup_unload(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_api_factory: MagicMock
) -> None:
    """Test config entry setup and unload."""
    config_entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            tradfri.CONF_HOST: "mock-host",
            tradfri.CONF_IDENTITY: "mock-identity",
            tradfri.CONF_KEY: "mock-key",
            tradfri.CONF_GATEWAY_ID: GATEWAY_ID,
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert device_entries
    device_entry = device_entries[0]
    assert device_entry.identifiers == {
        (tradfri.DOMAIN, config_entry.data[tradfri.CONF_GATEWAY_ID])
    }
    assert device_entry.manufacturer == "IKEA of Sweden"
    assert device_entry.name == "Gateway"
    assert device_entry.model == "E1526"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_api_factory.shutdown.call_count == 1


async def test_remove_stale_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test remove stale device registry entries."""
    config_entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            tradfri.CONF_HOST: "mock-host",
            tradfri.CONF_IDENTITY: "mock-identity",
            tradfri.CONF_KEY: "mock-key",
            tradfri.CONF_GATEWAY_ID: GATEWAY_ID,
        },
    )

    config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(tradfri.DOMAIN, "stale_device_id")},
        name="stale-device",
    )
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == 1
    device_entry = device_entries[0]
    assert device_entry.identifiers == {(tradfri.DOMAIN, "stale_device_id")}

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    # Check that only the gateway device entry remains.
    assert len(device_entries) == 1
    device_entry = device_entries[0]
    assert device_entry.identifiers == {
        (tradfri.DOMAIN, config_entry.data[tradfri.CONF_GATEWAY_ID])
    }
    assert device_entry.manufacturer == "IKEA of Sweden"
    assert device_entry.name == "Gateway"
    assert device_entry.model == "E1526"


async def test_migrate_config_entry_and_identifiers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    command_store: CommandStore,
) -> None:
    """Test correction of device registry entries."""
    config_entry1 = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            tradfri.CONF_HOST: "mock-host1",
            tradfri.CONF_IDENTITY: "mock-identity1",
            tradfri.CONF_KEY: "mock-key1",
            tradfri.CONF_GATEWAY_ID: GATEWAY_ID1,
        },
    )

    gateway1 = mock_gateway_fixture(command_store, GATEWAY_ID1)
    command_store.register_device(
        gateway1, load_json_object_fixture("bulb_w.json", DOMAIN)
    )
    config_entry1.add_to_hass(hass)

    config_entry2 = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            tradfri.CONF_HOST: "mock-host2",
            tradfri.CONF_IDENTITY: "mock-identity2",
            tradfri.CONF_KEY: "mock-key2",
            tradfri.CONF_GATEWAY_ID: GATEWAY_ID2,
        },
    )

    config_entry2.add_to_hass(hass)

    # Add non-tradfri config entry for use in testing negation logic
    config_entry3 = MockConfigEntry(
        domain="test_domain",
    )

    config_entry3.add_to_hass(hass)

    # Create gateway device for config entry 1
    gateway1_device = device_registry.async_get_or_create(
        config_entry_id=config_entry1.entry_id,
        identifiers={(config_entry1.domain, config_entry1.data["gateway_id"])},
        name="Gateway",
    )

    # Create bulb 1 on gateway 1 in Device Registry - this has the old identifiers format
    gateway1_bulb1 = device_registry.async_get_or_create(
        config_entry_id=config_entry1.entry_id,
        identifiers={(tradfri.DOMAIN, 65537)},
        name="bulb1",
    )

    # Update bulb 1 device to have both config entry IDs
    # This is to simulate existing data scenario with older version of tradfri component
    device_registry.async_update_device(
        gateway1_bulb1.id,
        add_config_entry_id=config_entry2.entry_id,
    )

    # Create bulb 2 on gateway 1 in Device Registry - this has the new identifiers format
    gateway1_bulb2 = device_registry.async_get_or_create(
        config_entry_id=config_entry1.entry_id,
        identifiers={(tradfri.DOMAIN, f"{GATEWAY_ID1}-65538")},
        name="bulb2",
    )

    # Update bulb 2 device to have an additional config entry from config_entry3
    # This is to simulate scenario whereby a device entry
    # is shared by multiple config entries
    # and where at least one of those config entries is not the 'tradfri' domain
    device_registry.async_update_device(
        gateway1_bulb2.id,
        add_config_entry_id=config_entry3.entry_id,
        merge_identifiers={("test_domain", "config_entry_3-device2")},
    )

    # Create a device on config entry 3 in Device Registry
    config_entry3_device = device_registry.async_get_or_create(
        config_entry_id=config_entry3.entry_id,
        identifiers={("test_domain", "config_entry_3-device1")},
        name="device",
    )

    # Set up all tradfri config entries.
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Validate that gateway 1 bulb 1 is still the same device entry
    # This inherently also validates that the device's identifiers
    # have been updated to the new unique format
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry1.entry_id
    )
    assert (
        device_registry.async_get_device(
            identifiers={(tradfri.DOMAIN, f"{GATEWAY_ID1}-65537")}
        ).id
        == gateway1_bulb1.id
    )

    # Validate that gateway 1 bulb 1 only has gateway 1's config ID associated to it
    # (Device at index 0 is the gateway)
    assert device_entries[1].config_entries == {config_entry1.entry_id}

    # Validate that the gateway 1 device is unchanged
    assert device_entries[0].id == gateway1_device.id
    assert device_entries[0].identifiers == gateway1_device.identifiers
    assert device_entries[0].config_entries == gateway1_device.config_entries

    # Validate that gateway 1 bulb 2 now only exists associated to config entry 3.
    # The device will have had its identifiers updated to the new format (for the tradfri
    # domain) per migrate_config_entry_and_identifiers().
    # The device will have then been removed from config entry 1 (gateway1)
    # due to it not matching a device in the command store.
    device_entry = device_registry.async_get_device(
        identifiers={(tradfri.DOMAIN, f"{GATEWAY_ID1}-65538")}
    )

    assert device_entry.id == gateway1_bulb2.id
    # Assert that the only config entry associated to this device is config entry 3
    assert device_entry.config_entries == {config_entry3.entry_id}
    # Assert that that device's other identifiers remain untouched
    assert device_entry.identifiers == {
        (tradfri.DOMAIN, f"{GATEWAY_ID1}-65538"),
        ("test_domain", "config_entry_3-device2"),
    }

    # Validate that gateway 2 bulb 1 has been added to device registry and with correct unique identifiers
    # (This bulb device exists on gateway 2 because the command_store created above will be executed
    # for each gateway being set up.)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry2.entry_id
    )
    assert len(device_entries) == 2
    assert device_entries[1].identifiers == {(tradfri.DOMAIN, f"{GATEWAY_ID2}-65537")}

    # Validate that gateway 2 bulb 1 only has gateway 2's config ID associated to it
    assert device_entries[1].config_entries == {config_entry2.entry_id}

    # Validate that config entry 3 device 1 is still present,
    # and has not had its config entries or identifiers changed
    # N.B. The gateway1_bulb2 device will qualify in this set
    # because the config entry 3 was added to it above
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry3.entry_id
    )
    assert len(device_entries) == 2
    assert device_entries[0].id == config_entry3_device.id
    assert device_entries[0].identifiers == {("test_domain", "config_entry_3-device1")}
    assert device_entries[0].config_entries == {config_entry3.entry_id}

    # Assert that the tradfri config entries have been migrated to v2 and
    # the non-tradfri config entry remains at v1
    assert config_entry1.version == 2
    assert config_entry2.version == 2
    assert config_entry3.version == 1


def mock_gateway_fixture(command_store: CommandStore, gateway_id: str) -> Gateway:
    """Mock a Tradfri gateway."""
    gateway = Gateway()
    command_store.register_response(
        gateway.get_gateway_info(),
        {ATTR_GATEWAY_ID: gateway_id, ATTR_FIRMWARE_VERSION: "1.2.1234"},
    )
    command_store.register_response(
        gateway.get_devices(),
        [],
    )
    return gateway
