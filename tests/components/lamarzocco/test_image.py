"""Tests for La Marzocco image."""

from unittest.mock import MagicMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_images(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco images."""

    with patch("homeassistant.components.lamarzocco.PLATFORMS", [Platform.IMAGE]):
        await async_init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
