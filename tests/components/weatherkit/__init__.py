"""Tests for the Apple WeatherKit integration."""
from unittest.mock import patch

from apple_weatherkit import DataSetType

from homeassistant.components.weatherkit.const import (
    CONF_KEY_ID,
    CONF_KEY_PEM,
    CONF_SERVICE_ID,
    CONF_TEAM_ID,
    DOMAIN,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

EXAMPLE_CONFIG_DATA = {
    CONF_LATITUDE: 35.4690101707532,
    CONF_LONGITUDE: 135.74817234593166,
    CONF_KEY_ID: "QABCDEFG123",
    CONF_SERVICE_ID: "io.home-assistant.testing",
    CONF_TEAM_ID: "ABCD123456",
    CONF_KEY_PEM: "-----BEGIN PRIVATE KEY-----\nwhateverkey\n-----END PRIVATE KEY-----",
}


async def init_integration(
    hass: HomeAssistant,
    is_night_time: bool = False,
    has_hourly_forecast: bool = True,
    has_daily_forecast: bool = True,
) -> MockConfigEntry:
    """Set up the WeatherKit integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="0123456",
        data=EXAMPLE_CONFIG_DATA,
    )

    weather_response = load_json_object_fixture("weatherkit/weather_response.json")

    available_data_sets = [DataSetType.CURRENT_WEATHER]

    if is_night_time:
        weather_response["currentWeather"]["daylight"] = False
        weather_response["currentWeather"]["conditionCode"] = "Clear"

    if not has_daily_forecast:
        del weather_response["forecastDaily"]
    else:
        available_data_sets.append(DataSetType.DAILY_FORECAST)

    if not has_hourly_forecast:
        del weather_response["forecastHourly"]
    else:
        available_data_sets.append(DataSetType.HOURLY_FORECAST)

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_weather_data",
        return_value=weather_response,
    ), patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=available_data_sets,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
