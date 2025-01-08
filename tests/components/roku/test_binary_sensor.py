"""Tests for the sensors provided by the Roku integration."""

from unittest.mock import MagicMock, patch

import pytest
from rokuecp import Device as RokuDevice
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("mock_device", ["roku3", "rokutv-7820x"], indirect=True)
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_device: RokuDevice,
    mock_roku: MagicMock,
) -> None:
    """Test the Roku binary sensor entities."""
    with patch("homeassistant.components.roku.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry, mock_device)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
