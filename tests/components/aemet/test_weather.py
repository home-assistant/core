"""The sensor tests for the AEMET OpenData platform."""
import datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aemet.const import ATTRIBUTION, DOMAIN
from homeassistant.components.aemet.weather_update_coordinator import (
    WEATHER_UPDATE_INTERVAL,
)
from homeassistant.components.weather import (
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_SNOWY,
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
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECAST,
)
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .util import async_init_integration, mock_api_call

from tests.typing import WebSocketGenerator


async def test_aemet_weather(hass: HomeAssistant) -> None:
    """Test states of the weather."""

    hass.config.set_time_zone("UTC")
    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.now", return_value=now), patch(
        "homeassistant.util.dt.utcnow", return_value=now
    ):
        await async_init_integration(hass)

    state = hass.states.get("weather.aemet")
    assert state
    assert state.state == ATTR_CONDITION_SNOWY
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_WEATHER_HUMIDITY) == 99.0
    assert state.attributes.get(ATTR_WEATHER_PRESSURE) == 1004.4  # 100440.0 Pa -> hPa
    assert state.attributes.get(ATTR_WEATHER_TEMPERATURE) == -0.7
    assert state.attributes.get(ATTR_WEATHER_WIND_BEARING) == 90.0
    assert state.attributes.get(ATTR_WEATHER_WIND_SPEED) == 15.0  # 4.17 m/s -> km/h
    forecast = state.attributes.get(ATTR_FORECAST)[0]
    assert forecast.get(ATTR_FORECAST_CONDITION) == ATTR_CONDITION_PARTLYCLOUDY
    assert forecast.get(ATTR_FORECAST_PRECIPITATION) is None
    assert forecast.get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) == 30
    assert forecast.get(ATTR_FORECAST_TEMP) == 4
    assert forecast.get(ATTR_FORECAST_TEMP_LOW) == -4
    assert (
        forecast.get(ATTR_FORECAST_TIME)
        == dt_util.parse_datetime("2021-01-10 00:00:00+00:00").isoformat()
    )
    assert forecast.get(ATTR_FORECAST_WIND_BEARING) == 45.0
    assert forecast.get(ATTR_FORECAST_WIND_SPEED) == 20.0  # 5.56 m/s -> km/h

    state = hass.states.get("weather.aemet_hourly")
    assert state is None


async def test_aemet_weather_legacy(hass: HomeAssistant) -> None:
    """Test states of the weather."""

    registry = er.async_get(hass)
    registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "None hourly",
    )

    hass.config.set_time_zone("UTC")
    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.now", return_value=now), patch(
        "homeassistant.util.dt.utcnow", return_value=now
    ):
        await async_init_integration(hass)

    state = hass.states.get("weather.aemet_daily")
    assert state
    assert state.state == ATTR_CONDITION_SNOWY
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_WEATHER_HUMIDITY) == 99.0
    assert state.attributes.get(ATTR_WEATHER_PRESSURE) == 1004.4  # 100440.0 Pa -> hPa
    assert state.attributes.get(ATTR_WEATHER_TEMPERATURE) == -0.7
    assert state.attributes.get(ATTR_WEATHER_WIND_BEARING) == 90.0
    assert state.attributes.get(ATTR_WEATHER_WIND_SPEED) == 15.0  # 4.17 m/s -> km/h
    forecast = state.attributes.get(ATTR_FORECAST)[0]
    assert forecast.get(ATTR_FORECAST_CONDITION) == ATTR_CONDITION_PARTLYCLOUDY
    assert forecast.get(ATTR_FORECAST_PRECIPITATION) is None
    assert forecast.get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) == 30
    assert forecast.get(ATTR_FORECAST_TEMP) == 4
    assert forecast.get(ATTR_FORECAST_TEMP_LOW) == -4
    assert (
        forecast.get(ATTR_FORECAST_TIME)
        == dt_util.parse_datetime("2021-01-10 00:00:00+00:00").isoformat()
    )
    assert forecast.get(ATTR_FORECAST_WIND_BEARING) == 45.0
    assert forecast.get(ATTR_FORECAST_WIND_SPEED) == 20.0  # 5.56 m/s -> km/h

    state = hass.states.get("weather.aemet_hourly")
    assert state is None


async def test_forecast_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test multiple forecast."""
    hass.config.set_time_zone("UTC")
    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.now", return_value=now), patch(
        "homeassistant.util.dt.utcnow", return_value=now
    ):
        await async_init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {
            "entity_id": "weather.aemet",
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECAST,
        {
            "entity_id": "weather.aemet",
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

    hass.config.set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    await async_init_integration(hass)

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": forecast_type,
            "entity_id": "weather.aemet",
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

    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        freezer.tick(WEATHER_UPDATE_INTERVAL + datetime.timedelta(seconds=1))
        await hass.async_block_till_done()
        msg = await client.receive_json()

    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    forecast2 = msg["event"]["forecast"]

    assert forecast2 == snapshot
