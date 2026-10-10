"""Tests for the Environment Canada integration."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.environment_canada.const import CONF_STATION, DOMAIN
from homeassistant.const import CONF_LANGUAGE, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_LATITUDE: 55.55,
    CONF_LONGITUDE: 42.42,
    CONF_STATION: "XX/1234567",
    CONF_LANGUAGE: "Gibberish",
}


def build_mocks(ec_data) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Build the weather, AQHI and radar library mocks used during setup."""

    def mock_ec() -> MagicMock:
        ec_mock = MagicMock()
        ec_mock.station_id = FIXTURE_USER_INPUT[CONF_STATION]
        ec_mock.lat = FIXTURE_USER_INPUT[CONF_LATITUDE]
        ec_mock.lon = FIXTURE_USER_INPUT[CONF_LONGITUDE]
        ec_mock.language = FIXTURE_USER_INPUT[CONF_LANGUAGE]
        ec_mock.update = AsyncMock()
        return ec_mock

    weather_mock = mock_ec()
    ec_data["metadata"].timestamp = datetime(2022, 10, 4, tzinfo=UTC)
    weather_mock.conditions = ec_data["conditions"]
    weather_mock.alerts = ec_data["alerts"]
    weather_mock.daily_forecasts = ec_data["daily_forecasts"]
    weather_mock.hourly_forecasts = ec_data["hourly_forecasts"]
    weather_mock.metadata = ec_data["metadata"]

    radar_mock = mock_ec()
    radar_mock.image = b"GIF..."
    radar_mock.timestamp = datetime(2022, 10, 4, tzinfo=UTC)
    radar_mock.layer = "precip_type"
    radar_mock.metadata = {"attribution": "Data provided by Environment Canada"}
    radar_mock.clear_cache = MagicMock()

    return weather_mock, mock_ec(), radar_mock


async def init_integration(
    hass: HomeAssistant,
    ec_data,
    options: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Set up the Environment Canada integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=FIXTURE_USER_INPUT, title="Home", options=options or {}
    )
    config_entry.add_to_hass(hass)

    weather_mock, aqhi_mock, radar_mock = build_mocks(ec_data)

    with (
        patch(
            "homeassistant.components.environment_canada.ECWeather",
            return_value=weather_mock,
        ),
        patch(
            "homeassistant.components.environment_canada.ECAirQuality",
            return_value=aqhi_mock,
        ),
        patch(
            "homeassistant.components.environment_canada.ECMap",
            return_value=radar_mock,
        ),
        patch(
            "homeassistant.components.environment_canada.config_flow.ECWeather",
            return_value=weather_mock,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
