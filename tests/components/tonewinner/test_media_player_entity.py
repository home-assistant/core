"""Test the ToneWinner AT-500 media player entity."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

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
    mock_receiver: MagicMock,
) -> None:
    """Test media player entity setup."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    assert entity.unique_id == mock_config_entry.entry_id
    assert entity.has_entity_name is True
    assert entity.name is None
    assert entity.device_class == "receiver"
    assert entity.state == MediaPlayerState.OFF


async def test_media_player_device_info(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test media player device info."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

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
    mock_receiver: MagicMock,
) -> None:
    """Test media player supported features."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    assert entity.supported_features > 0


async def test_media_player_source_list_default(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
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

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    assert entity.source_list
    assert len(entity.source_list) == len(INPUT_SOURCES)
    assert "HDMI 1" in entity.source_list
    assert "Bluetooth" in entity.source_list


async def test_media_player_source_list_with_mappings(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test media player source list with custom mappings."""
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

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    assert "Living Room TV" in entity.source_list
    assert "My Bluetooth" in entity.source_list
    assert "Bedroom TV" not in entity.source_list
    assert "HDMI 1" not in entity.source_list


async def test_media_player_sound_mode_list(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test media player sound mode list."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    assert entity.sound_mode_list
    assert len(entity.sound_mode_list) > 0


async def test_media_player_handle_power_on(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test handling power on via state callback."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    with patch.object(entity, "schedule_update_ha_state"):
        entity._on_state_change(mock_receiver.state)
        assert entity.available is True


async def test_media_player_handle_power_off(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test handling power off via state callback."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"
    entity._attr_source = "HDMI 1"

    mock_receiver.state.power = False
    entity._apply_state(mock_receiver.state)

    assert entity.state == MediaPlayerState.OFF
    assert entity.source is None


async def test_media_player_handle_volume_response(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test handling volume level response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    mock_receiver.state.volume = 50.0
    entity._apply_state(mock_receiver.state)

    assert entity.volume_level is not None
    assert 0 <= entity.volume_level <= 1


async def test_media_player_handle_mute_on(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test handling mute on response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    mock_receiver.state.mute = True
    entity._apply_state(mock_receiver.state)

    assert entity.is_volume_muted is True


async def test_media_player_handle_mute_off(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test handling mute off response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    mock_receiver.state.mute = False
    entity._apply_state(mock_receiver.state)

    assert entity.is_volume_muted is False


async def test_media_player_handle_input_source(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test handling input source response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    mock_receiver.state.source_name = "HDMI 1"
    mock_receiver.state.audio_source = "HDMI"
    mock_receiver.state.power = True
    entity._apply_state(mock_receiver.state)

    assert entity.source == "HDMI 1"


async def test_media_player_handle_custom_source_name(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test handling input source with custom name."""
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

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    mock_receiver.state.source_name = "HDMI 1"
    mock_receiver.state.audio_source = None
    mock_receiver.state.power = True
    entity._apply_state(mock_receiver.state)

    assert entity.source == "Living Room TV"


async def test_media_player_handle_sound_mode(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test handling sound mode response."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    mock_receiver.state.sound_mode_label = "Direct"
    entity._apply_state(mock_receiver.state)

    assert entity.sound_mode == "Direct"


async def test_media_player_handle_uppercase_source_with_custom_name(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test handling uppercase source name with custom mapping."""
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

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    mock_receiver.state.source_name = "COAXIAL 1"
    mock_receiver.state.audio_source = "CO1"
    mock_receiver.state.power = True
    entity._apply_state(mock_receiver.state)

    assert entity.source == "Sonos"


async def test_media_player_handle_custom_name_from_device(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test when device sends custom name that matches our HA config."""
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

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    mock_receiver.state.source_name = "Sonos"
    mock_receiver.state.audio_source = "CO1"
    mock_receiver.state.power = True
    entity._apply_state(mock_receiver.state)

    assert entity.source == "Sonos"


async def test_media_player_handle_unknown_name_with_audio_source_fallback(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test when device name is unknown but audio source maps to custom name."""
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

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    mock_receiver.state.source_name = "My Device"
    mock_receiver.state.audio_source = "CO1"
    mock_receiver.state.power = True
    entity._apply_state(mock_receiver.state)

    assert entity.source == "Sonos Connect"


async def test_media_player_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test turning on the media player."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.async_turn_on()

    mock_receiver.power_on.assert_called_once()


async def test_media_player_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test turning off the media player."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    await entity.async_turn_off()

    mock_receiver.power_off.assert_called_once()


async def test_media_player_set_volume_level(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test setting volume level."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)
    entity.entity_id = "media_player.test"

    await entity.async_set_volume_level(0.5)

    mock_receiver.set_volume.assert_called_once()


async def test_media_player_mute_on(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test muting the media player."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.async_mute_volume(True)

    mock_receiver.mute_on.assert_called_once()


async def test_media_player_select_source(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting input source."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.async_select_source("HDMI 1")

    mock_receiver.select_source.assert_called_once()


async def test_media_player_select_custom_source(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
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

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.async_select_source("Living Room TV")

    mock_receiver.select_source.assert_called_once()


async def test_media_player_select_sound_mode(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting sound mode."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.async_select_sound_mode("Stereo")

    mock_receiver.select_sound_mode.assert_called_once()


async def test_media_player_volume_up(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test volume up."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.async_volume_up()

    mock_receiver.volume_up.assert_called_once()


async def test_media_player_volume_down(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test volume down."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.async_volume_down()

    mock_receiver.volume_down.assert_called_once()


async def test_media_player_send_raw_command(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test sending raw command."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    await entity.send_raw_command("CUSTOM COMMAND")

    mock_receiver.send_command.assert_called_once()


async def test_media_player_cleanup_on_removal(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test cleanup when entity is removed."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    async def dummy_task():
        await asyncio.sleep(10)

    entity._source_check_task = asyncio.create_task(dummy_task())

    await entity.async_will_remove_from_hass()

    assert entity._source_check_task.cancelled()


async def test_media_player_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test media player unique ID."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    assert entity.unique_id == mock_config_entry.entry_id


async def test_media_player_has_entity_name(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_receiver: MagicMock,
) -> None:
    """Test media player has entity name."""
    mock_config_entry.add_to_hass(hass)

    entity = TonewinnerMediaPlayer(hass, mock_config_entry, mock_receiver)

    assert entity.has_entity_name is True
    assert entity.name is None
