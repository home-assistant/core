"""Test Environment Canada diagnostics."""
from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.environment_canada.const import (
    CONF_LANGUAGE,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

FIXTURE_USER_INPUT = {
    CONF_LATITUDE: 55.55,
    CONF_LONGITUDE: 42.42,
    CONF_STATION: "XX/1234567",
    CONF_LANGUAGE: "Gibberish",
}


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Environment Canada integration in Home Assistant."""

    def mock_ec():
        ec_mock = MagicMock()
        ec_mock.station_id = FIXTURE_USER_INPUT[CONF_STATION]
        ec_mock.lat = FIXTURE_USER_INPUT[CONF_LATITUDE]
        ec_mock.lon = FIXTURE_USER_INPUT[CONF_LONGITUDE]
        ec_mock.language = FIXTURE_USER_INPUT[CONF_LANGUAGE]
        ec_mock.update = AsyncMock()
        return ec_mock

    config_entry = MockConfigEntry(domain=DOMAIN, data=FIXTURE_USER_INPUT)
    config_entry.add_to_hass(hass)

    ec_data = json.loads(
        load_fixture("environment_canada/current_conditions_data.json")
    )

    weather_mock = mock_ec()
    ec_data["metadata"]["timestamp"] = datetime(2022, 10, 4, tzinfo=timezone.utc)
    weather_mock.conditions = ec_data["conditions"]
    weather_mock.alerts = ec_data["alerts"]
    weather_mock.daily_forecasts = ec_data["daily_forecasts"]
    weather_mock.metadata = ec_data["metadata"]

    radar_mock = mock_ec()
    radar_mock.image = b"GIF..."
    radar_mock.timestamp = datetime(2022, 10, 4, tzinfo=timezone.utc)

    with patch(
        "homeassistant.components.environment_canada.ECWeather",
        return_value=weather_mock,
    ), patch(
        "homeassistant.components.environment_canada.ECAirQuality",
        return_value=mock_ec(),
    ), patch(
        "homeassistant.components.environment_canada.ECRadar", return_value=radar_mock
    ), patch(
        "homeassistant.components.environment_canada.config_flow.ECWeather",
        return_value=weather_mock,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test config entry diagnostics."""

    config_entry = await init_integration(hass)
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    redacted_entry = json.loads(
        load_fixture("environment_canada/config_entry_data.json")
    )

    assert diagnostics == redacted_entry
