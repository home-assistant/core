"""Tests for the sensors of the Backup integration."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.backup.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_backup_integration

from tests.common import snapshot_platform


async def test_setup_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup backup config entry."""
    with patch("homeassistant.components.backup.PLATFORMS", [Platform.SENSOR]):
        await setup_backup_integration(hass, with_hassio=False)
        await hass.async_block_till_done(wait_background_tasks=True)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
