"""Test Trafikverket Weatherstation diagnostics."""

from __future__ import annotations

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, load_int) == snapshot
    )
