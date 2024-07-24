"""Test APCUPSd diagnostics reporting abilities."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import async_init_integration

from tests.components.diagnostics import snapshot_get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    entry = await async_init_integration(hass)
    await snapshot_get_diagnostics_for_config_entry(hass, hass_client, entry, snapshot)
