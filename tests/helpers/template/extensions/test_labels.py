"""Test label template functions."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)

from tests.common import MockConfigEntry
from tests.helpers.template.helpers import assert_result_info, render_to_info


async def test_labels(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test labels function."""

    # Test no labels
    info = render_to_info(hass, "{{ labels() }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test one label
    label1 = label_registry.async_create("label1")
    info = render_to_info(hass, "{{ labels() }}")
    assert_result_info(info, [label1.label_id])
    assert info.rate_limit is None

    # Test multiple label
    label2 = label_registry.async_create("label2")
    info = render_to_info(hass, "{{ labels() }}")
    assert_result_info(info, [label1.label_id, label2.label_id])
    assert info.rate_limit is None

    # Test non-existing entity ID
    info = render_to_info(hass, "{{ labels('sensor.fake') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 'sensor.fake' | labels }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test non existing device ID (hex value)
    info = render_to_info(hass, "{{ labels('123abc') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ '123abc' | labels }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Create a device & entity for testing
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)
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

    # Test entity, which has no labels
    info = render_to_info(hass, f"{{{{ labels('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{entity_entry.entity_id}' | labels }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test device, which has no labels
    info = render_to_info(hass, f"{{{{ labels('{device_entry.id}') }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{device_entry.id}' | labels }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Add labels to the entity & device
    device_entry = device_registry.async_update_device(
        device_entry.id, labels=[label1.label_id]
    )
    entity_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, labels=[label2.label_id]
    )

    # Test entity, which now has a label
    info = render_to_info(hass, f"{{{{ '{entity_entry.entity_id}' | labels }}}}")
    assert_result_info(info, [label2.label_id])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ labels('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, [label2.label_id])
    assert info.rate_limit is None

    # Test device, which now has a label
    info = render_to_info(hass, f"{{{{ '{device_entry.id}' | labels }}}}")
    assert_result_info(info, [label1.label_id])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ labels('{device_entry.id}') }}}}")
    assert_result_info(info, [label1.label_id])
    assert info.rate_limit is None

    # Create area for testing
    area = area_registry.async_create("living room")

    # Test area, which has no labels
    info = render_to_info(hass, f"{{{{ '{area.id}' | labels }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ labels('{area.id}') }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Add label to the area
    area_registry.async_update(area.id, labels=[label1.label_id, label2.label_id])

    # Test area, which now has labels
    info = render_to_info(hass, f"{{{{ '{area.id}' | labels }}}}")
    assert_result_info(info, [label1.label_id, label2.label_id])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ labels('{area.id}') }}}}")
    assert_result_info(info, [label1.label_id, label2.label_id])
    assert info.rate_limit is None


async def test_label_id(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test label_id function."""
    # Test non existing label name
    info = render_to_info(hass, "{{ label_id('non-existing label') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 'non-existing label' | label_id }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ label_id(42) }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 42 | label_id }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test with an actual label
    label = label_registry.async_create("existing label")
    info = render_to_info(hass, "{{ label_id('existing label') }}")
    assert_result_info(info, label.label_id)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 'existing label' | label_id }}")
    assert_result_info(info, label.label_id)
    assert info.rate_limit is None


async def test_label_name(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test label_name function."""
    # Test non existing label ID
    info = render_to_info(hass, "{{ label_name('1234567890') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ '1234567890' | label_name }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ label_name(42) }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 42 | label_name }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test non existing label ID
    label = label_registry.async_create("choo choo")
    info = render_to_info(hass, f"{{{{ label_name('{label.label_id}') }}}}")
    assert_result_info(info, label.name)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{label.label_id}' | label_name }}}}")
    assert_result_info(info, label.name)
    assert info.rate_limit is None


async def test_label_description(
    hass: HomeAssistant,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test label_description function."""
    # Test non existing label ID
    info = render_to_info(hass, "{{ label_description('1234567890') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ '1234567890' | label_description }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ label_description(42) }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 42 | label_description }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test valid label ID
    label = label_registry.async_create("choo choo", description="chugga chugga")
    info = render_to_info(hass, f"{{{{ label_description('{label.label_id}') }}}}")
    assert_result_info(info, label.description)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{label.label_id}' | label_description }}}}")
    assert_result_info(info, label.description)
    assert info.rate_limit is None


async def test_label_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test label_entities function."""

    # Test non existing device ID
    info = render_to_info(hass, "{{ label_entities('deadbeef') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 'deadbeef' | label_entities }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ label_entities(42) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 42 | label_entities }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Create a fake config entry with a entity
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
    )

    # Add a label to the entity
    label = label_registry.async_create("Romantic Lights")
    entity_registry.async_update_entity(entity_entry.entity_id, labels={label.label_id})

    # Get entities by label ID
    info = render_to_info(hass, f"{{{{ label_entities('{label.label_id}') }}}}")
    assert_result_info(info, ["light.hue_5678"])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{label.label_id}' | label_entities }}}}")
    assert_result_info(info, ["light.hue_5678"])
    assert info.rate_limit is None

    # Get entities by label name
    info = render_to_info(hass, f"{{{{ label_entities('{label.name}') }}}}")
    assert_result_info(info, ["light.hue_5678"])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{label.name}' | label_entities }}}}")
    assert_result_info(info, ["light.hue_5678"])
    assert info.rate_limit is None


async def test_label_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test label_devices function."""

    # Test non existing device ID
    info = render_to_info(hass, "{{ label_devices('deadbeef') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 'deadbeef' | label_devices }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ label_devices(42) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 42 | label_devices }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Create a fake config entry with a device
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    # Add a label to it
    label = label_registry.async_create("Romantic Lights")
    device_registry.async_update_device(device_entry.id, labels=[label.label_id])

    # Get the devices from a label by its ID
    info = render_to_info(hass, f"{{{{ label_devices('{label.label_id}') }}}}")
    assert_result_info(info, [device_entry.id])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{label.label_id}' | label_devices }}}}")
    assert_result_info(info, [device_entry.id])
    assert info.rate_limit is None

    # Get the devices from a label by its name
    info = render_to_info(hass, f"{{{{ label_devices('{label.name}') }}}}")
    assert_result_info(info, [device_entry.id])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{label.name}' | label_devices }}}}")
    assert_result_info(info, [device_entry.id])
    assert info.rate_limit is None


async def test_label_areas(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test label_areas function."""

    # Test non existing area ID
    info = render_to_info(hass, "{{ label_areas('deadbeef') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 'deadbeef' | label_areas }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ label_areas(42) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 42 | label_areas }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Create an area with an label
    label = label_registry.async_create("Upstairs")
    master_bedroom = area_registry.async_create(
        "Master Bedroom", labels=[label.label_id]
    )

    # Get areas by label ID
    info = render_to_info(hass, f"{{{{ label_areas('{label.label_id}') }}}}")
    assert_result_info(info, [master_bedroom.id])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{label.label_id}' | label_areas }}}}")
    assert_result_info(info, [master_bedroom.id])
    assert info.rate_limit is None

    # Get areas by label name
    info = render_to_info(hass, f"{{{{ label_areas('{label.name}') }}}}")
    assert_result_info(info, [master_bedroom.id])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{label.name}' | label_areas }}}}")
    assert_result_info(info, [master_bedroom.id])
    assert info.rate_limit is None
