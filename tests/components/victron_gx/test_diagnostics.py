"""Tests for victron_gx diagnostics."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion
from victron_mqtt import Hub as VictronVenusHub

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    with patch(
        "homeassistant.components.victron_gx.hub.VictronVenusHub"
    ):
        result = await get_diagnostics_for_config_entry(
            hass, hass_client, mock_config_entry
        )
    assert result == snapshot
