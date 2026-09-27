"""Tests for the diagnostics data provided by the Velux integration."""

from unittest.mock import MagicMock, patch

import pytest
from pyvlx.const import GatewayState, GatewaySubState
from pyvlx.dataobjects import DtoState
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2025-01-01T00:00:00+00:00")
@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_pyvlx: MagicMock,
    mock_window: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for Velux config entry."""
    mock_window.node_id = 1
    mock_pyvlx.connection.connected = True
    mock_pyvlx.connection.connection_counter = 3
    mock_pyvlx.connection.frame_received_cbs = []
    mock_pyvlx.connection.connection_opened_cbs = []
    mock_pyvlx.connection.connection_closed_cbs = []
    mock_pyvlx.klf200.state = DtoState(
        GatewayState.GATEWAY_MODE_WITH_ACTUATORS, GatewaySubState.IDLE
    )
    mock_pyvlx.klf200.version = None
    mock_pyvlx.klf200.protocol_version = None

    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.velux.PLATFORMS", [Platform.COVER]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
