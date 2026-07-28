"""Tests for the Honeywell Lyric binary sensor platform."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_credentials: None,
    mock_lyric_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lyric binary sensor platform via a real config entry setup."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
