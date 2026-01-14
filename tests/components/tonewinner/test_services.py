"""Test the ToneWinner AT-500 services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from serial_asyncio_fast import SerialTransport
import voluptuous as vol

from homeassistant.components.tonewinner import async_unload_entry, media_player
from homeassistant.components.tonewinner.const import DOMAIN
from homeassistant.components.tonewinner.media_player import (
    SERVICE_SEND_RAW,
    SERVICE_SEND_RAW_SCHEMA,
    TonewinnerMediaPlayer,
)
from homeassistant.core import HomeAssistant, ServiceCall


async def test_send_raw_service(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test the send_raw service."""
    mock_config_entry.add_to_hass(hass)

    # Create entity
    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity._transport = mock_serial_connection
    entity.entity_id = "media_player.tonewinner_at_500"

    # Add entity to hass
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entities"] = {entity.entity_id: entity}

    # Call the service
    call = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SEND_RAW,
        data={"command": "CUSTOM TEST COMMAND"},
    )

    await entity.send_raw_command(call.data["command"])

    # Verify command was sent
    mock_serial_connection.write.assert_called()


async def test_send_raw_service_schema_validation(
    hass: HomeAssistant,
) -> None:
    """Test the send_raw service schema validation."""
    # Valid schema
    valid_data = {"command": "TEST COMMAND"}
    assert SERVICE_SEND_RAW_SCHEMA(valid_data) is not None

    # Missing command
    with pytest.raises(vol.Invalid):
        SERVICE_SEND_RAW_SCHEMA({})

    # Invalid type
    with pytest.raises(vol.Invalid):
        SERVICE_SEND_RAW_SCHEMA({"command": 123})


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


async def test_send_raw_service_when_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test send_raw service when device is disconnected."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity._transport = None  # Not connected

    # Should not raise an exception
    await entity.send_raw_command("TEST COMMAND")


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


async def test_service_registration(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test that services are registered correctly during setup."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.services.async_register") as mock_register:
        await media_player.async_setup_entry(hass, mock_config_entry, AsyncMock())

        # Verify service was registered
        mock_register.assert_called()


async def test_service_deregistration_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test that services are deregistered when config entry is unloaded."""
    mock_config_entry.add_to_hass(hass)

    # Simulate registered service
    hass.data.setdefault(DOMAIN, {})
    service_key = f"{mock_config_entry.entry_id}_service"
    hass.data[DOMAIN][service_key] = MagicMock()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=True,
    ):
        await async_unload_entry(hass, mock_config_entry)

    # Service should be removed
    assert service_key not in hass.data.get(DOMAIN, {})


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


async def test_send_raw_service_unicode(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test send_raw service with unicode characters."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity._transport = mock_serial_connection

    # Send unicode command
    unicode_command = "测试命令"

    await entity.send_raw_command(unicode_command)

    mock_serial_connection.write.assert_called()
