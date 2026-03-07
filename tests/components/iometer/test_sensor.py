"""Test the sensors provided by the Powerfox integration."""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.conftest import AsyncMock


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_sensors(
    hass: HomeAssistant,
    mock_iometer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Iometer sensors."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
