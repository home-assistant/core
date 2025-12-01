"""Test the Fressnapf Tracker sensor platform."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import snapshot_devices

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch(
        "homeassistant.components.fressnapf_tracker.PLATFORMS", [Platform.SENSOR]
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_state_entity_device_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entity is created correctly."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    await snapshot_devices(device_registry, mock_config_entry, snapshot)
