"""Climate sensor tests for Intergas InComfort integration."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import snapshot_platform


@patch("homeassistant.components.incomfort.PLATFORMS", [Platform.CLIMATE])
@pytest.mark.parametrize(
    "mock_room_status",
    [
        {"room_temp": 21.42, "setpoint": 18.0, "override": 18.0},
        {"room_temp": 21.42, "setpoint": 18.0, "override": 0.0},
    ],
    ids=["new_thermostat", "legacy_thermostat"],
)
async def test_setup_platform(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test the incomfort entities are set up correctly.

    Legacy thermostats report 0.0 as override if no override is set,
    but new thermostat sync the override with the actual setpoint instead.
    """
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
