"""Tests for the diagnostics data provided by LG webOS TV."""

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import setup_webostv

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    client,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    entry = await setup_webostv(hass)
    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot(
        exclude=props("created_at", "modified_at", "entry_id")
    )
