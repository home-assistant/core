"""Test the Aurora binary sensor platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def binary_sensor_only() -> Generator[None]:
    """Only set up the binary sensor platform."""
    with patch(
        "homeassistant.components.aurora.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        yield


async def test_binary_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_aurora_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Aurora binary sensor entity."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensor_above_threshold(
    hass: HomeAssistant,
    mock_aurora_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor is ON when forecast exceeds threshold."""
    # Forecast is 42, threshold is 75 -> OFF
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.aurora_visibility_visibility_alert")
    assert state is not None
    assert state.state == STATE_OFF

    # Update forecast above threshold
    mock_aurora_client.get_forecast_data.return_value = 80
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.aurora_visibility_visibility_alert")
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensor_below_threshold(
    hass: HomeAssistant,
    mock_aurora_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor is OFF when forecast is below threshold."""
    # Forecast is 42, threshold is 75 -> OFF
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.aurora_visibility_visibility_alert")
    assert state is not None
    assert state.state == STATE_OFF


async def test_binary_sensor_unavailable_on_error(
    hass: HomeAssistant,
    mock_aurora_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor becomes unavailable when coordinator update fails."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.aurora_visibility_visibility_alert")
    assert state is not None
    assert state.state == STATE_OFF

    # Simulate API error
    mock_aurora_client.get_forecast_data.side_effect = ClientError
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.aurora_visibility_visibility_alert")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
