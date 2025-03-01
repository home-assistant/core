"""Tests for the sensors of the Backup integration."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.backup.const import DOMAIN
from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_backup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_setup_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup backup config entry."""
    await setup_backup_integration(hass, with_hassio=False)
    entry = MockConfigEntry(domain=DOMAIN, source=SOURCE_SYSTEM)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.backup.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
