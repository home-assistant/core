"""Tests for Tradfri setup."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pytradfri.device import Device

from homeassistant.components import tradfri
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.components.tradfri.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import GATEWAY_ID, GATEWAY_ID1, GATEWAY_ID2

from tests.common import MockConfigEntry, load_fixture


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


@pytest.fixture(scope="module")
def bulb_w() -> str:
    """Return a bulb W response."""
    return load_fixture("bulb_w.json", DOMAIN)


@pytest.mark.parametrize(
    ("device", "entity_id", "state_attributes"),
    [
        (
            "bulb_w",
            "light.test_w",
            {
                ATTR_BRIGHTNESS: 250,
                ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
                ATTR_COLOR_MODE: ColorMode.BRIGHTNESS,
            },
        ),
    ],
    indirect=["device"],
)
async def test_migrate_entity_unique_ids(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: Device,
    entity_id: str,
    state_attributes: dict[str, Any],
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
    config_entry2 = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            tradfri.CONF_HOST: "mock-host2",
            tradfri.CONF_IDENTITY: "mock-identity2",
            tradfri.CONF_KEY: "mock-key2",
            tradfri.CONF_GATEWAY_ID: GATEWAY_ID2,
        },
    )

    config_entry1.add_to_hass(hass)
    config_entry2.add_to_hass(hass)

    # No need to explicitly run async_setup() for each config-entry;
    # __init__.py will loop through all configured gateways itself when invoked.
    await hass.config_entries.async_setup(config_entry1.entry_id)
    await hass.async_block_till_done()

    # Update bulb 1 identifiers on gateway 1 reflect old-style ID
    # Update bulb 1 device to have both config-entry IDs
    # This is to simulate existing data scenario with older version of tradfri component
    gateway_1_bulb = device_registry.async_get_device(
        identifiers={(tradfri.DOMAIN, f"{GATEWAY_ID1}-65537")}
    )
    device_registry.async_update_device(
        gateway_1_bulb.id,
        add_config_entry_id=config_entry2.entry_id,
        new_identifiers={(tradfri.DOMAIN, 65537)},
    )
    # Remove bulb 1 from gateway 2 completely
    # This is to simulate existing data scenario with older version of tradfri component
    gateway_2_bulb = device_registry.async_get_device(
        identifiers={(tradfri.DOMAIN, f"{GATEWAY_ID2}-65537")}
    )
    device_registry.async_remove_device(gateway_2_bulb.id)

    # Validate that gateway 1 has 2 devices associated to it
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry1.entry_id
    )
    assert len(device_entries) == 2

    # Validate that gateway 2 still technically has 2 devices associated to it
    # despite removing the bulb - async_entries_for_config_entry() will qualify
    # the bulb device that is now associated to both config-entries
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry2.entry_id
    )
    assert len(device_entries) == 2

    # Force updates of all config entries to re-run async_setup_entry with device_registry and entity_registry persisting
    await hass.config_entries.async_reload(config_entry1.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(config_entry2.entry_id)
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

    # Validate that gateway 2 bulb 1 has been re-added to device registry and with correct unique identifiers
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry2.entry_id
    )
    assert len(device_entries) == 2
    assert device_entries[1].identifiers == {(tradfri.DOMAIN, f"{GATEWAY_ID2}-65537")}

    # Validate that gateway 2 bulb 1 only has only gateway 2's config ID associated to it
    assert device_entries[1].config_entries == {config_entry2.entry_id}
