"""Tests for the diagnostics data provided by the System Monitor integration."""

from unittest.mock import Mock

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_psutil: Mock,
    mock_os: Mock,
    mock_added_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_added_config_entry
    ) == snapshot(exclude=props("last_update", "entry_id"))
