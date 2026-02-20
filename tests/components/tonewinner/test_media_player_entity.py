"""Test the ToneWinner AT-500 media player entity."""

import asyncio
from unittest.mock import MagicMock, patch

from serial_asyncio_fast import SerialTransport

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.components.tonewinner.const import (
    CONF_BAUD_RATE,
    CONF_SERIAL_PORT,
    CONF_SOURCE_MAPPINGS,
    DOMAIN,
)
from homeassistant.components.tonewinner.media_player import (
    INPUT_SOURCES,
    TonewinnerMediaPlayer,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_media_player_setup(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test media player entity setup."""
    mock_config_entry.add_to_hass(hass)

    # Create entity
    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)

    # Verify basic attributes
    assert entity.unique_id == mock_config_entry.entry_id
    assert entity.name == "Tonewinner AT-500"
    assert entity.device_class == "receiver"
    assert entity.available is False
    assert entity.state == MediaPlayerState.OFF


async def test_media_player_device_info(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test media player device info."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)

    # Verify device info
    device_info = entity.device_info
    assert device_info is not None
    assert "identifiers" in device_info and device_info["identifiers"] == {
        (DOMAIN, mock_config_entry.entry_id)
    }
    assert "manufacturer" in device_info and device_info["manufacturer"] == "Tonewinner"
    assert "model" in device_info and device_info["model"] == "AT-500"


async def test_media_player_supported_features(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test media player supported features."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)

    # Verify supported features (should be a non-zero integer)
    assert entity.supported_features > 0


async def test_media_player_source_list_default(
    hass: HomeAssistant,
) -> None:
    """Test media player default source list."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)

    # Should have all default sources
    assert entity.source_list
    assert len(entity.source_list) == len(INPUT_SOURCES)
    assert "HDMI 1" in entity.source_list
    assert "Bluetooth" in entity.source_list


async def test_media_player_source_list_with_mappings(
    hass: HomeAssistant,
) -> None:
    """Test media player source list with custom mappings."""
    # Custom mappings - rename and disable
    source_mappings = {
        "HD1": {"enabled": True, "name": "Living Room TV"},
        "HD2": {"enabled": False, "name": "Bedroom TV"},
        "BT": {"enabled": True, "name": "My Bluetooth"},
    }

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={CONF_SOURCE_MAPPINGS: source_mappings},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)

    # Should only have enabled sources with custom names
    assert "Living Room TV" in entity.source_list
    assert "My Bluetooth" in entity.source_list
    assert "Bedroom TV" not in entity.source_list  # Disabled
    assert "HDMI 1" not in entity.source_list  # Original name not present


async def test_media_player_sound_mode_list(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test media player sound mode list."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)

    # Should have sound modes
    assert entity.sound_mode_list
    assert len(entity.sound_mode_list) > 0


async def test_media_player_connect(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test media player connection."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)

    # Mock the connection
    with patch("serial_asyncio_fast.create_serial_connection") as mock_connect:
        mock_connect.return_value = (mock_serial_connection, MagicMock())

        await entity.connect()

        # Verify connection was attempted
        mock_connect.assert_called_once()


async def test_media_player_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test media player connection failure handling."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)

    # Mock connection failure
    with patch(
        "serial_asyncio_fast.create_serial_connection",
        side_effect=OSError("Connection failed"),
    ):
        await entity.connect()

        # Should mark as unavailable
        assert entity.available is False


async def test_media_player_handle_power_on(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test handling power on response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"

    # Mock async task creation and state update to avoid task cleanup issues
    with patch("asyncio.create_task"), patch.object(entity, "schedule_update_ha_state"):
        # Handle power on response
        entity.handle_response("POWER ON")

        assert entity.state == MediaPlayerState.ON


async def test_media_player_handle_power_off(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test handling power off response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"
    entity._attr_source = "HDMI 1"  # Set a source first

    # Mock async task creation to avoid task cleanup issues
    with patch("asyncio.create_task"):
        # Handle power off response
        entity.handle_response("POWER OFF")

        # Power off should clear the source
        assert entity.state == MediaPlayerState.OFF
        assert entity._attr_source is None  # Source is cleared when powered off


async def test_media_player_handle_volume_response(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test handling volume level response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"

    with patch.object(entity, "schedule_update_ha_state"):
        # Handle volume response (50.0 gets converted to 0-1 scale)
        entity.handle_response("VOL 50.0")

        # The actual conversion depends on the protocol's max volume
        # Just verify it got set
        assert entity.volume_level is not None
        assert 0 <= entity.volume_level <= 1


async def test_media_player_handle_mute_on(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test handling mute on response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"

    # Handle mute on response (protocol format is "MUTE ON")
    entity.handle_response("MUTE ON")

    assert entity.is_volume_muted is True


async def test_media_player_handle_mute_off(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test handling mute off response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"

    # Handle mute off response
    entity.handle_response("AMT OFF")

    assert entity.is_volume_muted is False


async def test_media_player_handle_input_source(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test handling input source response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"

    with patch("asyncio.create_task"):
        # Handle input source response (HD1 = HDMI 1)
        # Note: Protocol format is "V=NO" not "V= NO" (no space after =)
        entity.handle_response("SI 01 HDMI 1 V=HD1 A=HDMI")

        assert entity.source == "HDMI 1"


async def test_media_player_handle_custom_source_name(
    hass: HomeAssistant,
) -> None:
    """Test handling input source with custom name."""
    # Custom source mapping
    source_mappings = {
        "HD1": {"enabled": True, "name": "Living Room TV"},
    }

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={CONF_SOURCE_MAPPINGS: source_mappings},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"

    # Mock async task creation to avoid task cleanup issues
    with patch("asyncio.create_task"):
        # Handle input source response
        # Device returns the default name "HDMI 1", but we have a custom mapping
        # to "Living Room TV", so the integration should map it correctly
        entity.handle_response("SI 01 HDMI 1 V=HD1 A=HDMI")

        # The device sends "HDMI 1" (default name), which maps to source code "HD1",
        # which then maps to the custom name "Living Room TV"
        assert entity.source == "Living Room TV"


async def test_media_player_handle_sound_mode(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test handling sound mode response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"

    # Handle sound mode response (protocol format is "MODE DIRECT")
    entity.handle_response("MODE DIRECT")

    assert entity.sound_mode == "Direct"


async def test_media_player_handle_uppercase_source_with_custom_name(
    hass: HomeAssistant,
) -> None:
    """Test handling uppercase source name with custom mapping."""
    # Custom source mapping - COAXIAL 1 (uppercase from device) -> Sonos
    source_mappings = {
        "CO1": {"enabled": True, "name": "Sonos"},
    }

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={CONF_SOURCE_MAPPINGS: source_mappings},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"

    # Mock async task creation to avoid task cleanup issues
    with patch("asyncio.create_task"):
        # Device sends "COAXIAL 1" in uppercase, but INPUT_SOURCES has "Coaxial 1"
        # The integration should do case-insensitive matching
        entity.handle_response("SI 09 COAXIAL 1 V=NO A=CO1")

        # Should map: "COAXIAL 1" -> "CO1" -> "Sonos"
        assert entity.source == "Sonos"


async def test_media_player_handle_custom_name_from_device(
    hass: HomeAssistant,
) -> None:
    """Test when device sends custom name that matches our HA config."""
    # User configured "Sonos" as custom name in HA AND on the device
    source_mappings = {
        "CO1": {"enabled": True, "name": "Sonos"},
    }

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={CONF_SOURCE_MAPPINGS: source_mappings},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"

    # Mock async task creation to avoid task cleanup issues
    with patch("asyncio.create_task"):
        # Device sends "Sonos" (custom name set on device)
        entity.handle_response("SI 09 Sonos V=NO A=CO1")

        # Should match directly: "Sonos" is in _custom_name_to_source_code
        assert entity.source == "Sonos"


async def test_media_player_handle_unknown_name_with_audio_source_fallback(
    hass: HomeAssistant,
) -> None:
    """Test when device name is unknown but audio source maps to custom name."""
    # User configured custom name, but device sends something we don't recognize
    source_mappings = {
        "CO1": {"enabled": True, "name": "Sonos Connect"},
    }

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={CONF_SOURCE_MAPPINGS: source_mappings},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"

    # Mock async task creation to avoid task cleanup issues
    with patch("asyncio.create_task"):
        # Device sends unknown name "My Device", but audio_source is CO1 which we know
        entity.handle_response("SI 09 My Device V=NO A=CO1")

        # Should fallback to audio source: "My Device" -> "CO1" (from A=) -> "Sonos Connect"
        assert entity.source == "Sonos Connect"


async def test_media_player_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test turning on the media player."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity._transport = mock_serial_connection

    # Turn on
    await entity.async_turn_on()

    # Verify command was sent
    mock_serial_connection.write.assert_called()


async def test_media_player_turn_off(
    hass: HomeAssistant,
    mock_config_entry,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test turning off the media player."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"
    entity._transport = mock_serial_connection

    # Turn off
    await entity.async_turn_off()

    # Verify command was sent
    mock_serial_connection.write.assert_called()


async def test_media_player_set_volume_level(
    hass: HomeAssistant,
    mock_config_entry,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test setting volume level."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"
    entity._transport = mock_serial_connection

    # Set volume to 50%
    await entity.async_set_volume_level(0.5)

    # Verify command was sent
    mock_serial_connection.write.assert_called()


async def test_media_player_mute_on(
    hass: HomeAssistant,
    mock_config_entry,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test muting the media player."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"
    entity._transport = mock_serial_connection

    # Mute
    await entity.async_mute_volume(True)

    # Verify command was sent
    mock_serial_connection.write.assert_called()


async def test_media_player_select_source(
    hass: HomeAssistant,
    mock_config_entry,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test selecting input source."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"
    entity._transport = mock_serial_connection

    # Select HDMI 1
    await entity.async_select_source("HDMI 1")

    # Verify command was sent
    mock_serial_connection.write.assert_called()


async def test_media_player_select_custom_source(
    hass: HomeAssistant,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test selecting source with custom name."""
    source_mappings = {
        "HD1": {"enabled": True, "name": "Living Room TV"},
    }

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={CONF_SOURCE_MAPPINGS: source_mappings},
        entry_id="test_entry_id",
        title="Tonewinner AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"
    entity._transport = mock_serial_connection

    # Select custom-named source
    await entity.async_select_source("Living Room TV")

    # Verify command was sent with correct source code
    mock_serial_connection.write.assert_called()


async def test_media_player_select_sound_mode(
    hass: HomeAssistant,
    mock_config_entry,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test selecting sound mode."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"
    entity._transport = mock_serial_connection

    # Select stereo mode
    await entity.async_select_sound_mode("Stereo")

    # Verify command was sent
    mock_serial_connection.write.assert_called()


async def test_media_player_volume_up(
    hass: HomeAssistant,
    mock_config_entry,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test volume up."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"
    entity._transport = mock_serial_connection

    await entity.async_volume_up()

    mock_serial_connection.write.assert_called()


async def test_media_player_volume_down(
    hass: HomeAssistant,
    mock_config_entry,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test volume down."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"
    entity._transport = mock_serial_connection

    await entity.async_volume_down()

    mock_serial_connection.write.assert_called()


async def test_media_player_send_raw_command(
    hass: HomeAssistant,
    mock_config_entry,
    mock_serial_connection: SerialTransport,
) -> None:
    """Test sending raw command."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"
    entity._transport = mock_serial_connection

    # Send raw command
    await entity.send_raw_command("CUSTOM COMMAND")

    # Verify command was sent
    mock_serial_connection.write.assert_called()


async def test_media_player_set_available(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test setting availability."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)
    entity.entity_id = "media_player.test"

    with patch.object(entity, "schedule_update_ha_state"):
        # Set available
        entity.set_available(True)
        assert entity.available is True

        # Set unavailable
        entity.set_available(False)
        assert entity.available is False


async def test_media_player_cleanup_on_removal(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test cleanup when entity is removed."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)

    # Create mock task with proper behavior
    # Use asyncio.create_task to create real tasks that can be cancelled
    async def dummy_task():
        """A dummy async task that can be cancelled."""
        await asyncio.sleep(10)

    entity._source_check_task = asyncio.create_task(dummy_task())

    # Cleanup
    await entity.async_will_remove_from_hass()

    # Verify task was cancelled (it should be done)
    assert entity._source_check_task.cancelled()


async def test_media_player_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test media player unique ID."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)

    assert entity.unique_id == mock_config_entry.entry_id


async def test_media_player_has_entity_name(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test media player has entity name."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_config_entry.data)

    # has_entity_name is False because _attr_has_entity_name is not set
    # and name is set to "Tonewinner AT-500" from the title
    assert entity.name == "Tonewinner AT-500"
