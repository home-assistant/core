"""The tests for the buienradar weather component."""

from datetime import timedelta
import json
from unittest.mock import patch

from buienradar.constants import MESSAGE, SUCCESS
from buienradar.urls import JSON_FEED_URL, json_precipitation_forecast_url
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    async_fire_time_changed,
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
from homeassistant.const import STATE_UNAVAILABLE, TargetKey
from homeassistant.core import HomeAssistant

from . import TEST_LATITUDE, TEST_LONGITUDE, setup_integration

WEATHER_ENTITY = "weather.buienradar"
PARSE_FAILED = {SUCCESS: False, MESSAGE: "no data"}


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


@pytest.mark.usefixtures("mock_buienradar_feeds")
async def test_update_failure_and_recovery(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the entity is unavailable after a failed update and recovers."""
    # Outside the hour buienradar.nl updates its forecast, when failures keep the data.
    freezer.move_to("2026-01-14T12:00:00+00:00")
    await setup_integration(hass)
    assert hass.states.get(WEATHER_ENTITY).state != STATE_UNAVAILABLE

    with patch(
        "homeassistant.components.buienradar.util.parse_data",
        return_value=PARSE_FAILED,
    ):
        freezer.tick(timedelta(minutes=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(WEATHER_ENTITY).state == STATE_UNAVAILABLE

    # A failed update is retried two minutes later.
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(WEATHER_ENTITY).state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_buienradar_feeds")
async def test_failure_during_service_quiet_hour_keeps_data(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a failed update keeps the last data while the service updates."""
    # 23:20 UTC is 00:20 CET, inside the hour buienradar.nl updates its forecast.
    freezer.move_to("2026-01-14T23:10:00+00:00")
    await setup_integration(hass)
    state = hass.states.get(WEATHER_ENTITY)
    assert state.state != STATE_UNAVAILABLE

    with patch(
        "homeassistant.components.buienradar.util.parse_data",
        return_value=PARSE_FAILED,
    ):
        freezer.tick(timedelta(minutes=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(WEATHER_ENTITY).state == state.state
