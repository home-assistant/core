"""Test Yale Smart Living diagnostics."""
from __future__ import annotations

from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    load_int: ConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = load_int

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag == snapshot
