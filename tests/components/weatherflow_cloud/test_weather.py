"""Tests for the WeatherFlow Cloud weather platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import JsonValueType

from . import setup_integration


async def test_weather(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_rest_api: AsyncMock,
    mock_get_stations: AsyncMock,
    mock_websocket_api: AsyncMock,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.weatherflow_cloud.PLATFORMS", [Platform.WEATHER]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_forecast_subscription_survives_a_missing_station(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rest_api: AsyncMock,
    mock_get_stations: AsyncMock,
    mock_websocket_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a live forecast subscription when the station disappears."""
    with patch(
        "homeassistant.components.weatherflow_cloud.PLATFORMS", [Platform.WEATHER]
    ):
        await setup_integration(hass, mock_config_entry)

    weather = hass.data["entity_components"]["weather"].get_entity(
        "weather.my_home_station"
    )
    assert weather is not None

    forecasts: list[list[JsonValueType] | None] = []
    weather.async_subscribe_forecast("daily", forecasts.append)

    mock_rest_api.get_all_data.return_value = {}

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await weather.async_update_listeners(["daily"])
    assert forecasts
    assert all(forecast is None for forecast in forecasts)
