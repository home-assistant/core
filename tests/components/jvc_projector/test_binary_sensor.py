"""Tests for the JVC Projector binary sensor device."""
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import setup_platform


async def test_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    entry = entity_registry.async_get("binary_sensor.jvc_projector")
    assert entry.unique_id == "2834013428b6_BinarySensor"


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the binary sensor attributes are correct."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    state = hass.states.get("binary_sensor.is_on")
    assert state.state == STATE_OFF
