"""Tests for Intergas InComfort integration."""

from unittest.mock import MagicMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.incomfort import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_CONFIG

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.incomfort.PLATFORMS", [Platform.SENSOR])
async def test_setup_platforms(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the incomfort integration is set up correctly."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
