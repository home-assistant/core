"""Test the Litter-Robot sensor entity."""
from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import PERCENTAGE

from .conftest import setup_integration

ENTITY_ID = "sensor.test_waste_drawer"


async def test_sensor(hass, mock_account):
    """Tests the sensor entity was set up."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    sensor = hass.states.get(ENTITY_ID)
    assert sensor
    assert sensor.state == "50"
    assert sensor.attributes["cycle_count"] == 15
    assert sensor.attributes["cycle_capacity"] == 30
    assert sensor.attributes["cycles_after_drawer_full"] == 0
    assert sensor.attributes["unit_of_measurement"] == PERCENTAGE
