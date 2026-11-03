"""Tests for the LIFX coordinator."""

import pytest

from homeassistant.components.lifx.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from . import LABEL, SERIAL, async_setup_lifx_entry, async_trigger_update
from .helpers import create_mock_light


async def test_label_change_renames_the_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test a label changed in the LIFX app renames the device on the next poll."""
    device = create_mock_light()
    entry = await async_setup_lifx_entry(hass, device)

    device.state.label = "Reading Lamp"
    await async_trigger_update(hass)

    registered = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), entry.entry_id
    )
    assert registered
    assert registered.name == "Reading Lamp"
    assert hass.states.get("light.my_group_reading_lamp") is None
    state = hass.states.get("light.my_group_my_bulb")
    assert state
    assert state.name == "Reading Lamp"


async def test_label_change_keeps_a_name_set_by_the_user(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test a name the user gave the device still takes precedence."""
    device = create_mock_light()
    entry = await async_setup_lifx_entry(hass, device)
    registered = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), entry.entry_id
    )
    assert registered
    device_registry.async_update_device(registered.id, name_by_user="Desk")

    device.state.label = "Reading Lamp"
    await async_trigger_update(hass)

    registered = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), entry.entry_id
    )
    assert registered
    assert registered.name == "Reading Lamp"
    assert registered.name_by_user == "Desk"


async def test_empty_label_keeps_the_device_name(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test a light reporting no label keeps the name it had."""
    device = create_mock_light()
    entry = await async_setup_lifx_entry(hass, device)

    device.state.label = ""
    await async_trigger_update(hass)

    registered = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), entry.entry_id
    )
    assert registered
    assert registered.name == LABEL


async def test_label_change_drops_the_area_name(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test a new label starting with the device's area is renamed without it."""
    device = create_mock_light()
    entry = await async_setup_lifx_entry(hass, device)

    device.state.label = "My Group Reading Lamp"
    await async_trigger_update(hass)

    registered = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), entry.entry_id
    )
    assert registered
    assert registered.name == "Reading Lamp"


@pytest.mark.parametrize(
    ("area_name", "expected_name"),
    [
        pytest.param("Kitchen", "Pendant", id="area_in_label"),
        pytest.param("Lounge", "Kitchen Pendant", id="area_not_in_label"),
    ],
)
async def test_area_change_renames_the_device(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    area_name: str,
    expected_name: str,
) -> None:
    """Test moving the device to another area renames it on the next poll."""
    device = create_mock_light()
    device.state.label = "Kitchen Pendant"
    entry = await async_setup_lifx_entry(hass, device)
    registered = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), entry.entry_id
    )
    assert registered
    assert registered.name == "Kitchen Pendant"

    device_registry.async_update_device(
        registered.id, area_id=area_registry.async_get_or_create(area_name).id
    )
    await async_trigger_update(hass)

    registered = device_registry.async_get(registered.id)
    assert registered
    assert registered.name == expected_name


async def test_entity_id_format_change_renames_the_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test leaving the area out of the entity ID format restores the full label."""
    device = create_mock_light()
    device.state.label = "My Group Pendant"
    entry = await async_setup_lifx_entry(hass, device)
    registered = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), entry.entry_id
    )
    assert registered
    assert registered.name == "Pendant"

    entity_registry.async_update_settings(
        entity_id_parts=[er.EntityNamePart.DEVICE, er.EntityNamePart.ENTITY]
    )
    await async_trigger_update(hass)

    registered = device_registry.async_get(registered.id)
    assert registered
    assert registered.name == "My Group Pendant"
