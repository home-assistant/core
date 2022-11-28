"""Test for the smhi weather entity."""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from smhi.smhi_lib import APIURL_TEMPLATE, SmhiForecast, SmhiForecastException

from homeassistant.components.smhi.const import (
    ATTR_SMHI_CLOUDINESS,
    ATTR_SMHI_THUNDER_PROBABILITY,
    ATTR_SMHI_WIND_GUST_SPEED,
)
from homeassistant.components.smhi.weather import CONDITION_CLASSES, RETRY_TIMEOUT
from homeassistant.components.weather import (
    ATTR_FORECAST,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRESSURE,
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
    ATTR_WEATHER_WIND_SPEED_UNIT,
    DOMAIN as WEATHER_DOMAIN,
)
from homeassistant.const import ATTR_ATTRIBUTION, SPEED_METERS_PER_SECOND, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import ENTITY_ID, TEST_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_hass(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test for successfully setting up the smhi integration."""
    uri = APIURL_TEMPLATE.format(
        TEST_CONFIG["location"]["longitude"], TEST_CONFIG["location"]["latitude"]
    )
    aioclient_mock.get(uri, text=api_response)

    entry = MockConfigEntry(domain="smhi", data=TEST_CONFIG, version=2)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1

    #  Testing the actual entity state for
    #  deeper testing than normal unity test
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.state == "sunny"
    assert state.attributes[ATTR_SMHI_CLOUDINESS] == 50
    assert state.attributes[ATTR_SMHI_THUNDER_PROBABILITY] == 33
    assert state.attributes[ATTR_SMHI_WIND_GUST_SPEED] == 16.92
    assert state.attributes[ATTR_ATTRIBUTION].find("SMHI") >= 0
    assert state.attributes[ATTR_WEATHER_HUMIDITY] == 55
    assert state.attributes[ATTR_WEATHER_PRESSURE] == 1024
    assert state.attributes[ATTR_WEATHER_TEMPERATURE] == 17
    assert state.attributes[ATTR_WEATHER_VISIBILITY] == 50
    assert state.attributes[ATTR_WEATHER_WIND_SPEED] == 6.84
    assert state.attributes[ATTR_WEATHER_WIND_BEARING] == 134
    assert len(state.attributes["forecast"]) == 4

    forecast = state.attributes["forecast"][1]
    assert forecast[ATTR_FORECAST_TIME] == "2018-09-02T12:00:00"
    assert forecast[ATTR_FORECAST_TEMP] == 21
    assert forecast[ATTR_FORECAST_TEMP_LOW] == 6
    assert forecast[ATTR_FORECAST_PRECIPITATION] == 0
    assert forecast[ATTR_FORECAST_CONDITION] == "partlycloudy"
    assert forecast[ATTR_FORECAST_PRESSURE] == 1026
    assert forecast[ATTR_FORECAST_WIND_BEARING] == 203
    assert forecast[ATTR_FORECAST_WIND_SPEED] == 6.12


async def test_properties_no_data(hass: HomeAssistant) -> None:
    """Test properties when no API data available."""
    entry = MockConfigEntry(domain="smhi", data=TEST_CONFIG, version=2)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.smhi.weather.Smhi.async_get_forecast",
        side_effect=SmhiForecastException("boom"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.name == "test"
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_ATTRIBUTION] == "Swedish weather institute (SMHI)"
    assert ATTR_WEATHER_HUMIDITY not in state.attributes
    assert ATTR_WEATHER_PRESSURE not in state.attributes
    assert ATTR_WEATHER_TEMPERATURE not in state.attributes
    assert ATTR_WEATHER_VISIBILITY not in state.attributes
    assert ATTR_WEATHER_WIND_SPEED not in state.attributes
    assert ATTR_WEATHER_WIND_BEARING not in state.attributes
    assert ATTR_FORECAST not in state.attributes
    assert ATTR_SMHI_CLOUDINESS not in state.attributes
    assert ATTR_SMHI_THUNDER_PROBABILITY not in state.attributes
    assert ATTR_SMHI_WIND_GUST_SPEED not in state.attributes


async def test_properties_unknown_symbol(hass: HomeAssistant) -> None:
    """Test behaviour when unknown symbol from API."""
    data = SmhiForecast(
        temperature=5,
        temperature_max=10,
        temperature_min=0,
        humidity=5,
        pressure=1008,
        thunder=0,
        cloudiness=52,
        precipitation=1,
        wind_direction=180,
        wind_speed=10,
        horizontal_visibility=6,
        wind_gust=1.5,
        mean_precipitation=0.5,
        total_precipitation=1,
        symbol=100,  # Faulty symbol
        valid_time=datetime(2018, 1, 1, 0, 1, 2),
    )

    data2 = SmhiForecast(
        temperature=5,
        temperature_max=10,
        temperature_min=0,
        humidity=5,
        pressure=1008,
        thunder=0,
        cloudiness=52,
        precipitation=1,
        wind_direction=180,
        wind_speed=10,
        horizontal_visibility=6,
        wind_gust=1.5,
        mean_precipitation=0.5,
        total_precipitation=1,
        symbol=100,  # Faulty symbol
        valid_time=datetime(2018, 1, 1, 12, 1, 2),
    )

    data3 = SmhiForecast(
        temperature=5,
        temperature_max=10,
        temperature_min=0,
        humidity=5,
        pressure=1008,
        thunder=0,
        cloudiness=52,
        precipitation=1,
        wind_direction=180,
        wind_speed=10,
        horizontal_visibility=6,
        wind_gust=1.5,
        mean_precipitation=0.5,
        total_precipitation=1,
        symbol=100,  # Faulty symbol
        valid_time=datetime(2018, 1, 2, 12, 1, 2),
    )

    testdata = [data, data2, data3]

    entry = MockConfigEntry(domain="smhi", data=TEST_CONFIG, version=2)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.smhi.weather.Smhi.async_get_forecast",
        return_value=testdata,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.name == "test"
    assert state.state == STATE_UNKNOWN
    assert ATTR_FORECAST in state.attributes
    assert all(
        forecast[ATTR_FORECAST_CONDITION] is None
        for forecast in state.attributes[ATTR_FORECAST]
    )


@pytest.mark.parametrize("error", [SmhiForecastException(), asyncio.TimeoutError()])
async def test_refresh_weather_forecast_retry(
    hass: HomeAssistant, error: Exception
) -> None:
    """Test the refresh weather forecast function."""
    entry = MockConfigEntry(domain="smhi", data=TEST_CONFIG, version=2)
    entry.add_to_hass(hass)
    now = utcnow()

    with patch(
        "homeassistant.components.smhi.weather.Smhi.async_get_forecast",
        side_effect=error,
    ) as mock_get_forecast:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)

        assert state
        assert state.name == "test"
        assert state.state == STATE_UNKNOWN
        assert mock_get_forecast.call_count == 1

        future = now + timedelta(seconds=RETRY_TIMEOUT + 1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state
        assert state.state == STATE_UNKNOWN
        assert mock_get_forecast.call_count == 2

        future = future + timedelta(seconds=RETRY_TIMEOUT + 1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state
        assert state.state == STATE_UNKNOWN
        assert mock_get_forecast.call_count == 3

        future = future + timedelta(seconds=RETRY_TIMEOUT + 1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state
        assert state.state == STATE_UNKNOWN
        # after three failed retries we stop retrying and go back to normal interval
        assert mock_get_forecast.call_count == 3


def test_condition_class():
    """Test condition class."""

    def get_condition(index: int) -> str:
        """Return condition given index."""
        return [k for k, v in CONDITION_CLASSES.items() if index in v][0]

    # SMHI definitions as follows, see
    # http://opendata.smhi.se/apidocs/metfcst/parameters.html

    # 1. Clear sky
    assert get_condition(1) == "sunny"
    # 2. Nearly clear sky
    assert get_condition(2) == "sunny"
    # 3. Variable cloudiness
    assert get_condition(3) == "partlycloudy"
    # 4. Halfclear sky
    assert get_condition(4) == "partlycloudy"
    # 5. Cloudy sky
    assert get_condition(5) == "cloudy"
    # 6. Overcast
    assert get_condition(6) == "cloudy"
    # 7. Fog
    assert get_condition(7) == "fog"
    # 8. Light rain showers
    assert get_condition(8) == "rainy"
    # 9. Moderate rain showers
    assert get_condition(9) == "rainy"
    # 18. Light rain
    assert get_condition(18) == "rainy"
    # 19. Moderate rain
    assert get_condition(19) == "rainy"
    # 10. Heavy rain showers
    assert get_condition(10) == "pouring"
    # 20. Heavy rain
    assert get_condition(20) == "pouring"
    # 21. Thunder
    assert get_condition(21) == "lightning"
    # 11. Thunderstorm
    assert get_condition(11) == "lightning-rainy"
    # 15. Light snow showers
    assert get_condition(15) == "snowy"
    # 16. Moderate snow showers
    assert get_condition(16) == "snowy"
    # 17. Heavy snow showers
    assert get_condition(17) == "snowy"
    # 25. Light snowfall
    assert get_condition(25) == "snowy"
    # 26. Moderate snowfall
    assert get_condition(26) == "snowy"
    # 27. Heavy snowfall
    assert get_condition(27) == "snowy"
    # 12. Light sleet showers
    assert get_condition(12) == "snowy-rainy"
    # 13. Moderate sleet showers
    assert get_condition(13) == "snowy-rainy"
    # 14. Heavy sleet showers
    assert get_condition(14) == "snowy-rainy"
    # 22. Light sleet
    assert get_condition(22) == "snowy-rainy"
    # 23. Moderate sleet
    assert get_condition(23) == "snowy-rainy"
    # 24. Heavy sleet
    assert get_condition(24) == "snowy-rainy"


async def test_custom_speed_unit(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test Wind Gust speed with custom unit."""
    uri = APIURL_TEMPLATE.format(
        TEST_CONFIG["location"]["longitude"], TEST_CONFIG["location"]["latitude"]
    )
    aioclient_mock.get(uri, text=api_response)

    entry = MockConfigEntry(domain="smhi", data=TEST_CONFIG, version=2)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.name == "test"
    assert state.attributes[ATTR_SMHI_WIND_GUST_SPEED] == 16.92

    entity_reg = er.async_get(hass)
    entity_reg.async_update_entity_options(
        state.entity_id,
        WEATHER_DOMAIN,
        {ATTR_WEATHER_WIND_SPEED_UNIT: SPEED_METERS_PER_SECOND},
    )

    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_SMHI_WIND_GUST_SPEED] == 4.7
