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

async def test_forecast_callbacks_return_none_when_station_is_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rest_api: AsyncMock,
    mock_get_stations: AsyncMock,
    mock_websocket_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test forecast callbacks do not raise when the station disappears."""
    with patch(
        "homeassistant.components.weatherflow_cloud.PLATFORMS", [Platform.WEATHER]
    ):
        await setup_integration(hass, mock_config_entry)

    weather = hass.data["entity_components"]["weather"].get_entity(
        "weather.my_home_station"
    )
    assert weather is not None

    mock_rest_api.get_all_data.return_value = {}

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert weather._async_forecast_daily() is None
    assert weather._async_forecast_hourly() is None
