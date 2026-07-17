"""Test the Nespresso entities."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import SERVICE_INFO

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("platform", [Platform.SENSOR, Platform.BINARY_SENSOR])
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_update_device: AsyncMock,
    platform: Platform,
) -> None:
    """Test the created entities."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.nespresso_ble.PLATFORMS", [platform]),
        patch(
            "homeassistant.components.nespresso_ble.coordinator.bluetooth.async_ble_device_from_address",
            return_value=SERVICE_INFO.device,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
