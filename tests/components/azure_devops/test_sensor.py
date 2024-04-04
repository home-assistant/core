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

    assert (
        entry := entity_registry.async_get("sensor.testproject_test_build_latest_build")
    )

    assert entry == snapshot(name=f"{entry.entity_id}-entry")

    assert hass.states.get(entry.entity_id) == snapshot(name=f"{entry.entity_id}-state")
