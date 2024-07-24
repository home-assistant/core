"""Test Notion diagnostics."""

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.components.diagnostics import snapshot_get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    setup_config_entry,
) -> None:
    """Test config entry diagnostics."""
    assert await snapshot_get_diagnostics_for_config_entry(
        hass, hass_client, config_entry, snapshot
    )
