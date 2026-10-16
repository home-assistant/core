"""Test the Chess.com initialization."""

from unittest.mock import AsyncMock

from chess_com_api import ChessComAPIError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.chess_com.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_chess_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Chess.com device."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "532748851"), mock_config_entry.entry_id
    )
    assert device
    assert device == snapshot


async def test_setup_entry_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_chess_client: AsyncMock,
) -> None:
    """Test setup is retried when Chess.com cannot be reached."""
    mock_chess_client.get_player.side_effect = ChessComAPIError("Boom")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "update_error"
    assert mock_config_entry.reason == (
        "An error occurred while communicating with Chess.com: Boom"
    )
