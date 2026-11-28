"""The tests for the buienradar weather component."""

from http import HTTPStatus
import json

from buienradar.urls import JSON_FEED_URL, json_precipitation_forecast_url
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_load_fixture,
    async_load_json_object_fixture,
)
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_SUNNY,
    DOMAIN as WEATHER_DOMAIN,
    WeatherService,
    WeatherServiceArgument,
)
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant

from . import TEST_CFG_DATA, TEST_LATITUDE, TEST_LONGITUDE, setup_integration

WEATHER_ENTITY = "weather.buienradar"


async def test_smoke_test_setup_component(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Smoke test for successfully set-up with default config."""
    aioclient_mock.get(
        "https://data.buienradar.nl/2.0/feed/json", status=HTTPStatus.NOT_FOUND
    )
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state.state == "unknown"


@pytest.mark.usefixtures("mock_buienradar_feeds")
async def test_weather(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the weather entity state."""
    await setup_integration(hass)

    assert hass.states.get(WEATHER_ENTITY) == snapshot


@pytest.mark.parametrize(
    ("icon", "expected_condition"),
    [
        ("a.png", ATTR_CONDITION_SUNNY),
        ("aa.png", ATTR_CONDITION_CLEAR_NIGHT),
        ("cc.png", ATTR_CONDITION_CLOUDY),
    ],
)
async def test_condition_day_and_night(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    icon: str,
    expected_condition: str,
) -> None:
    """Test a clear sky is only reported as sunny during the day."""
    feed = await async_load_json_object_fixture(hass, "feed.json", DOMAIN)
    for station in feed["actual"]["stationmeasurements"]:
        station["iconurl"] = (
            f"https://www.buienradar.nl/resources/images/icons/weather/30x30/{icon}"
        )
    aioclient_mock.get(JSON_FEED_URL, text=json.dumps(feed))
    aioclient_mock.get(
        json_precipitation_forecast_url(TEST_LATITUDE, TEST_LONGITUDE),
        text=await async_load_fixture(hass, "rain.txt", DOMAIN),
    )

    await setup_integration(hass)

    assert hass.states.get(WEATHER_ENTITY).state == expected_condition


@pytest.mark.usefixtures("mock_buienradar_feeds")
async def test_forecast(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the daily forecast."""
    await setup_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        WeatherService.GET_FORECASTS,
        {TargetKey.ENTITY_ID: WEATHER_ENTITY, WeatherServiceArgument.TYPE: "daily"},
        blocking=True,
        return_response=True,
    )

    assert response == snapshot
