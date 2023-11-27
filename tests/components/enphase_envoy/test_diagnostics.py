"""Test Enphase Envoy diagnostics."""
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    setup_enphase_envoy,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
