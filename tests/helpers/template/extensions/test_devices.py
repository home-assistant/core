"""Test device template functions."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.template import TemplateError

from tests.common import MockConfigEntry
from tests.helpers.template.helpers import assert_result_info, render_to_info


async def test_device_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device_entities function."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    # Test non existing device ids
    info = render_to_info(hass, "{{ device_entities('abc123') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ device_entities(56) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test device without entities
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    info = render_to_info(hass, f"{{{{ device_entities('{device_entry.id}') }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test device with single entity, which has no state
    entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )
    info = render_to_info(hass, f"{{{{ device_entities('{device_entry.id}') }}}}")
    assert_result_info(info, ["light.hue_5678"], [])
    assert info.rate_limit is None
    info = render_to_info(
        hass,
        (
            f"{{{{ device_entities('{device_entry.id}') | expand "
            "| sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}"
        ),
    )
    assert_result_info(info, "", ["light.hue_5678"])
    assert info.rate_limit is None

    # Test device with single entity, with state
    hass.states.async_set("light.hue_5678", "happy")
    info = render_to_info(
        hass,
        (
            f"{{{{ device_entities('{device_entry.id}') | expand "
            "| sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}"
        ),
    )
    assert_result_info(info, "light.hue_5678", ["light.hue_5678"])
    assert info.rate_limit is None

    # Test device with multiple entities, which have a state
    entity_registry.async_get_or_create(
        "light",
        "hue",
        "ABCD",
        config_entry=config_entry,
        device_id=device_entry.id,
    )
    hass.states.async_set("light.hue_abcd", "camper")
    info = render_to_info(hass, f"{{{{ device_entities('{device_entry.id}') }}}}")
    assert_result_info(info, ["light.hue_5678", "light.hue_abcd"], [])
    assert info.rate_limit is None
    info = render_to_info(
        hass,
        (
            f"{{{{ device_entities('{device_entry.id}') | expand "
            "| sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}"
        ),
    )
    assert_result_info(
        info, "light.hue_5678, light.hue_abcd", ["light.hue_5678", "light.hue_abcd"]
    )
    assert info.rate_limit is None


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device_id function."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model="test",
        name="test",
    )
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "test", suggested_object_id="test", device_id=device_entry.id
    )
    entity_entry_no_device = entity_registry.async_get_or_create(
        "sensor", "test", "test_no_device", suggested_object_id="test"
    )

    info = render_to_info(hass, "{{ 'sensor.fail' | device_id }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ 56 | device_id }}")
    assert_result_info(info, None)

    info = render_to_info(hass, "{{ 'not_a_real_entity_id' | device_id }}")
    assert_result_info(info, None)

    info = render_to_info(
        hass, f"{{{{ device_id('{entity_entry_no_device.entity_id}') }}}}"
    )
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ device_id('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, device_entry.id)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ device_id('test') }}")
    assert_result_info(info, device_entry.id)
    assert info.rate_limit is None


async def test_device_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device_name function."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    # Test non existing entity id
    info = render_to_info(hass, "{{ device_name('sensor.fake') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test non existing device id
    info = render_to_info(hass, "{{ device_name('1234567890') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test wrong value type
    info = render_to_info(hass, "{{ device_name(56) }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test device with single entity
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        name="A light",
    )
    entity_entry = entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )
    info = render_to_info(hass, f"{{{{ device_name('{device_entry.id}') }}}}")
    assert_result_info(info, device_entry.name)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ device_name('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, device_entry.name)
    assert info.rate_limit is None

    # Test device after renaming
    device_entry = device_registry.async_update_device(
        device_entry.id,
        name_by_user="My light",
    )

    info = render_to_info(hass, f"{{{{ device_name('{device_entry.id}') }}}}")
    assert_result_info(info, device_entry.name_by_user)
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ device_name('{entity_entry.entity_id}') }}}}")
    assert_result_info(info, device_entry.name_by_user)
    assert info.rate_limit is None


async def test_device_attr(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device_attr and is_device_attr functions."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    # Test non existing device ids (device_attr)
    info = render_to_info(hass, "{{ device_attr('abc123', 'id') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ device_attr(56, 'id') }}")
    with pytest.raises(TemplateError):
        assert_result_info(info, None)

    # Test non existing device ids (is_device_attr)
    info = render_to_info(hass, "{{ is_device_attr('abc123', 'id', 'test') }}")
    assert_result_info(info, False)
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ is_device_attr(56, 'id', 'test') }}")
    with pytest.raises(TemplateError):
        assert_result_info(info, False)

    # Test non existing entity id (device_attr)
    info = render_to_info(hass, "{{ device_attr('entity.test', 'id') }}")
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test non existing entity id (is_device_attr)
    info = render_to_info(hass, "{{ is_device_attr('entity.test', 'id', 'test') }}")
    assert_result_info(info, False)
    assert info.rate_limit is None

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model="test",
    )
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test", "test", suggested_object_id="test", device_id=device_entry.id
    )

    # Test non existent device attribute (device_attr)
    info = render_to_info(
        hass, f"{{{{ device_attr('{device_entry.id}', 'invalid_attr') }}}}"
    )
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test non existent device attribute (is_device_attr)
    info = render_to_info(
        hass, f"{{{{ is_device_attr('{device_entry.id}', 'invalid_attr', 'test') }}}}"
    )
    assert_result_info(info, False)
    assert info.rate_limit is None

    # Test None device attribute (device_attr)
    info = render_to_info(
        hass, f"{{{{ device_attr('{device_entry.id}', 'manufacturer') }}}}"
    )
    assert_result_info(info, None)
    assert info.rate_limit is None

    # Test None device attribute mismatch (is_device_attr)
    info = render_to_info(
        hass, f"{{{{ is_device_attr('{device_entry.id}', 'manufacturer', 'test') }}}}"
    )
    assert_result_info(info, False)
    assert info.rate_limit is None

    # Test None device attribute match (is_device_attr)
    info = render_to_info(
        hass, f"{{{{ is_device_attr('{device_entry.id}', 'manufacturer', None) }}}}"
    )
    assert_result_info(info, True)
    assert info.rate_limit is None

    # Test valid device attribute match (device_attr)
    info = render_to_info(hass, f"{{{{ device_attr('{device_entry.id}', 'model') }}}}")
    assert_result_info(info, "test")
    assert info.rate_limit is None

    # Test valid device attribute match (device_attr)
    info = render_to_info(
        hass, f"{{{{ device_attr('{entity_entry.entity_id}', 'model') }}}}"
    )
    assert_result_info(info, "test")
    assert info.rate_limit is None

    # Test valid device attribute mismatch (is_device_attr)
    info = render_to_info(
        hass, f"{{{{ is_device_attr('{device_entry.id}', 'model', 'fail') }}}}"
    )
    assert_result_info(info, False)
    assert info.rate_limit is None

    # Test valid device attribute match (is_device_attr)
    info = render_to_info(
        hass, f"{{{{ is_device_attr('{device_entry.id}', 'model', 'test') }}}}"
    )
    assert_result_info(info, True)
    assert info.rate_limit is None

    # Test filter syntax (device_attr)
    info = render_to_info(
        hass, f"{{{{ '{entity_entry.entity_id}' | device_attr('model') }}}}"
    )
    assert_result_info(info, "test")
    assert info.rate_limit is None

    # Test test syntax (is_device_attr)
    info = render_to_info(
        hass,
        (
            f"{{{{ ['{device_entry.id}'] | select('is_device_attr', 'model', 'test') "
            "| list }}"
        ),
    )
    assert_result_info(info, [device_entry.id])
    assert info.rate_limit is None
