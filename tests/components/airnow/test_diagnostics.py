"""Test AirNow diagnostics."""
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    setup_airnow,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
