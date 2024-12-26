"""Velbus binary_sensor platform tests."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_binary_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test if all binary_sensors get created."""
    assert len(hass.states.async_entity_ids("binary_sensor")) == 1

    state = hass.states.get("binary_sensor.ButtonOn")
    assert state
    assert state.state == STATE_ON
