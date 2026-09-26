"""Test fixtures for the search integration."""

import pytest

from homeassistant.components.search import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(name="search_item_ids")
async def search_item_ids_fixture(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
) -> dict[str, str]:
    """Set up a device and a child device, each owning enabled and disabled entities.

    The child device inherits the area from its parent, so it is reached by an area
    or floor search without having an area of its own.

    Returns the item id to search by, per key.
    """
    assert await async_setup_component(hass, DOMAIN, {})

    floor = floor_registry.async_create("First floor")
    area = area_registry.async_create("Kitchen", floor_id=floor.floor_id)

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "1")}
    )
    device_registry.async_update_device(device.id, area_id=area.id)

    child_device = device_registry.async_get_or_create_child(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "1-child")},
        parent_device_id=device.id,
        name="Child",
    )

    entity_registry.async_get_or_create(
        "light",
        "test",
        "enabled",
        suggested_object_id="enabled",
        config_entry=config_entry,
        device_id=device.id,
    )
    entity_registry.async_get_or_create(
        "light",
        "test",
        "disabled",
        suggested_object_id="disabled",
        config_entry=config_entry,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    # A disabled entity that overrides its area instead of inheriting it from the
    # device is reached through the area index, which has no disabled filter.
    disabled_area_override_entity = entity_registry.async_get_or_create(
        "light",
        "test",
        "disabled_area_override",
        suggested_object_id="disabled_area_override",
        config_entry=config_entry,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    entity_registry.async_update_entity(
        disabled_area_override_entity.entity_id, area_id=area.id
    )

    entity_registry.async_get_or_create(
        "light",
        "test",
        "child_enabled",
        suggested_object_id="child_enabled",
        config_entry=config_entry,
        device_id=child_device.id,
    )
    entity_registry.async_get_or_create(
        "light",
        "test",
        "child_disabled",
        suggested_object_id="child_disabled",
        config_entry=config_entry,
        device_id=child_device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    return {
        "floor": floor.floor_id,
        "area": area.id,
        "device": device.id,
        "child_device": child_device.id,
    }
