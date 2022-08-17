"""Test the Fully Kiosk Browser light."""
from unittest.mock import MagicMock

from homeassistant.components.fully_kiosk.const import DOMAIN
import homeassistant.components.light as light
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_switches(
    hass: HomeAssistant, mock_fully_kiosk: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test Fully Kiosk switches."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    entity = hass.states.get("light.amazon_fire_screen")
    assert entity
    assert entity.state == "on"
    assert entity.attributes.get(light.ATTR_BRIGHTNESS) == 9

    entry = entity_registry.async_get("light.amazon_fire_screen")
    assert entry
    assert entry.unique_id == "abcdef-123456-screen"

    await call_service(hass, "turn_off", "light.amazon_fire_screen")
    assert len(mock_fully_kiosk.screenOff.mock_calls) == 1

    await call_service(hass, "turn_on", "light.amazon_fire_screen")
    assert len(mock_fully_kiosk.screenOn.mock_calls) == 1

    await hass.services.async_call(
        light.DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "light.amazon_fire_screen", light.ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    assert len(mock_fully_kiosk.setScreenBrightness.mock_calls) == 1

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url == "http://192.168.1.234:2323"
    assert device_entry.entry_type is None
    assert device_entry.hw_version is None
    assert device_entry.identifiers == {(DOMAIN, "abcdef-123456")}
    assert device_entry.manufacturer == "amzn"
    assert device_entry.model == "KFDOWI"
    assert device_entry.name == "Amazon Fire"
    assert device_entry.sw_version == "1.42.5"


def call_service(hass, service, entity_id):
    """Call any service on entity."""
    return hass.services.async_call(
        light.DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
