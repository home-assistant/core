"""Test the Anova sensors."""


from . import async_init_integration


async def test_sensors(hass):
    """Test setting up creates the sensors."""
    await async_init_integration(hass)
    assert len(hass.states.async_all("sensor")) == 9
    assert hass.states.get("sensor.cook_time_remaining").state == "0"
    assert hass.states.get("sensor.cook_time").state == "0"
    assert hass.states.get("sensor.firmware_version").state == "2.2.0"
    assert hass.states.get("sensor.heater_temperature").state == "20.87"
    assert hass.states.get("sensor.mode").state == "Low water"
    assert hass.states.get("sensor.state").state == "No state"
    assert hass.states.get("sensor.target_temperature").state == "23.33"
    assert hass.states.get("sensor.water_temperature").state == "21.33"
    assert hass.states.get("sensor.triac_temperature").state == "21.79"
