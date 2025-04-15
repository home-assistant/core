"""Tests the diagnostics for Home Assistant Backup integration."""

from syrupy import SnapshotAssertion

from homeassistant.components.backup.const import DOMAIN
from homeassistant.core import HomeAssistant

from .common import setup_backup_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_backup_integration(hass, with_hassio=False)
    await hass.async_block_till_done(wait_background_tasks=True)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    diag_data = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag_data == snapshot
