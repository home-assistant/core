"""Test diagnostics of Linear Garage Door."""

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .util import async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    entry = await async_init_integration(hass)
    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert result == snapshot
