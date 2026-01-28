"""Test weather of Google Weather integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from google_weather_api import GoogleWeatherApiError, WeatherCondition
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.google_weather.weather import _CONDITION_MAP
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_SUNNY,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.typing import WebSocketGenerator


async def test_weather(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test states of the weather."""
    with patch(
        "homeassistant.components.google_weather._PLATFORMS", [Platform.WEATHER]
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    entity_id = "weather.home"
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "sunny"

    mock_google_weather_api.async_get_current_conditions.side_effect = (
        GoogleWeatherApiError()
    )

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Reset side effect, return a valid response again
    mock_google_weather_api.async_get_current_conditions.side_effect = None

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "sunny"
    mock_google_weather_api.async_get_current_conditions.assert_called_with(
        latitude=10.1, longitude=20.1
    )


async def test_manual_update_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await async_setup_component(hass, "homeassistant", {})

    assert mock_google_weather_api.async_get_current_conditions.call_count == 1
    mock_google_weather_api.async_get_current_conditions.assert_called_with(
        latitude=10.1, longitude=20.1
    )

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["weather.home"]},
        blocking=True,
    )

    assert mock_google_weather_api.async_get_current_conditions.call_count == 2


@pytest.mark.parametrize(
    ("api_condition", "is_daytime", "expected_ha_condition"),
    [
        (WeatherCondition.Type.CLEAR, True, ATTR_CONDITION_SUNNY),
        (WeatherCondition.Type.CLEAR, False, ATTR_CONDITION_CLEAR_NIGHT),
        (WeatherCondition.Type.PARTLY_CLOUDY, True, ATTR_CONDITION_PARTLYCLOUDY),
        (WeatherCondition.Type.PARTLY_CLOUDY, False, ATTR_CONDITION_PARTLYCLOUDY),
        (WeatherCondition.Type.TYPE_UNSPECIFIED, True, "unknown"),
    ],
)
async def test_condition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
    api_condition: WeatherCondition.Type,
    is_daytime: bool,
    expected_ha_condition: str,
) -> None:
    """Test condition mapping."""
    mock_google_weather_api.async_get_current_conditions.return_value.weather_condition.type = api_condition
    mock_google_weather_api.async_get_current_conditions.return_value.is_daytime = (
        is_daytime
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get("weather.home")
    assert state.state == expected_ha_condition


def test_all_conditions_mapped() -> None:
    """Ensure all WeatherCondition.Type enum members are in the _CONDITION_MAP."""
    for condition_type in WeatherCondition.Type:
        assert condition_type in _CONDITION_MAP


@pytest.mark.parametrize(("forecast_type"), ["daily", "hourly", "twice_daily"])
async def test_forecast_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_google_weather_api: AsyncMock,
    forecast_type,
) -> None:
    """Test forecast service."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {
            "entity_id": "weather.home",
            "type": forecast_type,
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_forecast_subscription(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test multiple forecast."""
    client = await hass_ws_client(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

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

    freezer.tick(timedelta(hours=1) + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    msg = await client.receive_json()

    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    forecast2 = msg["event"]["forecast"]

    assert forecast2 != []
    assert forecast2 == snapshot
