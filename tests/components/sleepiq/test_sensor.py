"""The tests for SleepIQ sensor platform."""
from homeassistant.components.sensor import DOMAIN
from homeassistant.helpers import entity_registry as er

from .conftest import setup_platform


async def test_setup(hass, mock_aioresponse):
    """Test for successfully setting up the SleepIQ platform."""
    await setup_platform(hass, DOMAIN)
    entity_registry = er.async_get(hass)

    assert len(entity_registry.entities) == 2

    entry = entity_registry.async_get("sensor.sleepnumber_ile_test1_sleepnumber")
    assert entry.original_name == "SleepNumber ILE Test1 SleepNumber"
    assert hass.states.get(entry.entity_id).state == "40"

    entry = entity_registry.async_get("sensor.sleepnumber_ile_test2_sleepnumber")
    assert entry.original_name == "SleepNumber ILE Test2 SleepNumber"
    assert hass.states.get(entry.entity_id).state == "80"
