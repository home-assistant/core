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

    gateway_1 = mock_gateway_fixture(command_store, GATEWAY_ID1)
    command_store.register_device(
        gateway_1, load_json_object_fixture("bulb_w.json", DOMAIN)
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

    # Create bulb 1 on gateway 1 in Device Registry - this has the old identifiers format
    gateway_1_bulb = device_registry.async_get_or_create(
        config_entry_id=config_entry1.entry_id,
        identifiers={(tradfri.DOMAIN, 65537)},
        name="bulb1",
    )

    # Update bulb 1 device to have both config-entry IDs
    # This is to simulate existing data scenario with older version of tradfri component
    device_registry.async_update_device(
        gateway_1_bulb.id,
        add_config_entry_id=config_entry2.entry_id,
    )

    # Set up all tradfri config entries.
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Validate that gateway 1 bulb 1 is still the same device entry
    # This inherently also validates that the device's identifiers have been updated to the new unique format
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry1.entry_id
    )
    assert (
        device_registry.async_get_device(
            identifiers={(tradfri.DOMAIN, f"{GATEWAY_ID1}-65537")}
        ).id
        == gateway_1_bulb.id
    )

    # Validate that gateway 1 bulb 1 only has only gateway 1's config ID associated to it
    assert device_entries[1].config_entries == {config_entry1.entry_id}

    # Validate that gateway 2 bulb 1 has been added to device registry and with correct unique identifiers
    # (This exists because the command_store seems to be executed for each gateway being set up - not
    # _only_ for the gateway that was in context in the register_device() function. )
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry2.entry_id
    )
    assert len(device_entries) == 2
    assert device_entries[1].identifiers == {(tradfri.DOMAIN, f"{GATEWAY_ID2}-65537")}

    # Validate that gateway 2 bulb 1 only has only gateway 2's config ID associated to it
    assert device_entries[1].config_entries == {config_entry2.entry_id}
