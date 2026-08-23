"""Test the Tonewinner AT-500 services."""

from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.tonewinner.const import DOMAIN
from homeassistant.components.tonewinner.media_player import TonewinnerMediaPlayer
from homeassistant.components.tonewinner.services import SERVICE_SEND_RAW_FIELDS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_send_raw_service_schema_validation(
    hass: HomeAssistant,
) -> None:
    """Test the send_raw service schema validation."""
    schema = vol.Schema(SERVICE_SEND_RAW_FIELDS)
    valid_data = {"command": "TEST COMMAND"}
    assert schema(valid_data) == valid_data

    with pytest.raises(vol.Invalid):
        schema({})

    with pytest.raises(vol.Invalid):
        schema({"command": None})


async def test_send_raw_service_call(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test calling the send_raw service routes to the entity."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tonewinner.TonewinnerReceiver",
        return_value=mock_receiver,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("media_player.tonewinner_at_500")
    assert state is not None

    await hass.services.async_call(
        DOMAIN,
        "send_raw",
        {"command": "PWR01"},
        target={"entity_id": "media_player.tonewinner_at_500"},
        blocking=True,
    )

    mock_receiver.send_command.assert_called_once_with("PWR01")


async def test_send_raw_service_multiple_commands(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test sending multiple raw commands in sequence."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    commands = ["CMD1", "CMD2", "CMD3"]

    for cmd in commands:
        await entity.send_raw_command(cmd)

    actual = [call.args[0] for call in mock_receiver.send_command.call_args_list]
    assert actual == commands


async def test_send_raw_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test sending a raw command while disconnected raises a user error."""
    mock_config_entry.add_to_hass(hass)
    mock_receiver.connected = False

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    with pytest.raises(HomeAssistantError, match="Not connected"):
        await entity.send_raw_command("PWR01")

    mock_receiver.send_command.assert_not_called()


async def test_send_raw_invalid_hex(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test an invalid hex command raises a user error."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    with pytest.raises(HomeAssistantError, match="Invalid hex command"):
        await entity.send_raw_command("0xZZ")

    mock_receiver.send_command.assert_not_called()


async def test_send_raw_non_ascii_hex(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test a hex command with non-ASCII bytes raises a user error."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    with pytest.raises(HomeAssistantError, match="non-ASCII"):
        await entity.send_raw_command("0xFF")

    mock_receiver.send_command.assert_not_called()


async def test_send_raw_valid_hex(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test a valid hex command is decoded and sent."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.send_raw_command("0x21 0x50")

    mock_receiver.send_command.assert_called_once_with("!P")
