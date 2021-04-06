"""The tests for the Template Weather platform."""
from pytest import approx

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
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM, UnitSystem


async def test_template_state_text_metric(hass):
    """Test the state text of a template with metric unit system."""
    await _test_template_state_text(hass, METRIC_SYSTEM)


async def test_template_state_text_imperial(hass):
    """Test the state text of a template with imperial unit system."""
    await _test_template_state_text(hass, IMPERIAL_SYSTEM)


async def _test_template_state_text(hass, unit_system: UnitSystem):
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

    hass.config.units = unit_system
    await hass.async_block_till_done()

    hass.states.async_set("sensor.attribution", "The custom attribution")
    await hass.async_block_till_done()
    # all temperature sensors are automatically converted into hass.config.units.temperature
    # therefore, value will be interpreted as-is
    hass.states.async_set("sensor.temperature", 22.3)  # in °C or °F
    await hass.async_block_till_done()
    hass.states.async_set("sensor.humidity", 60)  # in %
    await hass.async_block_till_done()
    hass.states.async_set("sensor.pressure", 1002.3)  # in hPa
    await hass.async_block_till_done()
    hass.states.async_set("sensor.windspeed", 10)  # in km/h
    await hass.async_block_till_done()
    hass.states.async_set("sensor.windbearing", 180)  # in °
    await hass.async_block_till_done()
    hass.states.async_set("sensor.ozone", 25)  # in ppm
    await hass.async_block_till_done()
    hass.states.async_set("sensor.visibility", 4.6)  # in km
    await hass.async_block_till_done()

    state = hass.states.get("weather.test")
    assert state is not None

    assert state.state == "sunny"

    data = state.attributes
    assert data.get(ATTR_WEATHER_ATTRIBUTION) == "The custom attribution"
    assert data.get(ATTR_WEATHER_HUMIDITY) == 60  # in %
    assert data.get(ATTR_WEATHER_WIND_BEARING) == 180  # in °
    assert data.get(ATTR_WEATHER_OZONE) == 25  # in ppm

    if unit_system is METRIC_SYSTEM:
        assert data.get(ATTR_WEATHER_TEMPERATURE) == approx(22.3)  # in °C
        assert data.get(ATTR_WEATHER_PRESSURE) == approx(1002.3)  # in hpa
        assert data.get(ATTR_WEATHER_WIND_SPEED) == approx(10)  # in km/h
        assert data.get(ATTR_WEATHER_VISIBILITY) == approx(4.6)  # in km
    else:
        assert data.get(ATTR_WEATHER_TEMPERATURE) == approx(22)  # in °F (rounded)
        assert data.get(ATTR_WEATHER_PRESSURE) == approx(29.597899)  # in inhg
        assert data.get(ATTR_WEATHER_WIND_SPEED) == approx(6.21371)  # in mph
        assert data.get(ATTR_WEATHER_VISIBILITY) == approx(2.858306)  # in mi


async def test_template_state_text_empty_sensor_values(hass):
    """Test the state text of a template if sensors report empty values."""
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

    hass.states.async_set("sensor.pressure", "")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.windspeed", "")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.visibility", "")
    await hass.async_block_till_done()

    state = hass.states.get("weather.test")
    assert state is not None

    data = state.attributes
    assert data.get(ATTR_WEATHER_PRESSURE) is None
    assert data.get(ATTR_WEATHER_WIND_SPEED) is None
    assert data.get(ATTR_WEATHER_VISIBILITY) is None
