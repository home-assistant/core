"""Tests for init of Azure DevOps."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "mock_devops_client",
)
async def test_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor entities."""
    assert (state := hass.states.get("sensor.testproject_test_build_latest_build"))
    assert state.state == "1"
    assert state.attributes["definition_id"] == 9876
    assert state.attributes["definition_name"] == "Test Build"
    assert state.attributes["id"] == 5678
    assert state.attributes["reason"] == "manual"
    assert state.attributes["result"] == "succeeded"
    assert state.attributes["source_branch"] == "main"
    assert state.attributes["source_version"] == "123"
    assert state.attributes["status"] == "completed"
