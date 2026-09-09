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

from tests.common import MockConfigEntry, async_load_json_object_fixture


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
    """Test migration of device registry identifiers to the unique format.

    A device belongs to a single config entry, so a stale tradfri device is
    removed rather than moved to another config entry.
    """
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
        gateway1, await async_load_json_object_fixture(hass, "bulb_w.json", DOMAIN)
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

    # A non-tradfri config entry, to verify its device and version are untouched.
    config_entry3 = MockConfigEntry(domain="test_domain")
    config_entry3.add_to_hass(hass)

    gateway1_device = device_registry.async_get_or_create(
        config_entry_id=config_entry1.entry_id,
        identifiers={(config_entry1.domain, config_entry1.data["gateway_id"])},
        name="Gateway",
    )

    # Bulb with the old, non-unique identifier format; it is still reported by
    # the gateway (id 65537 from bulb_w.json), so migration renames its
    # identifier and it is kept.
    gateway1_bulb1 = device_registry.async_get_or_create(
        config_entry_id=config_entry1.entry_id,
        identifiers={(tradfri.DOMAIN, 65537)},
        name="bulb1",
    )

    # Bulb with the new identifier format that is no longer reported by the
    # gateway (id 65538), so it is a stale device that gets removed.
    device_registry.async_get_or_create(
        config_entry_id=config_entry1.entry_id,
        identifiers={(tradfri.DOMAIN, f"{GATEWAY_ID1}-65538")},
        name="bulb2",
    )

    config_entry3_device = device_registry.async_get_or_create(
        config_entry_id=config_entry3.entry_id,
        identifiers={("test_domain", "config_entry_3-device1")},
        name="device",
    )

    # Set up all tradfri config entries.
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Bulb 1 kept the same device entry, its identifier migrated to the unique
    # format, and it is still owned only by gateway 1's config entry.
    migrated_bulb1 = device_registry.async_get_device_by_identifier(
        (tradfri.DOMAIN, f"{GATEWAY_ID1}-65537"), config_entry1.entry_id
    )
    assert migrated_bulb1.id == gateway1_bulb1.id
    assert migrated_bulb1.config_entry_id == config_entry1.entry_id

    # The gateway device is unchanged.
    migrated_gateway1 = device_registry.async_get_device_by_identifier(
        (tradfri.DOMAIN, GATEWAY_ID1), config_entry1.entry_id
    )
    assert migrated_gateway1.id == gateway1_device.id
    assert migrated_gateway1.identifiers == gateway1_device.identifiers
    assert migrated_gateway1.config_entry_id == config_entry1.entry_id

    # Bulb 2 is stale and has been removed, not moved to another config entry.
    assert (
        device_registry.async_get_device_by_identifier(
            (tradfri.DOMAIN, f"{GATEWAY_ID1}-65538"), config_entry1.entry_id
        )
        is None
    )

    # Gateway 2 discovered the same bulb and stored it with the unique
    # identifier format, owned only by gateway 2's config entry. (This bulb
    # exists on gateway 2 because the command store is shared between gateways.)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry2.entry_id
    )
    assert len(device_entries) == 2
    gateway2_bulb = device_registry.async_get_device_by_identifier(
        (tradfri.DOMAIN, f"{GATEWAY_ID2}-65537"), config_entry2.entry_id
    )
    assert gateway2_bulb.config_entry_id == config_entry2.entry_id

    # The non-tradfri device and config entry are untouched.
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry3.entry_id
    )
    assert len(device_entries) == 1
    assert device_entries[0].id == config_entry3_device.id
    assert device_entries[0].identifiers == {("test_domain", "config_entry_3-device1")}
    assert device_entries[0].config_entry_id == config_entry3.entry_id

    # The tradfri config entries have been migrated to v2 and the non-tradfri
    # config entry remains at v1.
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
