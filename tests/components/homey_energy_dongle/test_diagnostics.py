"""Test Homey Energy Dongle diagnostics."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics redact the meter identifiers."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == snapshot(exclude=props("created_at", "modified_at", "entry_id"))
