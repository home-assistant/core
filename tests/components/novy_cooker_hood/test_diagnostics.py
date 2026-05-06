"""Tests for the diagnostics provided by the Novy Cooker Hood integration."""

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_novy_cooker_hood: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_novy_cooker_hood
    ) == snapshot(
        exclude=props(
            "created_at", "modified_at", "entry_id", "unique_id", "transmitter"
        )
    )
