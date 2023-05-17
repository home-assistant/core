"""Test weather of AccuWeather integration."""
from datetime import timedelta
from unittest.mock import PropertyMock, patch

from homeassistant.components.accuweather.const import ATTRIBUTION
from homeassistant.components.weather import (
    ATTR_FORECAST,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import init_integration

from tests.common import (
    async_fire_time_changed,
    load_json_array_fixture,
    load_json_object_fixture,
)


async def test_weather_without_forecast(hass: HomeAssistant) -> None:
    """Test states of the weather without forecast."""
    await init_integration(hass)
    registry = er.async_get(hass)

    state = hass.states.get("weather.home")
    assert state
    assert state.state == "sunny"
    assert not state.attributes.get(ATTR_FORECAST)
    assert state.attributes.get(ATTR_WEATHER_HUMIDITY) == 67
    assert state.attributes.get(ATTR_WEATHER_PRESSURE) == 1012.0
    assert state.attributes.get(ATTR_WEATHER_TEMPERATURE) == 22.6
    assert state.attributes.get(ATTR_WEATHER_VISIBILITY) == 16.1
    assert state.attributes.get(ATTR_WEATHER_WIND_BEARING) == 180
    assert state.attributes.get(ATTR_WEATHER_WIND_SPEED) == 14.5  # 4.03 m/s -> km/h
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION

    entry = registry.async_get("weather.home")
    assert entry
    assert entry.unique_id == "0123456"


async def test_weather_with_forecast(hass: HomeAssistant) -> None:
    """Test states of the weather with forecast."""
    await init_integration(hass, forecast=True)
    registry = er.async_get(hass)

    state = hass.states.get("weather.home")
    assert state
    assert state.state == "sunny"
    assert state.attributes.get(ATTR_WEATHER_HUMIDITY) == 67
    assert state.attributes.get(ATTR_WEATHER_PRESSURE) == 1012.0
    assert state.attributes.get(ATTR_WEATHER_TEMPERATURE) == 22.6
    assert state.attributes.get(ATTR_WEATHER_VISIBILITY) == 16.1
    assert state.attributes.get(ATTR_WEATHER_WIND_BEARING) == 180
    assert state.attributes.get(ATTR_WEATHER_WIND_SPEED) == 14.5  # 4.03 m/s -> km/h
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    forecast = state.attributes.get(ATTR_FORECAST)[0]
    assert forecast.get(ATTR_FORECAST_CONDITION) == "lightning-rainy"
    assert forecast.get(ATTR_FORECAST_PRECIPITATION) == 4.8
    assert forecast.get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) == 58
    assert forecast.get(ATTR_FORECAST_TEMP) == 29.5
    assert forecast.get(ATTR_FORECAST_TEMP_LOW) == 15.4
    assert forecast.get(ATTR_FORECAST_TIME) == "2020-07-26T05:00:00+00:00"
    assert forecast.get(ATTR_FORECAST_WIND_BEARING) == 166
    assert forecast.get(ATTR_FORECAST_WIND_SPEED) == 13.0  # 3.61 m/s -> km/h

    entry = registry.async_get("weather.home")
    assert entry
    assert entry.unique_id == "0123456"


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    await init_integration(hass)

    state = hass.states.get("weather.home")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "sunny"

    future = utcnow() + timedelta(minutes=60)
    with patch(
        "homeassistant.components.accuweather.AccuWeather._async_get_data",
        side_effect=ConnectionError(),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("weather.home")
        assert state
        assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=120)
    with patch(
        "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
        return_value=load_json_object_fixture(
            "accuweather/current_conditions_data.json"
        ),
    ), patch(
        "homeassistant.components.accuweather.AccuWeather.requests_remaining",
        new_callable=PropertyMock,
        return_value=10,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("weather.home")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "sunny"


async def test_manual_update_entity(hass: HomeAssistant) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await init_integration(hass, forecast=True)

    await async_setup_component(hass, "homeassistant", {})

    current = load_json_object_fixture("accuweather/current_conditions_data.json")
    forecast = load_json_array_fixture("accuweather/forecast_data.json")

    with patch(
        "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
        return_value=current,
    ) as mock_current, patch(
        "homeassistant.components.accuweather.AccuWeather.async_get_forecast",
        return_value=forecast,
    ) as mock_forecast, patch(
        "homeassistant.components.accuweather.AccuWeather.requests_remaining",
        new_callable=PropertyMock,
        return_value=10,
    ):
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["weather.home"]},
            blocking=True,
        )
    assert mock_current.call_count == 1
    assert mock_forecast.call_count == 1


async def test_unsupported_condition_icon_data(hass: HomeAssistant) -> None:
    """Test with unsupported condition icon data."""
    await init_integration(hass, forecast=True, unsupported_icon=True)

    state = hass.states.get("weather.home")
    assert state.attributes.get(ATTR_FORECAST_CONDITION) is None
