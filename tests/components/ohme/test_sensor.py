"""Tests for sensors."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

SENSORS = ("power", "energy", "current", "ct_current" "status")


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Ohme sensors."""
    with patch("homeassistant.components.ohme.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    for sensor in SENSORS:
        assert hass.states.get(f"sensor.ohme_home_pro_{sensor}") == snapshot(
            name=f"sensor.ohme_home_pro_{sensor}-state"
        )
