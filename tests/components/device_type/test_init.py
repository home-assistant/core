"""Test the Device type integration."""

from homeassistant.components.device_type import DOMAIN, SmartPlug
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_type import get_device_type_class
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component


async def test_setup(hass: HomeAssistant) -> None:
    """Test the integration sets up."""
    assert await async_setup_component(hass, DOMAIN, {})


def test_smart_plug() -> None:
    """Test the smart plug is in the vocabulary."""
    assert get_device_type_class("smart_plug") is SmartPlug
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
