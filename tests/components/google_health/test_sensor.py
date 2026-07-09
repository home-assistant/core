"""Tests for Google Health sensor platform."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

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
    """Test steps and distance sensors when the rollup endpoint returns no data."""
    mock_google_health_client.steps.today.return_value = None
    mock_google_health_client.distance.today.return_value = None

    assert await integration_setup()

    steps_state = hass.states.get("sensor.google_health_steps")
    assert steps_state is not None
    assert steps_state.state == "0"

    distance_state = hass.states.get("sensor.google_health_distance")
    assert distance_state is not None
    assert distance_state.state == "0.0"
