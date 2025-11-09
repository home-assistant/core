"""Tests for the WLED button platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

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
async def test_sesnor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
) -> None:
    """Test the creation and values of the WLED button."""

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    assert (
        entity_entry := entity_registry.async_get(
            "sensor.testuser_domain_com_total_available_storage"
        )
    )
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot
