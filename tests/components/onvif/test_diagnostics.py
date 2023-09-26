"""Test ONVIF diagnostics."""
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_onvif_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""

    entry, _, _ = await setup_onvif_integration(hass)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
