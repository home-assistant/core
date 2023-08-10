"""The tests for the Template Weather platform."""
import pytest

from homeassistant.components.weather import (
    ATTR_FORECAST,
    ATTR_WEATHER_APPARENT_TEMPERATURE,
    ATTR_WEATHER_CLOUD_COVERAGE,
    ATTR_WEATHER_DEW_POINT,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_GUST_SPEED,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECAST,
    Forecast,
)
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(("count", "domain"), [(1, WEATHER_DOMAIN)])
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
                    "wind_gust_speed_template": "{{ states('sensor.wind_gust_speed') }}",
                    "cloud_coverage_template": "{{ states('sensor.cloud_coverage') }}",
                    "dew_point_template": "{{ states('sensor.dew_point') }}",
                    "apparent_temperature_template": "{{ states('sensor.apparent_temperature') }}",
                },
            ]
        },
    ],
)
async def test_template_state_text(hass: HomeAssistant, start_ha) -> None:
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
        ("sensor.wind_gust_speed", ATTR_WEATHER_WIND_GUST_SPEED, 30),
        ("sensor.cloud_coverage", ATTR_WEATHER_CLOUD_COVERAGE, 75),
        ("sensor.dew_point", ATTR_WEATHER_DEW_POINT, 2.2),
        ("sensor.apparent_temperature", ATTR_WEATHER_APPARENT_TEMPERATURE, 25),
    ]:
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()
        state = hass.states.get("weather.test")
        assert state is not None
        assert state.state == "sunny"
        assert state.attributes.get(v_attr) == value


@pytest.mark.parametrize(("count", "domain"), [(1, WEATHER_DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "weather": [
                {
                    "platform": "template",
                    "name": "forecast",
                    "condition_template": "sunny",
                    "forecast_template": "{{ states.weather.forecast.attributes.forecast }}",
                    "forecast_daily_template": "{{ states.weather.forecast.attributes.forecast }}",
                    "forecast_hourly_template": "{{ states.weather.forecast.attributes.forecast }}",
                    "forecast_twice_daily_template": "{{ states.weather.forecast_twice_daily.attributes.forecast }}",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                },
            ]
        },
    ],
)
async def test_forecasts(hass: HomeAssistant, start_ha) -> None:
    """Test forecast service."""
    for attr, _v_attr, value in [
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
    ]:
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()

    hass.states.async_set(
        "weather.forecast",
        "sunny",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="cloudy",
                    datetime="2023-02-17T14:00:00+00:00",
                    temperature=14.2,
                )
            ]
        },
    )
    hass.states.async_set(
        "weather.forecast_twice_daily",
        "fog",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="fog",
                    datetime="2023-02-17T14:00:00+00:00",
                    temperature=14.2,
                    is_daytime=True,
                )
            ]
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("weather.forecast")
    assert state is not None
    assert state.state == "sunny"
    state2 = hass.states.get("weather.forecast_twice_daily")
    assert state2 is not None
    assert state2.state == "fog"

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {"entity_id": "weather.forecast", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert response == {
        "forecast": [
            {
                "condition": "cloudy",
                "datetime": "2023-02-17T14:00:00+00:00",
                "temperature": 14.2,
            }
        ]
    }
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {"entity_id": "weather.forecast", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    assert response == {
        "forecast": [
            {
                "condition": "cloudy",
                "datetime": "2023-02-17T14:00:00+00:00",
                "temperature": 14.2,
            }
        ]
    }
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {"entity_id": "weather.forecast", "type": "twice_daily"},
        blocking=True,
        return_response=True,
    )
    assert response == {
        "forecast": [
            {
                "condition": "fog",
                "datetime": "2023-02-17T14:00:00+00:00",
                "temperature": 14.2,
                "is_daytime": True,
            }
        ]
    }

    hass.states.async_set(
        "weather.forecast",
        "sunny",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="cloudy",
                    datetime="2023-02-17T14:00:00+00:00",
                    temperature=16.9,
                )
            ]
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("weather.forecast")
    assert state is not None
    assert state.state == "sunny"

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {"entity_id": "weather.forecast", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert response == {
        "forecast": [
            {
                "condition": "cloudy",
                "datetime": "2023-02-17T14:00:00+00:00",
                "temperature": 16.9,
            }
        ]
    }


@pytest.mark.parametrize(("count", "domain"), [(1, WEATHER_DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "weather": [
                {
                    "platform": "template",
                    "name": "forecast",
                    "condition_template": "sunny",
                    "forecast_template": "{{ states.weather.forecast.attributes.forecast }}",
                    "forecast_daily_template": "{{ states.weather.forecast.attributes.forecast }}",
                    "forecast_hourly_template": "{{ states.weather.forecast_hourly.attributes.forecast }}",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                },
            ]
        },
    ],
)
async def test_forecast_invalid(
    hass: HomeAssistant, start_ha, caplog: pytest.LogCaptureFixture
) -> None:
    """Test invalid forecasts."""
    for attr, _v_attr, value in [
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
    ]:
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()

    hass.states.async_set(
        "weather.forecast",
        "sunny",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="cloudy",
                    datetime="2023-02-17T14:00:00+00:00",
                    temperature=14.2,
                    not_correct=1,
                )
            ]
        },
    )
    hass.states.async_set(
        "weather.forecast_hourly",
        "sunny",
        {ATTR_FORECAST: None},
    )
    await hass.async_block_till_done()
    state = hass.states.get("weather.forecast_hourly")
    assert state is not None
    assert state.state == "sunny"

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {"entity_id": "weather.forecast", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert response == {"forecast": []}
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {"entity_id": "weather.forecast", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    assert response == {"forecast": []}
    assert "Only valid keys in Forecast are allowed" in caplog.text


@pytest.mark.parametrize(("count", "domain"), [(1, WEATHER_DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "weather": [
                {
                    "platform": "template",
                    "name": "forecast",
                    "condition_template": "sunny",
                    "forecast_template": "{{ states.weather.forecast.attributes.forecast }}",
                    "forecast_twice_daily_template": "{{ states.weather.forecast_twice_daily.attributes.forecast }}",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                },
            ]
        },
    ],
)
async def test_forecast_invalid_is_daytime_missing_in_twice_daily(
    hass: HomeAssistant, start_ha, caplog: pytest.LogCaptureFixture
) -> None:
    """Test forecast service invalid when is_daytime missing in twice_daily forecast."""
    for attr, _v_attr, value in [
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
    ]:
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()

    hass.states.async_set(
        "weather.forecast_twice_daily",
        "sunny",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="cloudy",
                    datetime="2023-02-17T14:00:00+00:00",
                    temperature=14.2,
                )
            ]
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("weather.forecast_twice_daily")
    assert state is not None
    assert state.state == "sunny"

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {"entity_id": "weather.forecast", "type": "twice_daily"},
        blocking=True,
        return_response=True,
    )
    assert response == {"forecast": []}
    assert "`is_daytime` is missing in twice_daily forecast" in caplog.text


@pytest.mark.parametrize(("count", "domain"), [(1, WEATHER_DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "weather": [
                {
                    "platform": "template",
                    "name": "forecast",
                    "condition_template": "sunny",
                    "forecast_template": "{{ states.weather.forecast.attributes.forecast }}",
                    "forecast_twice_daily_template": "{{ states.weather.forecast_twice_daily.attributes.forecast }}",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                },
            ]
        },
    ],
)
async def test_forecast_invalid_datetime_missing(
    hass: HomeAssistant, start_ha, caplog: pytest.LogCaptureFixture
) -> None:
    """Test forecast service invalid when datetime missing."""
    for attr, _v_attr, value in [
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
    ]:
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()

    hass.states.async_set(
        "weather.forecast_twice_daily",
        "sunny",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="cloudy",
                    temperature=14.2,
                    is_daytime=True,
                )
            ]
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("weather.forecast_twice_daily")
    assert state is not None
    assert state.state == "sunny"

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {"entity_id": "weather.forecast", "type": "twice_daily"},
        blocking=True,
        return_response=True,
    )
    assert response == {"forecast": []}
    assert "`datetime` is required in forecasts" in caplog.text
