"""Test Matter sensors."""

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.water_heater import STATE_ECO
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import snapshot_matter_entities


@pytest.mark.usefixtures("matter_devices")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.WATER_HEATER)


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test water heater sensor."""
    state = hass.states.get("water_heater.water_heater_none")
    assert state
    assert state.attributes["min_temp"] == 40
    assert state.attributes["max_temp"] == 65
    assert state.attributes["temperature"] == 65
    assert state.state == STATE_ECO
