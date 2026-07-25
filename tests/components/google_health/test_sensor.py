"""Tests for Google Health sensor platform."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

from google_health_api.model import ListDataPointResult, _ListDataPointsModel
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_google_health_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test all sensor entities."""
    with patch("homeassistant.components.google_health._PLATFORMS", [Platform.SENSOR]):
        assert await integration_setup()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_sensor_empty_rollup(
    hass: HomeAssistant,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test rollup sensors when the rollup endpoints return no data."""
    mock_google_health_client.steps.today.return_value = None
    mock_google_health_client.distance.today.return_value = None
    mock_google_health_client.active_energy_burned.today.return_value = None
    mock_google_health_client.total_calories.today.return_value = None
    mock_google_health_client.floors.today.return_value = None

    assert await integration_setup()

    steps_state = hass.states.get("sensor.google_health_steps")
    assert steps_state is not None
    assert steps_state.state == "0"

    distance_state = hass.states.get("sensor.google_health_distance")
    assert distance_state is not None
    assert distance_state.state == "0.0"

    active_calories_state = hass.states.get("sensor.google_health_active_calories")
    assert active_calories_state is not None
    assert active_calories_state.state == "0.0"

    total_calories_state = hass.states.get("sensor.google_health_total_calories")
    assert total_calories_state is not None
    assert total_calories_state.state == "0.0"

    floors_state = hass.states.get("sensor.google_health_floors")
    assert floors_state is not None
    assert floors_state.state == "0"


async def test_sensor_empty_sleep(
    hass: HomeAssistant,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test sleep sensors when the sleep endpoint returns no data."""
    mock_google_health_client.sleep.list.return_value = ListDataPointResult(
        _ListDataPointsModel(data_points=[])
    )

    assert await integration_setup()

    time_asleep_state = hass.states.get("sensor.google_health_time_asleep")
    assert time_asleep_state is not None
    assert time_asleep_state.state == "unknown"
