"""Tests the sensors provided by the Garages Amsterdam integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import snapshot_platform


async def test_all_sensors(
    hass: HomeAssistant,
    mock_garages_amsterdam: AsyncMock,
    mock_config_entry: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensors."""
    with patch(
        "homeassistant.components.garages_amsterdam.PLATFORMS", [Platform.SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
