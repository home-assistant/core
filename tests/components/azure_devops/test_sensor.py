"""Tests for init of Azure DevOps."""

import pytest

from homeassistant.components.azure_devops.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_devops_client: AsyncMock,
) -> None:
    """Test the sensor entities."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

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

    entry = entity_registry.async_get("sensor.testproject_test_build_latest_build")
    assert entry
    assert entry.unique_id == "testorg_1234_9876_latest_build"
