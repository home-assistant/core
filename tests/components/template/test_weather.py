"""The tests for the Template Weather platform."""
from homeassistant.components.weather import (
    ATTR_WEATHER_ATTRIBUTION,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN,
)
from homeassistant.setup import async_setup_component


async def test_template_state_text(hass):
    """Test the state text of a template."""
    await async_setup_component(
        hass,
        DOMAIN,
        {
            "weather": [
                {"weather": {"platform": "demo"}},
                {
                    "platform": "template",
                    "name": "test",
                    "attribution_template": "{{ states('sensor.attribution') }}",
                    "condition_template": "sunny",
                    "forecast_template": "{{ states.weather.demo.attributes.forecast }}",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                    "pressure_template": "{{ states('sensor.pressure') }}",
                    "wind_speed_template": "{{ states('sensor.windspeed') }}",
                    "wind_bearing_template": "{{ states('sensor.windbearing') }}",
                    "ozone_template": "{{ states('sensor.ozone') }}",
                    "visibility_template": "{{ states('sensor.visibility') }}",
                },
            ]
        },
    )
    await hass.async_block_till_done()

    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("sensor.attribution", "The custom attribution")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.temperature", 22.3)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.humidity", 60)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.pressure", 1000)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.windspeed", 20)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.windbearing", 180)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.ozone", 25)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.visibility", 4.6)
    await hass.async_block_till_done()

    state = hass.states.get("weather.test")
    assert state is not None

    assert state.state == "sunny"

    data = state.attributes
    assert data.get(ATTR_WEATHER_ATTRIBUTION) == "The custom attribution"
    assert data.get(ATTR_WEATHER_TEMPERATURE) == 22.3
    assert data.get(ATTR_WEATHER_HUMIDITY) == 60
    assert data.get(ATTR_WEATHER_PRESSURE) == 1000
    assert data.get(ATTR_WEATHER_WIND_SPEED) == 20
    assert data.get(ATTR_WEATHER_WIND_BEARING) == 180
    assert data.get(ATTR_WEATHER_OZONE) == 25
    assert data.get(ATTR_WEATHER_VISIBILITY) == 4.6
