"""Test floor template functions."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)

from tests.common import MockConfigEntry
from tests.helpers.template.helpers import assert_result_info, render_to_info


async def test_floors(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test floors function."""

    # Test no floors
    info = render_to_info(hass, "{{ floors() }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test one floor
    floor1 = floor_registry.async_create("First floor")
    info = render_to_info(hass, "{{ floors() }}")
    assert_result_info(info, [floor1.floor_id])
    assert info.rate_limit is None

    # Test multiple floors
    floor2 = floor_registry.async_create("Second floor")
    info = render_to_info(hass, "{{ floors() }}")
    assert_result_info(info, [floor1.floor_id, floor2.floor_id])
    assert info.rate_limit is None


async def test_floor_id(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test floor_id function."""

    def test(value: str, expected: str | None) -> None:
        info = render_to_info(hass, f"{{{{ floor_id('{value}') }}}}")
        assert_result_info(info, expected)
        assert info.rate_limit is None

        info = render_to_info(hass, f"{{{{ '{value}' | floor_id }}}}")
        assert_result_info(info, expected)
        assert info.rate_limit is None

    # Test non existing floor name
    test("Third floor", None)

    # Test wrong value type
    info = render_to_info(hass, "{{ floor_id(42) }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 42 | floor_id }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test with an actual floor
    floor = floor_registry.async_create("First floor")
    test("First floor", floor.floor_id)

    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)
    area_entry_hex = area_registry.async_get_or_create("123abc")

    # Create area, device, entity and assign area to device and entity
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
    device_entry = device_registry.async_update_device(
        device_entry.id, area_id=area_entry_hex.id
    )
    entity_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, area_id=area_entry_hex.id
    )

    test(area_entry_hex.id, None)
    test(device_entry.id, None)
    test(entity_entry.entity_id, None)

    # Add floor to area
    area_entry_hex = area_registry.async_update(
        area_entry_hex.id, floor_id=floor.floor_id
    )

    test(area_entry_hex.id, floor.floor_id)
    test(device_entry.id, floor.floor_id)
    test(entity_entry.entity_id, floor.floor_id)


async def test_floor_name(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test floor_name function."""

    def test(value: str, expected: str | None) -> None:
        info = render_to_info(hass, f"{{{{ floor_name('{value}') }}}}")
        assert_result_info(info, expected)
        assert info.rate_limit is None

        info = render_to_info(hass, f"{{{{ '{value}' | floor_name }}}}")
        assert_result_info(info, expected)
        assert info.rate_limit is None

    # Test non existing floor name
    test("Third floor", None)

    # Test wrong value type
    info = render_to_info(hass, "{{ floor_name(42) }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 42 | floor_name }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test existing floor ID
    floor = floor_registry.async_create("First floor")
    test(floor.floor_id, floor.name)

    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)
    area_entry_hex = area_registry.async_get_or_create("123abc")

    # Create area, device, entity and assign area to device and entity
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
    device_entry = device_registry.async_update_device(
        device_entry.id, area_id=area_entry_hex.id
    )
    entity_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, area_id=area_entry_hex.id
    )

    test(area_entry_hex.id, None)
    test(device_entry.id, None)
    test(entity_entry.entity_id, None)

    # Add floor to area
    area_entry_hex = area_registry.async_update(
        area_entry_hex.id, floor_id=floor.floor_id
    )

    test(area_entry_hex.id, floor.name)
    test(device_entry.id, floor.name)
    test(entity_entry.entity_id, floor.name)


async def test_floor_areas(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test floor_areas function."""

    # Test non existing floor ID
    info = render_to_info(hass, "{{ floor_areas('skyring') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 'skyring' | floor_areas }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ floor_areas(42) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 42 | floor_areas }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    floor = floor_registry.async_create("First floor")
    area = area_registry.async_create("Living room")
    area_registry.async_update(area.id, floor_id=floor.floor_id)

    # Get areas by floor ID
    info = render_to_info(hass, f"{{{{ floor_areas('{floor.floor_id}') }}}}")
    assert_result_info(info, [area.id])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{floor.floor_id}' | floor_areas }}}}")
    assert_result_info(info, [area.id])
    assert info.rate_limit is None

    # Get areas by floor name
    info = render_to_info(hass, f"{{{{ floor_areas('{floor.name}') }}}}")
    assert_result_info(info, [area.id])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{floor.name}' | floor_areas }}}}")
    assert_result_info(info, [area.id])
    assert info.rate_limit is None


async def test_floor_entities(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test floor_entities function."""

    # Test non existing floor ID
    info = render_to_info(hass, "{{ floor_entities('skyring') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 'skyring' | floor_entities }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ floor_entities(42) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 42 | floor_entities }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    floor = floor_registry.async_create("First floor")
    area1 = area_registry.async_create("Living room")
    area2 = area_registry.async_create("Dining room")
    area_registry.async_update(area1.id, floor_id=floor.floor_id)
    area_registry.async_update(area2.id, floor_id=floor.floor_id)

    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        "light",
        "hue",
        "living_room",
        config_entry=config_entry,
    )
    entity_registry.async_update_entity(entity_entry.entity_id, area_id=area1.id)
    entity_entry = entity_registry.async_get_or_create(
        "light",
        "hue",
        "dining_room",
        config_entry=config_entry,
    )
    entity_registry.async_update_entity(entity_entry.entity_id, area_id=area2.id)

    # Get entities by floor ID
    expected = ["light.hue_living_room", "light.hue_dining_room"]
    info = render_to_info(hass, f"{{{{ floor_entities('{floor.floor_id}') }}}}")
    assert_result_info(info, expected)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{floor.floor_id}' | floor_entities }}}}")
    assert_result_info(info, expected)
    assert info.rate_limit is None

    # Get entities by floor name
    info = render_to_info(hass, f"{{{{ floor_entities('{floor.name}') }}}}")
    assert_result_info(info, expected)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{floor.name}' | floor_entities }}}}")
    assert_result_info(info, expected)
    assert info.rate_limit is None
