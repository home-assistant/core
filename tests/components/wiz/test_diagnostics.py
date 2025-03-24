"""Test WiZ diagnostics."""

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import async_setup_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    _, entry = await async_setup_integration(hass)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
