"""The tests for the Template Weather platform."""
import pytest

from homeassistant.components.weather import (
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN,
)
from homeassistant.const import ATTR_ATTRIBUTION, STATE_UNKNOWN

from .helpers import template_restore_state_test


@pytest.mark.parametrize("count,domain", [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
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
    ],
)
async def test_template_state_text(hass, start_ha):
    """Test the state text of a template."""
    for attr, v_attr, value in [
        (
            "sensor.attribution",
            ATTR_ATTRIBUTION,
            "The custom attribution",
        ),
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
        ("sensor.pressure", ATTR_WEATHER_PRESSURE, 1000),
        ("sensor.windspeed", ATTR_WEATHER_WIND_SPEED, 20),
        ("sensor.windbearing", ATTR_WEATHER_WIND_BEARING, 180),
        ("sensor.ozone", ATTR_WEATHER_OZONE, 25),
        ("sensor.visibility", ATTR_WEATHER_VISIBILITY, 4.6),
    ]:
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()
        state = hass.states.get("weather.test")
        assert state is not None
        assert state.state == "sunny"
        assert state.attributes.get(v_attr) == value


@pytest.mark.parametrize("count,domain,platform", [(1, "weather", "weather")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "weather": {
                "platform": "template",
                "name": "restore",
                "unique_id": "restore",
                "attribution_template": "{{ states('sensor.test_state')|int(0) }}",
                "condition_template": f"{{{{ iif(is_state('sensor.test_state','10'),'{ATTR_CONDITION_SUNNY}','{ATTR_CONDITION_RAINY}') }}}}",
                "forecast_template": "{{ [{'temperature': states('sensor.test_state')|int(0) }] }}",
                "temperature_template": "{{ states('sensor.test_state')|int(0) }}",
                "humidity_template": "{{ states('sensor.test_state')|int(0) }}",
                "pressure_template": "{{ states('sensor.test_state')|int(0) }}",
                "wind_speed_template": "{{ states('sensor.test_state')|int(0) }}",
                "wind_bearing_template": "{{ states('sensor.test_state')|int(0) }}",
                "ozone_template": "{{ states('sensor.test_state')|int(0) }}",
                "visibility_template": "{{ states('sensor.test_state')|int(0) }}",
            },
        },
    ],
)
@pytest.mark.parametrize(
    "extra_config, restored_state, initial_state, initial_attributes, stored_attributes",
    [
        (
            {"restore": False},
            10,
            STATE_UNKNOWN,
            {
                "attribution": "Powered by Home Assistant",
                "condition": None,
                "forecast": [],
                "temperature": None,
                "humidity": None,
                "pressure": None,
                "wind_speed": None,
                "wind_bearing": None,
                "ozone": None,
                "visibility": None,
            },
            {},
        ),
        (
            {"restore": True},
            10,
            ATTR_CONDITION_SUNNY,
            {
                "attribution": 10,
                "forecast": [{"temperature": 10}],
                "temperature": 10,
                "humidity": 10,
                "pressure": 10,
                "wind_speed": 10,
                "wind_bearing": 10,
                "ozone": 10,
                "visibility": 10,
            },
            {
                "_condition": ATTR_CONDITION_SUNNY,
            },
        ),
    ],
)
async def test_template_restore_state(
    hass,
    count,
    domain,
    platform,
    config,
    extra_config,
    restored_state,
    initial_state,
    initial_attributes,
    stored_attributes,
):
    """Test restoring weather template."""

    config = dict(config)
    config[domain].update(**extra_config)

    await template_restore_state_test(
        hass,
        count,
        domain,
        config,
        restored_state,
        initial_state,
        initial_attributes,
        stored_attributes,
        platform,
        "restore",
    )
