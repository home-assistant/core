"""Tests for the Kodi diagnostics."""

from unittest.mock import MagicMock

from jsonrpc_base.jsonrpc import ProtocolError, TransportError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import VIDEO_PLAYER, setup_integration


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_kodi: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration(hass, mock_config_entry)
    mock_kodi.get_players.return_value = [VIDEO_PLAYER]

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


@pytest.mark.usefixtures("mock_kodi")
async def test_diagnostics_disconnected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics when Kodi is not connected."""
    await setup_integration(hass, mock_config_entry)
    mock_connection.connected = False

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TransportError("Connection lost"), id="transport_error"),
        pytest.param(
            TransportError(
                "Transport Error",
                None,
                OSError("Cannot connect to host kodi.local:8080"),
            ),
            id="transport_error_with_host",
        ),
        pytest.param(ProtocolError("Invalid response"), id="protocol_error"),
    ],
)
async def test_diagnostics_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_kodi: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    error: Exception,
) -> None:
    """Test diagnostics when querying Kodi fails."""
    await setup_integration(hass, mock_config_entry)
    mock_kodi.get_players.side_effect = error

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
