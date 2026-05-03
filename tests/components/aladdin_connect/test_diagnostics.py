"""Tests for the Aladdin Connect diagnostics."""

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await init_integration(hass, mock_config_entry)
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert result == snapshot(
        exclude=props("created_at", "modified_at", "entry_id", "expires_at")
    )
