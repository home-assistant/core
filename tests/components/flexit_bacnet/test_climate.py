"""Tests for the Flexit Nordic (BACnet) climate entity."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.flexit_bacnet import setup_with_selected_platforms


async def test_climate_entity(
    hass: HomeAssistant,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the initial parameters."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
