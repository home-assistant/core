"""Test Tuya fan platform."""

from __future__ import annotations

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import ManagerCompat
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device_arete_two_12l_dehumidifier_air_purifier: CustomerDevice,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    # Setup
    mock_manager.device_map = {
        mock_device_arete_two_12l_dehumidifier_air_purifier.id: mock_device_arete_two_12l_dehumidifier_air_purifier,
    }
    mock_config_entry.add_to_hass(hass)

    # Initialize the component
    with (
        patch("homeassistant.components.tuya.ManagerCompat", return_value=mock_manager),
        patch("homeassistant.components.tuya.PLATFORMS", [Platform.FAN]),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
