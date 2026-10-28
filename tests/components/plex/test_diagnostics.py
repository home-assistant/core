"""Tests for the Plex diagnostics."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("mock_plex_server")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entry: MockConfigEntry,
    mock_websocket: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    mock_websocket.return_value.state = "connected"

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
