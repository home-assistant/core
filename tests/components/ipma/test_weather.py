"""The tests for the IPMA weather component."""
import datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ipma.const import MIN_TIME_BETWEEN_UPDATES
from homeassistant.components.weather import (
    ATTR_FORECAST,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
    LEGACY_SERVICE_GET_FORECAST,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import MockLocation

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

TEST_CONFIG = {
    "name": "HomeTown",
    "latitude": "40.00",
    "longitude": "-8.00",
    "mode": "daily",
}

TEST_CONFIG_HOURLY = {
    "name": "HomeTown",
    "latitude": "40.00",
    "longitude": "-8.00",
    "mode": "hourly",
}


class MockBadLocation(MockLocation):
    """Mock Location with unresponsive api."""

    async def observation(self, api):
        """Mock Observation."""
        return None

    async def forecast(self, api, period):
        """Mock Forecast."""
        return []


async def test_setup_config_flow(hass: HomeAssistant) -> None:
    """Test for successfully setting up the IPMA platform."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("weather.hometown")
    assert state.state == "rainy"

    data = state.attributes
    assert data.get(ATTR_WEATHER_TEMPERATURE) == 18.0
    assert data.get(ATTR_WEATHER_HUMIDITY) == 71
    assert data.get(ATTR_WEATHER_PRESSURE) == 1000.0
    assert data.get(ATTR_WEATHER_WIND_SPEED) == 3.94
    assert data.get(ATTR_WEATHER_WIND_BEARING) == "NW"
    assert state.attributes.get("friendly_name") == "HomeTown"


async def test_daily_forecast(hass: HomeAssistant) -> None:
    """Test for successfully getting daily forecast."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("weather.hometown")
    assert state.state == "rainy"

    forecast = state.attributes.get(ATTR_FORECAST)[0]
    assert forecast.get(ATTR_FORECAST_TIME) == datetime.datetime(2020, 1, 16, 0, 0, 0)
    assert forecast.get(ATTR_FORECAST_CONDITION) == "rainy"
    assert forecast.get(ATTR_FORECAST_TEMP) == 16.2
    assert forecast.get(ATTR_FORECAST_TEMP_LOW) == 10.6
    assert forecast.get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) == "100.0"
    assert forecast.get(ATTR_FORECAST_WIND_SPEED) == 10.0
    assert forecast.get(ATTR_FORECAST_WIND_BEARING) == "S"


@pytest.mark.freeze_time("2020-01-14 23:00:00")
async def test_hourly_forecast(hass: HomeAssistant) -> None:
    """Test for successfully getting daily forecast."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG_HOURLY)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("weather.hometown")
    assert state.state == "rainy"

    forecast = state.attributes.get(ATTR_FORECAST)[0]
    assert forecast.get(ATTR_FORECAST_CONDITION) == "rainy"
    assert forecast.get(ATTR_FORECAST_TEMP) == 12.0
    assert forecast.get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) == 80.0
    assert forecast.get(ATTR_FORECAST_WIND_SPEED) == 32.7
    assert forecast.get(ATTR_FORECAST_WIND_BEARING) == "S"


async def test_failed_get_observation_forecast(hass: HomeAssistant) -> None:
    """Test for successfully setting up the IPMA platform."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockBadLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("weather.hometown")
    assert state.state == STATE_UNKNOWN

    data = state.attributes
    assert data.get(ATTR_WEATHER_TEMPERATURE) is None
    assert data.get(ATTR_WEATHER_HUMIDITY) is None
    assert data.get(ATTR_WEATHER_PRESSURE) is None
    assert data.get(ATTR_WEATHER_WIND_SPEED) is None
    assert data.get(ATTR_WEATHER_WIND_BEARING) is None
    assert state.attributes.get("friendly_name") == "HomeTown"


@pytest.mark.parametrize(
    ("service"),
    [
        SERVICE_GET_FORECASTS,
        LEGACY_SERVICE_GET_FORECAST,
    ],
)
async def test_forecast_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    service: str,
) -> None:
    """Test multiple forecast."""

    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": "weather.hometown",
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": "weather.hometown",
            "type": "hourly",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize("forecast_type", ["daily", "hourly"])
async def test_forecast_subscription(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    forecast_type: str,
) -> None:
    """Test multiple forecast."""
    client = await hass_ws_client(hass)

    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": forecast_type,
            "entity_id": "weather.hometown",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None
    subscription_id = msg["id"]

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    forecast1 = msg["event"]["forecast"]

    assert forecast1 == snapshot

    freezer.tick(MIN_TIME_BETWEEN_UPDATES + datetime.timedelta(seconds=1))
    await hass.async_block_till_done()
    msg = await client.receive_json()

    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    forecast2 = msg["event"]["forecast"]

    assert forecast2 == snapshot
