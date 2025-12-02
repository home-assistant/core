"""Test GIOS diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_config_entry = await init_integration(hass)
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
