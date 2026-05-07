"""Test for PTDevices sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.ptdevices._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_ptdevices_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_ptdevices_config_entry.entry_id
    )
