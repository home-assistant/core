"""Tests for init of Azure DevOps."""

from typing import Final

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import DEVOPS_BUILD_DEFINITION, DEVOPS_PROJECT

from tests.common import MockConfigEntry

BASE_SENSOR_NAME: Final[str] = (
    f"sensor.{DEVOPS_PROJECT.project_id}_{DEVOPS_BUILD_DEFINITION.build_id}"
)


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "mock_devops_client",
)
async def test_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a successful setup entry."""
    assert entity_registry.async_is_registered(f"{BASE_SENSOR_NAME}_latest_build")

    assert (state := hass.states.get(f"{BASE_SENSOR_NAME}_latest_build"))
    assert state.state == "1"
    assert state.attributes["definition_id"] == 1
    assert state.attributes["definition_name"] == "Test Build"
    assert state.attributes["id"] == 1
    assert state.attributes["reason"] == "manual"
    assert state.attributes["result"] == "succeeded"
    assert state.attributes["source_branch"] == "main"
    assert state.attributes["source_version"] == "123"
    assert state.attributes["status"] == "completed"
