"""Velbus binary_sensor platform tests."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.velbus.PLATFORMS", [Platform.BINARY_SENSOR]):
        await init_integration(hass, config_entry)

    state = hass.states.get("binary_sensor.ButtonOn")
    assert state
    assert state.state == STATE_ON

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
