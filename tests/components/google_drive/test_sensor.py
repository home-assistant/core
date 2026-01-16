"""Tests for the Google Drive sensor platform."""

import json
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from google_drive_api.exceptions import GoogleDriveApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.backup import AgentBackup
from homeassistant.components.google_drive.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = [
    pytest.mark.freeze_time("2021-11-04 17:36:59+01:00"),
]


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up Google Drive integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test the creation and values of the Google Drive sensors."""
    await setup_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    assert (
        entity_entry := entity_registry.async_get(
            "sensor.testuser_domain_com_total_available_storage"
        )
    )

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_unknown_when_unlimited_plan(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test the total storage are unknown when the user is on an unlimited plan."""
    mock_api.get_user = AsyncMock(
        return_value={
            "storageQuota": {
                "limit": None,
                "usage": "100",
                "usageInDrive": "50",
                "usageInTrash": "10",
            }
        }
    )

    assert not hass.states.get("sensor.testuser_domain_com_total_available_storage")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_availability(
    hass: HomeAssistant,
    mock_api: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the availability handling of the Google Drive sensors."""
    await setup_integration(hass, config_entry)

    mock_api.get_user.side_effect = GoogleDriveApiError("API error")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        state := hass.states.get("sensor.testuser_domain_com_total_available_storage")
    )
    assert state.state == STATE_UNAVAILABLE

    mock_api.list_files.side_effect = [{"files": []}]
    mock_api.get_user.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        state := hass.states.get("sensor.testuser_domain_com_total_available_storage")
    )
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calculate_backups_size(
    hass: HomeAssistant,
    mock_api: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test the availability handling of the Google Drive sensors."""
    await setup_integration(hass, config_entry)

    assert (
        state := hass.states.get("sensor.testuser_domain_com_total_size_of_backups")
    )
    assert state.state == "0.0"

    mock_api.list_files = AsyncMock(
        return_value={
            "files": [
                {
                    "id": "HA folder ID",
                    "name": "HA folder name",
                    "description": json.dumps(mock_agent_backup.as_dict()),
                }
            ]
        }
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        state := hass.states.get("sensor.testuser_domain_com_total_size_of_backups")
    )
    assert state.state == "100.0"
