"""Tests for the Google Drive sensor platform."""

from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.google_drive.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = [
    pytest.mark.freeze_time("2021-11-04 17:36:59+01:00"),
]


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Set up Google Drive integration."""
    mock_api.list_files = AsyncMock(
        return_value={"files": [{"id": "HA folder ID", "name": "HA folder name"}]}
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "setup_integration",
)
async def test_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
) -> None:
    """Test the creation and values of the Google Drive sensors."""

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    assert (
        entity_entry := entity_registry.async_get(
            "sensor.testuser_domain_com_total_available_storage"
        )
    )

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "setup_integration",
)
async def test_sesnor_unavailable_when_unlimited_plan(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
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
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        entity_entry := entity_registry.async_get(
            "sensor.testuser_domain_com_total_available_storage"
        )
    )
    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "unknown"
