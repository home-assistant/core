"""Test template helper functions."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.template.helpers import raise_no_default, resolve_area_id

from tests.common import MockConfigEntry


def test_raise_no_default() -> None:
    """Test raise_no_default raises ValueError with correct message."""
    with pytest.raises(
        ValueError,
        match="Template error: test got invalid input 'invalid' when rendering or compiling template '' but no default was specified",
    ):
        raise_no_default("test", "invalid")


async def test_resolve_area_id(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test resolve_area_id function."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    # Test non existing entity id
    assert resolve_area_id(hass, "sensor.fake") is None

    # Test non existing device id (hex value)
    assert resolve_area_id(hass, "123abc") is None

    # Test non existing area name
    assert resolve_area_id(hass, "fake area name") is None

    # Test wrong value type
    assert resolve_area_id(hass, 56) is None

    area_entry_entity_id = area_registry.async_get_or_create("sensor.fake")

    # Test device with single entity, which has no area
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )
    assert resolve_area_id(hass, device_entry.id) is None
    assert resolve_area_id(hass, entity_entry.entity_id) is None

    # Test device ID, entity ID and area name as input with area name that looks like
    # a device ID
    area_entry_hex = area_registry.async_get_or_create("123abc")
    device_entry = device_registry.async_update_device(
        device_entry.id, area_id=area_entry_hex.id
    )
    entity_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, area_id=area_entry_hex.id
    )

    assert resolve_area_id(hass, device_entry.id) == area_entry_hex.id
    assert resolve_area_id(hass, entity_entry.entity_id) == area_entry_hex.id
    assert resolve_area_id(hass, area_entry_hex.name) == area_entry_hex.id

    # Test device ID, entity ID and area name as input with area name that looks like an
    # entity ID
    area_entry_entity_id = area_registry.async_get_or_create("sensor.fake")
    device_entry = device_registry.async_update_device(
        device_entry.id, area_id=area_entry_entity_id.id
    )
    entity_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, area_id=area_entry_entity_id.id
    )

    assert resolve_area_id(hass, device_entry.id) == area_entry_entity_id.id
    assert resolve_area_id(hass, entity_entry.entity_id) == area_entry_entity_id.id
    assert resolve_area_id(hass, area_entry_entity_id.name) == area_entry_entity_id.id

    # Make sure that when entity doesn't have an area but its device does, that's what
    # gets returned
    entity_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, area_id=None
    )

    assert resolve_area_id(hass, entity_entry.entity_id) == area_entry_entity_id.id

    # Test area alias
    area_with_alias = area_registry.async_get_or_create("Living Room")
    area_registry.async_update(area_with_alias.id, aliases={"lounge", "family room"})

    assert resolve_area_id(hass, "Living Room") == area_with_alias.id
    assert resolve_area_id(hass, "lounge") == area_with_alias.id
    assert resolve_area_id(hass, "family room") == area_with_alias.id
