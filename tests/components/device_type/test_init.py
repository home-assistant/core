"""Test the Device type integration."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.device_type import DOMAIN, SmartPlug
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_type import get_device_type_class
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component


async def test_setup(hass: HomeAssistant) -> None:
    """Test the integration sets up."""
    assert await async_setup_component(hass, DOMAIN, {})


def test_smart_plug() -> None:
    """Test the smart plug is in the vocabulary."""
    assert get_device_type_class("smart_plug") is SmartPlug
    assert SmartPlug.ancestor_ids == ("smart_plug", "generic")
    assert {
        slot_id: slot.required for slot_id, slot in SmartPlug.declared_slots.items()
    } == {"outlet": True, "power": False, "energy": False}
    assert SmartPlug.outlet.accepts == (Platform.SWITCH,)
    assert SmartPlug.power.accepts_entity("sensor", "power")
    assert SmartPlug.energy.accepts_entity("sensor", "energy")


async def test_translations(hass: HomeAssistant) -> None:
    """Test the names of the device types are served."""
    assert await async_get_translations(hass, "en", "device_types", [DOMAIN]) == {
        "component.device_type.device_types.generic.name": "Device",
        "component.device_type.device_types.smart_plug.name": "Smart plug",
        "component.device_type.device_types.smart_plug.slots.outlet.name": "Outlet",
        "component.device_type.device_types.smart_plug.slots.power.name": "Power",
        "component.device_type.device_types.smart_plug.slots.energy.name": "Energy",
    }


async def test_missing_required_slots_logged(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a typed device without entities in its required slots is logged."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    for identifier, name, device_type in (
        (
            "empty_plug",
            "Empty plug",
            SmartPlug(outlet=(Platform.SWITCH, "empty_plug_outlet")),
        ),
        ("plug", "Plug", SmartPlug(outlet=(Platform.SWITCH, "plug_outlet"))),
        ("untyped", "Untyped", None),
    ):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("test", identifier)},
            name=name,
            device_type=device_type,
        )
    entity_registry.async_get_or_create(
        "switch", config_entry.domain, "plug_outlet", config_entry=config_entry
    )
    hass.set_state(CoreState.not_running)
    assert await async_setup_component(hass, DOMAIN, {})
    assert "required slots" not in caplog.text

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert caplog.text.count("required slots") == 1
    assert (
        "Device Empty plug of type smart_plug has no entity in its required slots"
        " outlet"
    ) in caplog.text
