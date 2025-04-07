"""Tests for the diagnostics data provided by the miele integration."""

from syrupy import SnapshotAssertion
from syrupy.filters import paths

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    init_integration,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(
        exclude=paths(
            "config_entry_data.token.expires_at",
            "miele_test.entry_id",
        )
    )
