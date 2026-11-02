"""Tests for the diagnostics provided by the Novy Cooker Hood integration."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_novy_cooker_hood: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics returns the entry, entities and transmitter state."""
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, init_novy_cooker_hood
    )

    assert result == snapshot(
        exclude=props(
            "config_entry_id",
            "context",
            "created_at",
            "device_id",
            "entry_id",
            "id",
            "last_changed",
            "last_reported",
            "last_updated",
            "modified_at",
            "unique_id",
        )
    )
