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


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the WeatherKit integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="0123456",
        data={
            CONF_LATITUDE: 35.4690101707532,
            CONF_LONGITUDE: 135.74817234593166,
            CONF_KEY_ID: "QABCDEFG123",
            CONF_SERVICE_ID: "io.home-assistant.testing",
            CONF_TEAM_ID: "ABCD123456",
            CONF_KEY_PEM: "-----BEGIN PRIVATE KEY-----\nwhateverkey\n-----END PRIVATE KEY-----",
        },
        pref_disable_polling=True,
    )

    weather_response = load_json_object_fixture("weatherkit/weather_response.json")

    with patch(
        "apple_weatherkit.client.WeatherKitApiClient.get_weather_data",
        return_value=weather_response,
    ), patch(
        "apple_weatherkit.client.WeatherKitApiClient.get_availability",
        return_value=[
            DataSetType.CURRENT_WEATHER,
            DataSetType.DAILY_FORECAST,
            DataSetType.HOURLY_FORECAST,
        ],
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
