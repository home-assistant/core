"""Test area template functions."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from tests.common import MockConfigEntry
from tests.helpers.template.helpers import assert_result_info, render_to_info


async def test_areas(hass: HomeAssistant, area_registry: ar.AreaRegistry) -> None:
    """Test areas function."""
    # Test no areas
    info = render_to_info(hass, "{{ areas() }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test one area
    area1 = area_registry.async_get_or_create("area1")
    info = render_to_info(hass, "{{ areas() }}")
    assert_result_info(info, [area1.id])
    assert info.rate_limit is None

    # Test multiple areas
    area2 = area_registry.async_get_or_create("area2")
    info = render_to_info(hass, "{{ areas() }}")
    assert_result_info(info, [area1.id, area2.id])
    assert info.rate_limit is None


async def test_area_id(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test area_id function."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    # Test non existing entity id
    info = render_to_info(hass, "{{ area_id('sensor.fake') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test non existing device id (hex value)
    info = render_to_info(hass, "{{ area_id('123abc') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test non existing area name
    info = render_to_info(hass, "{{ area_id('fake area name') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ area_id(56) }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    area_registry.async_get_or_create("sensor.fake")

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
    info = render_to_info(hass, f"{{{{ area_id('{device_entry.id}') }}}}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ area_id('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test device ID, entity ID and area name as input with area name that looks like
    # a device ID. Try a filter too
    area_entry_hex = area_registry.async_get_or_create("123abc")
    device_entry = device_registry.async_update_device(
        device_entry.id, area_id=area_entry_hex.id
    )
    entity_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, area_id=area_entry_hex.id
    )

    info = render_to_info(hass, f"{{{{ '{device_entry.id}' | area_id }}}}")
    assert_result_info(info, area_entry_hex.id)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ area_id('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, area_entry_hex.id)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ area_id('{area_entry_hex.name}') }}}}")
    assert_result_info(info, area_entry_hex.id)
    assert info.rate_limit is None

    # Test device ID, entity ID and area name as input with area name that looks like an
    # entity ID
    area_entry_entity_id = area_registry.async_get_or_create("sensor.fake")
    device_entry = device_registry.async_update_device(
        device_entry.id, area_id=area_entry_entity_id.id
    )
    entity_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, area_id=area_entry_entity_id.id
    )

    info = render_to_info(hass, f"{{{{ area_id('{device_entry.id}') }}}}")
    assert_result_info(info, area_entry_entity_id.id)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ area_id('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, area_entry_entity_id.id)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ area_id('{area_entry_entity_id.name}') }}}}")
    assert_result_info(info, area_entry_entity_id.id)
    assert info.rate_limit is None

    # Make sure that when entity doesn't have an area but its device does, that's what
    # gets returned
    entity_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, area_id=area_entry_entity_id.id
    )

    info = render_to_info(hass, f"{{{{ area_id('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, area_entry_entity_id.id)
    assert info.rate_limit is None


async def test_area_name(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test area_name function."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    # Test non existing entity id
    info = render_to_info(hass, "{{ area_name('sensor.fake') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test non existing device id (hex value)
    info = render_to_info(hass, "{{ area_name('123abc') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test non existing area id
    info = render_to_info(hass, "{{ area_name('1234567890') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ area_name(56) }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

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
    info = render_to_info(hass, f"{{{{ area_name('{device_entry.id}') }}}}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ area_name('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test device ID, entity ID and area id as input. Try a filter too
    area_entry = area_registry.async_get_or_create("123abc")
    device_entry = device_registry.async_update_device(
        device_entry.id, area_id=area_entry.id
    )
    entity_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, area_id=area_entry.id
    )

    info = render_to_info(hass, f"{{{{ '{device_entry.id}' | area_name }}}}")
    assert_result_info(info, area_entry.name)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ area_name('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, area_entry.name)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ area_name('{area_entry.id}') }}}}")
    assert_result_info(info, area_entry.name)
    assert info.rate_limit is None

    # Make sure that when entity doesn't have an area but its device does, that's what
    # gets returned
    entity_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, area_id=None
    )

    info = render_to_info(hass, f"{{{{ area_name('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, area_entry.name)
    assert info.rate_limit is None


async def test_area_entities(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test area_entities function."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    # Test non existing device id
    info = render_to_info(hass, "{{ area_entities('deadbeef') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ area_entities(56) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    area_entry = area_registry.async_get_or_create("sensor.fake")
    entity_entry = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
    )
    entity_registry.async_update_entity(entity_entry.entity_id, area_id=area_entry.id)

    info = render_to_info(hass, f"{{{{ area_entities('{area_entry.id}') }}}}")
    assert_result_info(info, ["light.hue_5678"])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{area_entry.name}' | area_entities }}}}")
    assert_result_info(info, ["light.hue_5678"])
    assert info.rate_limit is None

    # Test for entities that inherit area from device
    device_entry = device_registry.async_get_or_create(
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        config_entry_id=config_entry.entry_id,
        suggested_area="sensor.fake",
    )
    entity_registry.async_get_or_create(
        "light",
        "hue_light",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )

    info = render_to_info(hass, f"{{{{ '{area_entry.name}' | area_entities }}}}")
    assert_result_info(info, ["light.hue_5678", "light.hue_light_5678"])
    assert info.rate_limit is None


async def test_area_devices(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test area_devices function."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    # Test non existing device id
    info = render_to_info(hass, "{{ area_devices('deadbeef') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ area_devices(56) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    area_entry = area_registry.async_get_or_create("sensor.fake")
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        suggested_area=area_entry.name,
    )

    info = render_to_info(hass, f"{{{{ area_devices('{area_entry.id}') }}}}")
    assert_result_info(info, [device_entry.id])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{area_entry.name}' | area_devices }}}}")
    assert_result_info(info, [device_entry.id])
    assert info.rate_limit is None
