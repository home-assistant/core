"""Test the ToneWinner AT-500 services."""

from unittest.mock import MagicMock

import pytest
from serial_asyncio_fast import SerialTransport
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
    # Valid schema
    valid_data = {"command": "TEST COMMAND"}
    assert SERVICE_SEND_RAW_SCHEMA(valid_data) is not None

    # Missing command key
    with pytest.raises(vol.Invalid):  # Missing required key
        SERVICE_SEND_RAW_SCHEMA({})

    # None value (cv.string raises vol.Invalid for None)
    with pytest.raises(vol.Invalid):
        SERVICE_SEND_RAW_SCHEMA({"command": None})


async def test_send_raw_service_empty_command(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test send_raw service with empty command."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity._transport = mock_serial_connection

    # Send empty command
    await entity.send_raw_command("")

    # Should still attempt to write (protocol may allow empty)
    mock_serial_connection.write.assert_called()


async def test_send_raw_service_with_special_chars(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test send_raw service with special characters."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity._transport = mock_serial_connection

    # Send command with special characters
    special_command = "CMD\x01\x02\x03"

    await entity.send_raw_command(special_command)

    mock_serial_connection.write.assert_called()


async def test_send_raw_service_multiple_commands(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test sending multiple raw commands in sequence."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity._transport = mock_serial_connection

    # Send multiple commands
    commands = ["CMD1", "CMD2", "CMD3"]

    for cmd in commands:
        await entity.send_raw_command(cmd)

    # Verify all commands were sent
    assert mock_serial_connection.write.call_count == len(commands)


async def test_send_raw_service_long_command(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test send_raw service with very long command."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity._transport = mock_serial_connection

    # Send long command
    long_command = "A" * 1000

    await entity.send_raw_command(long_command)

    mock_serial_connection.write.assert_called()
