"""Test weather of AccuWeather integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.accuweather.const import UPDATE_INTERVAL_DAILY_FORECAST
from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import init_integration

from tests.common import async_fire_time_changed, snapshot_platform
from tests.typing import WebSocketGenerator


async def test_weather(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_accuweather_client: AsyncMock,
) -> None:
    """Test states of the weather without forecast."""
    with patch("homeassistant.components.accuweather.PLATFORMS", [Platform.WEATHER]):
        entry = await init_integration(hass)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_availability(
    hass: HomeAssistant,
    mock_accuweather_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    entity_id = "weather.home"
    await init_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "sunny"

    mock_accuweather_client.async_get_current_conditions.side_effect = ConnectionError

    freezer.tick(UPDATE_INTERVAL_DAILY_FORECAST)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_accuweather_client.async_get_current_conditions.side_effect = None

    freezer.tick(UPDATE_INTERVAL_DAILY_FORECAST)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "sunny"


async def test_manual_update_entity(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await init_integration(hass)

    await async_setup_component(hass, "homeassistant", {})

    assert mock_accuweather_client.async_get_current_conditions.call_count == 1

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["weather.home"]},
        blocking=True,
    )

    assert mock_accuweather_client.async_get_current_conditions.call_count == 2


async def test_unsupported_condition_icon_data(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test with unsupported condition icon data."""
    mock_accuweather_client.async_get_current_conditions.return_value["WeatherIcon"] = (
        999
    )

    await init_integration(hass)

    state = hass.states.get("weather.home")
    assert state.attributes.get(ATTR_FORECAST_CONDITION) is None


@pytest.mark.parametrize(
    ("service"),
    [SERVICE_GET_FORECASTS],
)
async def test_forecast_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_accuweather_client: AsyncMock,
    service: str,
) -> None:
    """Test multiple forecast."""
    await init_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": "weather.home",
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_forecast_subscription(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    mock_accuweather_client: AsyncMock,
) -> None:
    """Test multiple forecast."""
    client = await hass_ws_client(hass)

    await init_integration(hass)

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": "daily",
            "entity_id": "weather.home",
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

    assert forecast1 != []
    assert forecast1 == snapshot

    freezer.tick(UPDATE_INTERVAL_DAILY_FORECAST + timedelta(seconds=1))
    await hass.async_block_till_done()
    msg = await client.receive_json()

    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    forecast2 = msg["event"]["forecast"]

    assert forecast2 != []
    assert forecast2 == snapshot
