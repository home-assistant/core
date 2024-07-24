"""Test SimpliSafe diagnostics."""

from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import snapshot_get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    setup_simplisafe,
) -> None:
    """Test config entry diagnostics."""
    await snapshot_get_diagnostics_for_config_entry(
        hass, hass_client, config_entry, snapshot
    )
