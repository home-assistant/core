"""Tests for the WeatherFlow Cloud weather platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.typing import WebSocketGenerator
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


async def test_forecast_subscription_survives_a_missing_station(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
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

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": "daily",
            "entity_id": "weather.my_home_station",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    subscription_id = msg["id"]

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["event"]["forecast"]

    mock_rest_api.get_all_data.return_value = {}

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["event"]["forecast"] is None
