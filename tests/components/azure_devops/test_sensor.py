"""Tests for init of Azure DevOps."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: AsyncMock,
) -> None:
    """Test the sensor entities."""
    assert await setup_integration(hass, mock_config_entry)

    base_entity_id = "sensor.testproject_ci"
    sensor_keys = [
        "latest_build",
        "build_id",
        "build_reason",
        "build_result",
        "build_source_branch",
        "build_source_version",
        "build_status",
        "build_queue_time",
        "build_start_time",
        "build_finish_time",
        "build_url",
    ]

    for sensor_key in sensor_keys:
        assert (entry := entity_registry.async_get(f"{base_entity_id}_{sensor_key}"))

        assert entry == snapshot(name=f"{entry.entity_id}-entry")

        assert hass.states.get(entry.entity_id) == snapshot(
            name=f"{entry.entity_id}-state"
        )
