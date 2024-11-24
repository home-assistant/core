"""Tests for the JVC Projector binary sensor devices."""

from unittest.mock import MagicMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_binary_sensor_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup of the binary sensor entities and their states."""
    # Set up mock device with all binary sensor states
    mock_device.get_state.return_value = {
        "power": "standby",
        "low_latency": "off",
        "eshift": "on",
        "source": "signal",
    }

    # Set up integration with only binary sensor platform
    with patch(
        "homeassistant.components.jvc_projector.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    # Validate all binary sensor states via snapshot
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
