"""The tests for SleepIQ binary sensor platform."""
from homeassistant.components.binary_sensor import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_platform


async def test_setup_binary_sensor(hass: HomeAssistant, mock_aioresponse) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, DOMAIN)
    entity_registry = er.async_get(hass)

    assert len(entity_registry.entities) == 2

    entry = entity_registry.async_get("binary_sensor.sleepnumber_ile_test1_is_in_bed")
    assert entry.unique_id == "-31-R-InBed"
    assert hass.states.get(entry.entity_id).state == STATE_ON

    entry = entity_registry.async_get("binary_sensor.sleepnumber_ile_test2_is_in_bed")
    assert entry.unique_id == "-31-L-InBed"
    assert hass.states.get(entry.entity_id).state == STATE_OFF
