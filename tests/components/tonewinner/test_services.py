"""Test the ToneWinner AT-500 services."""

from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from homeassistant.components.tonewinner.media_player import (
    SERVICE_SEND_RAW_SCHEMA,
    TonewinnerMediaPlayer,
)
from homeassistant.core import HomeAssistant


async def test_send_raw_service_schema_validation(
    hass: HomeAssistant,
) -> None:
    """Test the send_raw service schema validation."""
    valid_data = {"command": "TEST COMMAND"}
    assert SERVICE_SEND_RAW_SCHEMA(valid_data) is not None

    with pytest.raises(vol.Invalid):
        SERVICE_SEND_RAW_SCHEMA({})

    with pytest.raises(vol.Invalid):
        SERVICE_SEND_RAW_SCHEMA({"command": None})


async def test_send_raw_service_empty_command(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test send_raw service with empty command."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.send_raw_command("")

    mock_receiver.send_command.assert_called()


async def test_send_raw_service_with_special_chars(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test send_raw service with special characters."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.send_raw_command("CMD\x01\x02\x03")

    mock_receiver.send_command.assert_called()


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

    assert mock_receiver.send_command.call_count == len(commands)


async def test_send_raw_service_long_command(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test send_raw service with very long command."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.send_raw_command("A" * 1000)

    mock_receiver.send_command.assert_called()
