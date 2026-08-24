"""Tests for Specialized Turbo diagnostics."""

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import ENCRYPTED_SERVICE_INFO, MockLibrary, make_populated_snapshot

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    encrypted_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics redact encryption metadata and include telemetry."""
    mock_library.monitor.snapshot = make_populated_snapshot()
    await setup_integration(hass, encrypted_config_entry, ENCRYPTED_SERVICE_INFO)

    result = await get_diagnostics_for_config_entry(
        hass,
        hass_client,
        encrypted_config_entry,
    )

    assert result == snapshot(
        exclude=props("created_at", "modified_at", "entry_id", "time")
    )
