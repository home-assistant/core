"""Test for the smhi weather entity."""
import asyncio
from datetime import datetime
import logging

from smhi.smhi_lib import APIURL_TEMPLATE, SmhiForecastException

from homeassistant.components.smhi import weather as weather_smhi
from homeassistant.components.smhi.const import ATTR_SMHI_CLOUDINESS
from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_WEATHER_ATTRIBUTION,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant

from tests.async_mock import AsyncMock, Mock, patch
from tests.common import MockConfigEntry, load_fixture

_LOGGER = logging.getLogger(__name__)

TEST_CONFIG = {"name": "test", "longitude": "17.84197", "latitude": "59.32624"}


async def test_setup_hass(hass: HomeAssistant, aioclient_mock) -> None:
    """Test for successfully setting up the smhi platform.

    This test are deeper integrated with the core. Since only
    config_flow is used the component are setup with
    "async_forward_entry_setup". The actual result are tested
    with the entity state rather than "per function" unity tests
    """
    uri = APIURL_TEMPLATE.format(TEST_CONFIG["longitude"], TEST_CONFIG["latitude"])
    api_response = load_fixture("smhi.json")
    aioclient_mock.get(uri, text=api_response)

    entry = MockConfigEntry(domain="smhi", data=TEST_CONFIG)

    await hass.config_entries.async_forward_entry_setup(entry, WEATHER_DOMAIN)
    assert aioclient_mock.call_count == 1

    #  Testing the actual entity state for
    #  deeper testing than normal unity test
    state = hass.states.get("weather.smhi_test")

    assert state.state == "sunny"
    assert state.attributes[ATTR_SMHI_CLOUDINESS] == 50
    assert state.attributes[ATTR_WEATHER_ATTRIBUTION].find("SMHI") >= 0
    assert state.attributes[ATTR_WEATHER_HUMIDITY] == 55
    assert state.attributes[ATTR_WEATHER_PRESSURE] == 1024
    assert state.attributes[ATTR_WEATHER_TEMPERATURE] == 17
    assert state.attributes[ATTR_WEATHER_VISIBILITY] == 50
    assert state.attributes[ATTR_WEATHER_WIND_SPEED] == 7
    assert state.attributes[ATTR_WEATHER_WIND_BEARING] == 134
    _LOGGER.error(state.attributes)
    assert len(state.attributes["forecast"]) == 4

    forecast = state.attributes["forecast"][1]
    assert forecast[ATTR_FORECAST_TIME] == "2018-09-02T12:00:00"
    assert forecast[ATTR_FORECAST_TEMP] == 21
    assert forecast[ATTR_FORECAST_TEMP_LOW] == 6
    assert forecast[ATTR_FORECAST_PRECIPITATION] == 0
    assert forecast[ATTR_FORECAST_CONDITION] == "partlycloudy"


def test_properties_no_data(hass: HomeAssistant) -> None:
    """Test properties when no API data available."""
    weather = weather_smhi.SmhiWeather("name", "10", "10")
    weather.hass = hass

    assert weather.name == "name"
    assert weather.should_poll is True
    assert weather.temperature is None
    assert weather.humidity is None
    assert weather.wind_speed is None
    assert weather.wind_bearing is None
    assert weather.visibility is None
    assert weather.pressure is None
    assert weather.cloudiness is None
    assert weather.condition is None
    assert weather.forecast is None
    assert weather.temperature_unit == TEMP_CELSIUS


# pylint: disable=protected-access
def test_properties_unknown_symbol() -> None:
    """Test behaviour when unknown symbol from API."""
    hass = Mock()
    data = Mock()
    data.temperature = 5
    data.mean_precipitation = 0.5
    data.total_precipitation = 1
    data.humidity = 5
    data.wind_speed = 10
    data.wind_direction = 180
    data.horizontal_visibility = 6
    data.pressure = 1008
    data.cloudiness = 52
    data.symbol = 100  # Faulty symbol
    data.valid_time = datetime(2018, 1, 1, 0, 1, 2)

    data2 = Mock()
    data2.temperature = 5
    data2.mean_precipitation = 0.5
    data2.total_precipitation = 1
    data2.humidity = 5
    data2.wind_speed = 10
    data2.wind_direction = 180
    data2.horizontal_visibility = 6
    data2.pressure = 1008
    data2.cloudiness = 52
    data2.symbol = 100  # Faulty symbol
    data2.valid_time = datetime(2018, 1, 1, 12, 1, 2)

    data3 = Mock()
    data3.temperature = 5
    data3.mean_precipitation = 0.5
    data3.total_precipitation = 1
    data3.humidity = 5
    data3.wind_speed = 10
    data3.wind_direction = 180
    data3.horizontal_visibility = 6
    data3.pressure = 1008
    data3.cloudiness = 52
    data3.symbol = 100  # Faulty symbol
    data3.valid_time = datetime(2018, 1, 2, 12, 1, 2)

    testdata = [data, data2, data3]

    weather = weather_smhi.SmhiWeather("name", "10", "10")
    weather.hass = hass
    weather._forecasts = testdata
    assert weather.condition is None
    forecast = weather.forecast[0]
    assert forecast[ATTR_FORECAST_CONDITION] is None


# pylint: disable=protected-access
async def test_refresh_weather_forecast_exceeds_retries(hass) -> None:
    """Test the refresh weather forecast function."""

    with patch.object(
        hass.helpers.event, "async_call_later"
    ) as call_later, patch.object(
        weather_smhi.SmhiWeather,
        "get_weather_forecast",
        side_effect=SmhiForecastException(),
    ):

        weather = weather_smhi.SmhiWeather("name", "17.0022", "62.0022")
        weather.hass = hass
        weather._fail_count = 2

        await weather.async_update()
        assert weather._forecasts is None
        assert not call_later.mock_calls


async def test_refresh_weather_forecast_timeout(hass) -> None:
    """Test timeout exception."""
    weather = weather_smhi.SmhiWeather("name", "17.0022", "62.0022")
    weather.hass = hass

    with patch.object(
        hass.helpers.event, "async_call_later"
    ) as call_later, patch.object(
        weather_smhi.SmhiWeather, "retry_update"
    ), patch.object(
        weather_smhi.SmhiWeather,
        "get_weather_forecast",
        side_effect=asyncio.TimeoutError,
    ):

        await weather.async_update()
        assert len(call_later.mock_calls) == 1
        # Assert we are going to wait RETRY_TIMEOUT seconds
        assert call_later.mock_calls[0][1][0] == weather_smhi.RETRY_TIMEOUT


async def test_refresh_weather_forecast_exception() -> None:
    """Test any exception."""

    hass = Mock()
    weather = weather_smhi.SmhiWeather("name", "17.0022", "62.0022")
    weather.hass = hass

    with patch.object(
        hass.helpers.event, "async_call_later"
    ) as call_later, patch.object(
        weather, "get_weather_forecast", side_effect=SmhiForecastException(),
    ):
        await weather.async_update()
        assert len(call_later.mock_calls) == 1
        # Assert we are going to wait RETRY_TIMEOUT seconds
        assert call_later.mock_calls[0][1][0] == weather_smhi.RETRY_TIMEOUT


async def test_retry_update():
    """Test retry function of refresh forecast."""
    hass = Mock()
    weather = weather_smhi.SmhiWeather("name", "17.0022", "62.0022")
    weather.hass = hass

    with patch.object(weather, "async_update", AsyncMock()) as update:
        await weather.retry_update(None)
        assert len(update.mock_calls) == 1


def test_condition_class():
    """Test condition class."""

    def get_condition(index: int) -> str:
        """Return condition given index."""
        return [k for k, v in weather_smhi.CONDITION_CLASSES.items() if index in v][0]

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
