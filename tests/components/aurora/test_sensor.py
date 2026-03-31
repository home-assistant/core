"""Test the Aurora sensor platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Only set up the sensor platform."""
    with patch(
        "homeassistant.components.aurora.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_aurora_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Aurora sensor entity."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_update(
    hass: HomeAssistant,
    mock_aurora_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor value updates on coordinator refresh."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.aurora_visibility_visibility")
    assert state is not None
    assert state.state == "42"

    # Update the forecast data
    mock_aurora_client.get_forecast_data.return_value = 85
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.aurora_visibility_visibility")
    assert state is not None
    assert state.state == "85"


async def test_sensor_unavailable_on_coordinator_error(
    hass: HomeAssistant,
    mock_aurora_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable when coordinator update fails."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.aurora_visibility_visibility")
    assert state is not None
    assert state.state == "42"

    # Simulate API error
    mock_aurora_client.get_forecast_data.side_effect = ClientError
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.aurora_visibility_visibility")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
